"""API routes for CV Creator web app."""

import logging
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import select

from cv_creator.web.database import OUTPUTS_DIR, PROFILES_DIR, UPLOADS_DIR, get_session_factory
from cv_creator.web.models import Profile, Task, TaskStatus
from cv_creator.web.schemas import ProfileListResponse, ProfileResponse, TaskListResponse, TaskResponse
from cv_creator.web.worker import cleanup_task_files, task_queue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def _sanitize_company(name: str | None) -> str | None:
    """Return a filesystem-safe version of the company name, or None."""
    if not name or name.strip().lower() in ("", "unknown company"):
        return None
    sanitized = re.sub(r"[^\w\s\-.]", "", name.strip())
    sanitized = re.sub(r"\s+", "_", sanitized)
    return sanitized or None


def _download_filename(base: str, company: str | None, ext: str) -> str:
    """Build a download filename like 'optimized_cv_Google.docx'."""
    if company:
        return f"{base}_{company}{ext}"
    return f"{base}{ext}"


# ── Profile endpoints ──────────────────────────────────────────────────────


@router.get("/profiles", response_model=ProfileListResponse)
async def list_profiles():
    """List all profiles."""
    async with get_session_factory()() as session:
        result = await session.execute(select(Profile).order_by(Profile.name))
        profiles = result.scalars().all()
        return ProfileListResponse(profiles=[ProfileResponse.model_validate(p) for p in profiles])


@router.post("/profiles", response_model=ProfileResponse, status_code=201)
async def create_profile(
    name: str = Form(),
    cv_style: str = Form("executive"),
    cv_file: UploadFile | None = None,
):
    """Create a new profile."""
    if not name.strip():
        raise HTTPException(status_code=400, detail="Profile name is required.")
    if cv_style not in ("executive", "normal"):
        raise HTTPException(status_code=400, detail="CV style must be 'executive' or 'normal'.")

    cv_filename = None
    if cv_file and cv_file.filename:
        allowed = (".pdf", ".md")
        if not cv_file.filename.lower().endswith(allowed):
            raise HTTPException(status_code=400, detail="CV file must be a PDF or Markdown (.md).")
        cv_filename = cv_file.filename

    async with get_session_factory()() as session:
        # Check uniqueness
        existing = await session.execute(select(Profile).where(Profile.name == name.strip()))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="A profile with this name already exists.")

        profile = Profile(name=name.strip(), cv_style=cv_style, cv_filename=cv_filename)
        session.add(profile)
        await session.commit()
        await session.refresh(profile)

        # Save CV file
        if cv_file and cv_filename:
            profile_dir = PROFILES_DIR / str(profile.id)
            profile_dir.mkdir(parents=True, exist_ok=True)
            ext = Path(cv_filename).suffix.lower()
            file_path = profile_dir / f"cv{ext}"
            content = await cv_file.read()
            file_path.write_bytes(content)

        return ProfileResponse.model_validate(profile)


@router.get("/profiles/{profile_id}", response_model=ProfileResponse)
async def get_profile(profile_id: int):
    """Get a single profile."""
    async with get_session_factory()() as session:
        result = await session.execute(select(Profile).where(Profile.id == profile_id))
        profile = result.scalar_one_or_none()
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found.")
        return ProfileResponse.model_validate(profile)


@router.put("/profiles/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: int,
    name: str = Form(None),
    cv_style: str = Form(None),
    cv_file: UploadFile | None = None,
):
    """Update a profile."""
    async with get_session_factory()() as session:
        result = await session.execute(select(Profile).where(Profile.id == profile_id))
        profile = result.scalar_one_or_none()
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found.")

        if name is not None and name.strip():
            # Check uniqueness if name changed
            if name.strip() != profile.name:
                dup = await session.execute(select(Profile).where(Profile.name == name.strip()))
                if dup.scalar_one_or_none():
                    raise HTTPException(status_code=409, detail="A profile with this name already exists.")
            profile.name = name.strip()

        if cv_style is not None:
            if cv_style not in ("executive", "normal"):
                raise HTTPException(status_code=400, detail="CV style must be 'executive' or 'normal'.")
            profile.cv_style = cv_style

        if cv_file and cv_file.filename:
            allowed = (".pdf", ".md")
            if not cv_file.filename.lower().endswith(allowed):
                raise HTTPException(status_code=400, detail="CV file must be a PDF or Markdown (.md).")
            profile.cv_filename = cv_file.filename
            profile_dir = PROFILES_DIR / str(profile.id)
            profile_dir.mkdir(parents=True, exist_ok=True)
            # Remove old CV files
            for old in profile_dir.glob("cv.*"):
                old.unlink()
            ext = Path(cv_file.filename).suffix.lower()
            file_path = profile_dir / f"cv{ext}"
            content = await cv_file.read()
            file_path.write_bytes(content)

        await session.commit()
        await session.refresh(profile)
        return ProfileResponse.model_validate(profile)


