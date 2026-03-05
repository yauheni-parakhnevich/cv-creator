"""Background worker for processing CV optimization tasks."""

import asyncio
import logging
import shutil
from datetime import datetime, timezone

from sqlalchemy import select, update

from cv_creator.web.database import OUTPUTS_DIR, UPLOADS_DIR, get_session_factory
from cv_creator.web.models import Task, TaskStatus

logger = logging.getLogger(__name__)

task_queue: asyncio.Queue[int] = asyncio.Queue()


async def recover_stuck_tasks():
    """Reset tasks stuck in 'processing' status back to 'pending' and re-enqueue them."""
    async with get_session_factory()() as session:
        result = await session.execute(select(Task).where(Task.status == TaskStatus.processing))
        stuck_tasks = result.scalars().all()
        for task in stuck_tasks:
            task.status = TaskStatus.pending
            task.updated_at = datetime.now(timezone.utc)
            logger.info("Recovered stuck task %d, re-enqueuing", task.id)
        await session.commit()

        for task in stuck_tasks:
            await task_queue.put(task.id)


async def process_task(task_id: int):
    """Process a single CV optimization task."""
    async with get_session_factory()() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            logger.warning("Task %d not found, skipping", task_id)
            return

        vacancy_text = task.vacancy_text
        background_text = task.background_text
        output_format = task.output_format
        cv_style = task.cv_style

        # Mark as processing
        task.status = TaskStatus.processing
        task.updated_at = datetime.now(timezone.utc)
        await session.commit()

    try:
        # Import lazily to avoid circular imports
        from cv_creator.agents import run_cv_optimization
        from cv_creator.agents.company_extractor import get_company_extractor_agent
        from cv_creator.config import initialize

        # Extract company name as a quick pre-step
        try:
            initialize()
            agent = get_company_extractor_agent()
            result = await agent.run(
                f"Extract the company name from this vacancy description:\n\n{vacancy_text}"
            )
            company_name = result.text.strip()
            async with get_session_factory()() as session:
                await session.execute(
                    update(Task)
                    .where(Task.id == task_id)
                    .values(company_name=company_name, updated_at=datetime.now(timezone.utc))
                )
                await session.commit()
            logger.info("Task %d: extracted company name '%s'", task_id, company_name)
        except Exception:
            logger.exception("Task %d: failed to extract company name, continuing", task_id)

        upload_dir = UPLOADS_DIR / str(task_id)
        output_dir = OUTPUTS_DIR / str(task_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Find the uploaded CV file (original.pdf or original.md)
        cv_candidates = list(upload_dir.glob("original.*"))
        if not cv_candidates:
            raise FileNotFoundError(f"No uploaded CV found in {upload_dir}")
        cv_path = cv_candidates[0]
        output_ext = output_format if output_format in ("pdf", "docx") else "pdf"
        output_path = output_dir / f"optimized_cv.{output_ext}"

        await run_cv_optimization(
            vacancy_description=vacancy_text,
            cv_pdf_path=str(cv_path),
            output_path=str(output_path),
            background=background_text,
            verbose=True,
            output_format=output_format,
            cv_style=cv_style,
        )

        # Detect cover letter file produced by the workflow
        cover_letter_filename = None
        for cl_candidate in output_dir.glob(f"cover_letter.{output_ext}"):
            cover_letter_filename = cl_candidate.name
            break
        if cover_letter_filename:
            logger.info("Task %d: cover letter found: %s", task_id, cover_letter_filename)

        # Update task as completed
        async with get_session_factory()() as session:
            await session.execute(
                update(Task)
                .where(Task.id == task_id)
                .values(
                    status=TaskStatus.completed,
                    output_filename=output_path.name,
                    cover_letter_filename=cover_letter_filename,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        logger.info("Task %d completed successfully", task_id)

    except Exception as e:
        logger.exception("Task %d failed: %s", task_id, e)
        async with get_session_factory()() as session:
            await session.execute(
                update(Task)
                .where(Task.id == task_id)
                .values(
                    status=TaskStatus.failed,
                    error_message=str(e),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()


async def worker_loop():
    """Main worker loop: processes tasks from the queue one at a time."""
    logger.info("Background worker started")
    while True:
        task_id = await task_queue.get()
        logger.info("Processing task %d", task_id)
        try:
            await process_task(task_id)
        except Exception:
            logger.exception("Unexpected error processing task %d", task_id)
        finally:
            task_queue.task_done()


def cleanup_task_files(task_id: int):
    """Remove uploaded and output files for a task."""
    upload_dir = UPLOADS_DIR / str(task_id)
    output_dir = OUTPUTS_DIR / str(task_id)
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
