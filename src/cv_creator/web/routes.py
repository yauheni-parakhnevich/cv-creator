"""API routes for CV Creator web app."""

import logging
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import select

from cv_creator.web.database import OUTPUTS_DIR, UPLOADS_DIR, get_session_factory
from cv_creator.web.models import Task, TaskStatus
from cv_creator.web.schemas import TaskListResponse, TaskResponse
from cv_creator.web.worker import cleanup_task_files, task_queue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    cv_file: UploadFile,
    vacancy_text: str = Form(),
    background_text: str | None = Form(None),
    output_format: str = Form("docx"),
    cv_style: str = Form("executive"),
):
    """Create a new CV optimization task."""
    allowed_extensions = (".pdf", ".md")
    if not cv_file.filename or not cv_file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(status_code=400, detail="CV file must be a PDF or Markdown (.md).")

    if output_format not in ("pdf", "docx"):
        raise HTTPException(status_code=400, detail="Output format must be 'pdf' or 'docx'.")

    if cv_style not in ("executive", "normal"):
        raise HTTPException(status_code=400, detail="CV style must be 'executive' or 'normal'.")

    if not vacancy_text.strip():
        raise HTTPException(status_code=400, detail="Vacancy text is required.")

    async with get_session_factory()() as session:
        task = Task(
            vacancy_text=vacancy_text,
            background_text=background_text if background_text and background_text.strip() else None,
            output_format=output_format,
            cv_style=cv_style,
            cv_filename=cv_file.filename,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)

        # Save uploaded file
        upload_dir = UPLOADS_DIR / str(task.id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(cv_file.filename).suffix.lower()
        file_path = upload_dir / f"original{ext}"
        content = await cv_file.read()
        file_path.write_bytes(content)

        # Enqueue for processing
        await task_queue.put(task.id)
        logger.info("Task %d created and enqueued", task.id)

        return TaskResponse.model_validate(task)


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks():
    """List all tasks, newest first."""
    async with get_session_factory()() as session:
        result = await session.execute(select(Task).order_by(Task.created_at.desc()))
        tasks = result.scalars().all()
        return TaskListResponse(tasks=[TaskResponse.model_validate(t) for t in tasks])


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int):
    """Get task details."""
    async with get_session_factory()() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        return TaskResponse.model_validate(task)


@router.get("/tasks/{task_id}/download")
async def download_output(task_id: int):
    """Download the output file for a completed task."""
    async with get_session_factory()() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        if task.status != TaskStatus.completed:
            raise HTTPException(status_code=400, detail="Task is not completed yet.")
        if not task.output_filename:
            raise HTTPException(status_code=404, detail="Output file not found.")

    output_path = OUTPUTS_DIR / str(task_id) / task.output_filename
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file not found on disk.")

    media_type = "application/pdf" if task.output_format == "pdf" else (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return FileResponse(
        path=output_path,
        filename=task.output_filename,
        media_type=media_type,
    )


@router.get("/tasks/{task_id}/summary")
async def get_summary(task_id: int):
    """Get the changes summary markdown for a completed task."""
    async with get_session_factory()() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        if task.status != TaskStatus.completed:
            raise HTTPException(status_code=404, detail="Summary not available yet.")
        if not task.output_filename:
            raise HTTPException(status_code=404, detail="Output not found.")

    summary_path = OUTPUTS_DIR / str(task_id) / (task.output_filename + ".summary.md")
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="Summary file not found.")

    return PlainTextResponse(summary_path.read_text(), media_type="text/markdown")


@router.get("/tasks/{task_id}/download-cover-letter")
async def download_cover_letter(task_id: int):
    """Download the cover letter file for a completed task."""
    async with get_session_factory()() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        if task.status != TaskStatus.completed:
            raise HTTPException(status_code=400, detail="Task is not completed yet.")
        if not task.cover_letter_filename:
            raise HTTPException(status_code=404, detail="Cover letter not available.")

    output_path = OUTPUTS_DIR / str(task_id) / task.cover_letter_filename
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Cover letter file not found on disk.")

    media_type = "application/pdf" if task.output_format == "pdf" else (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return FileResponse(
        path=output_path,
        filename=task.cover_letter_filename,
        media_type=media_type,
    )


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int):
    """Delete a task and its files."""
    async with get_session_factory()() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        await session.delete(task)
        await session.commit()

    cleanup_task_files(task_id)