@router.delete("/profiles/{profile_id}", status_code=204)
async def delete_profile(profile_id: int):
    """Delete a profile and its files."""
    async with get_session_factory()() as session:
        result = await session.execute(select(Profile).where(Profile.id == profile_id))
        profile = result.scalar_one_or_none()
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found.")
        await session.delete(profile)
        await session.commit()

    profile_dir = PROFILES_DIR / str(profile_id)
    if profile_dir.exists():
        shutil.rmtree(profile_dir)


# ── Task endpoints ─────────────────────────────────────────────────────────


@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    vacancy_text: str = Form(),
    profile_id: int = Form(),
    background_text: str | None = Form(None),
    output_format: str = Form("docx"),
    cv_style: str | None = Form(None),
    cv_file: UploadFile | None = None,
):
    """Create a new CV optimization task."""
    if output_format not in ("pdf", "docx"):
        raise HTTPException(status_code=400, detail="Output format must be 'pdf' or 'docx'.")
    if not vacancy_text.strip():
        raise HTTPException(status_code=400, detail="Vacancy text is required.")

    # Load profile
    async with get_session_factory()() as session:
        result = await session.execute(select(Profile).where(Profile.id == profile_id))
        profile = result.scalar_one_or_none()
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found.")

    # Determine CV style (use profile default if not overridden)
    task_cv_style = cv_style if cv_style in ("executive", "normal") else profile.cv_style

    # Determine CV source: per-task upload or profile CV
    if cv_file and cv_file.filename:
        allowed = (".pdf", ".md")
        if not cv_file.filename.lower().endswith(allowed):
            raise HTTPException(status_code=400, detail="CV file must be a PDF or Markdown (.md).")
        cv_filename = cv_file.filename
        cv_content = await cv_file.read()
        cv_from_profile = False
    elif profile.cv_filename:
        cv_filename = profile.cv_filename
        cv_content = None
        cv_from_profile = True
    else:
        raise HTTPException(status_code=400, detail="No CV file provided and profile has no CV uploaded.")

    async with get_session_factory()() as session:
        task = Task(
            profile_id=profile_id,
            vacancy_text=vacancy_text,
            background_text=background_text if background_text and background_text.strip() else None,
            output_format=output_format,
            cv_style=task_cv_style,
            cv_filename=cv_filename,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)

        # Save CV to task upload dir
        upload_dir = UPLOADS_DIR / str(task.id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(cv_filename).suffix.lower()
        file_path = upload_dir / f"original{ext}"

        if cv_from_profile:
            # Copy from profile directory
            profile_cv = PROFILES_DIR / str(profile_id) / f"cv{ext}"
            shutil.copy2(profile_cv, file_path)
        else:
            file_path.write_bytes(cv_content)

        # Enqueue for processing
        await task_queue.put(task.id)
        logger.info("Task %d created for profile %d and enqueued", task.id, profile_id)

        return TaskResponse.model_validate(task)


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    profile_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
):
    """List tasks, optionally filtered by profile, with pagination."""
    async with get_session_factory()() as session:
        base = select(Task)
        if profile_id is not None:
            base = base.where(Task.profile_id == profile_id)
        # Count total
        from sqlalchemy import func

        count_result = await session.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0
        pages = max(1, (total + per_page - 1) // per_page)
        # Fetch page
        query = base.order_by(Task.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        result = await session.execute(query)
        tasks = result.scalars().all()
        return TaskListResponse(
            tasks=[TaskResponse.model_validate(t) for t in tasks],
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
        )


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
    company = _sanitize_company(task.company_name)
    ext = Path(task.output_filename).suffix
    download_name = _download_filename("optimized_cv", company, ext)
    return FileResponse(
        path=output_path,
        filename=download_name,
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
    company = _sanitize_company(task.company_name)
    ext = Path(task.cover_letter_filename).suffix
    download_name = _download_filename("cover_letter", company, ext)
    return FileResponse(
        path=output_path,
        filename=download_name,
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
