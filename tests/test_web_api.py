"""Tests for CV Creator web API."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

import cv_creator.web.database as db_module
from cv_creator.web.models import Base


@pytest.fixture
async def client(tmp_path):
    """Create a test HTTP client with a temporary database."""
    # Override database module globals before importing app
    db_module.DATA_DIR = tmp_path
    db_module.UPLOADS_DIR = tmp_path / "uploads"
    db_module.OUTPUTS_DIR = tmp_path / "outputs"
    (tmp_path / "uploads").mkdir()
    (tmp_path / "outputs").mkdir()

    test_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", echo=False)
    db_module.set_engine(test_engine)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from cv_creator.web.app import create_app

    app = create_app(use_lifespan=False)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()

    # Reset module globals
    db_module._engine = None
    db_module._async_session = None


def make_pdf_bytes():
    return b"%PDF-1.4 fake pdf content"


class TestCreateTask:
    async def test_create_task_success(self, client):
        res = await client.post(
            "/api/tasks",
            files={"cv_file": ("resume.pdf", make_pdf_bytes(), "application/pdf")},
            data={"vacancy_text": "Software Engineer at Acme Corp", "output_format": "pdf"},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["status"] == "pending"
        assert data["cv_filename"] == "resume.pdf"
        assert data["vacancy_text"] == "Software Engineer at Acme Corp"
        assert data["output_format"] == "pdf"
        assert data["cv_style"] == "executive"
        assert data["company_name"] is None
        assert data["cover_letter_filename"] is None

    async def test_create_task_with_background(self, client):
        res = await client.post(
            "/api/tasks",
            files={"cv_file": ("cv.pdf", make_pdf_bytes(), "application/pdf")},
            data={
                "vacancy_text": "Data Scientist role",
                "background_text": "Led ML team at previous company",
                "output_format": "docx",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["background_text"] == "Led ML team at previous company"
        assert data["output_format"] == "docx"

    async def test_create_task_rejects_non_pdf(self, client):
        res = await client.post(
            "/api/tasks",
            files={"cv_file": ("resume.docx", b"not a pdf", "application/octet-stream")},
            data={"vacancy_text": "Some job"},
        )
        assert res.status_code == 400
        assert "PDF" in res.json()["detail"]

    async def test_create_task_rejects_invalid_format(self, client):
        res = await client.post(
            "/api/tasks",
            files={"cv_file": ("resume.pdf", make_pdf_bytes(), "application/pdf")},
            data={"vacancy_text": "Some job", "output_format": "txt"},
        )
        assert res.status_code == 400
        assert "format" in res.json()["detail"].lower()

    async def test_create_task_with_normal_style(self, client):
        res = await client.post(
            "/api/tasks",
            files={"cv_file": ("cv.pdf", make_pdf_bytes(), "application/pdf")},
            data={"vacancy_text": "Developer role", "cv_style": "normal"},
        )
        assert res.status_code == 201
        assert res.json()["cv_style"] == "normal"

    async def test_create_task_rejects_invalid_style(self, client):
        res = await client.post(
            "/api/tasks",
            files={"cv_file": ("resume.pdf", make_pdf_bytes(), "application/pdf")},
            data={"vacancy_text": "Some job", "cv_style": "fancy"},
        )
        assert res.status_code == 400
        assert "style" in res.json()["detail"].lower()

    async def test_create_task_rejects_empty_vacancy(self, client):
        res = await client.post(
            "/api/tasks",
            files={"cv_file": ("resume.pdf", make_pdf_bytes(), "application/pdf")},
            data={"vacancy_text": "   "},
        )
        assert res.status_code == 400


class TestListTasks:
    async def test_list_empty(self, client):
        res = await client.get("/api/tasks")
        assert res.status_code == 200
        assert res.json()["tasks"] == []

    async def test_list_after_create(self, client):
        await client.post(
            "/api/tasks",
            files={"cv_file": ("a.pdf", make_pdf_bytes(), "application/pdf")},
            data={"vacancy_text": "Job 1"},
        )
        await client.post(
            "/api/tasks",
            files={"cv_file": ("b.pdf", make_pdf_bytes(), "application/pdf")},
            data={"vacancy_text": "Job 2"},
        )
        res = await client.get("/api/tasks")
        assert res.status_code == 200
        tasks = res.json()["tasks"]
        assert len(tasks) == 2
        # Newest first
        assert tasks[0]["cv_filename"] == "b.pdf"


class TestGetTask:
    async def test_get_existing(self, client):
        create_res = await client.post(
            "/api/tasks",
            files={"cv_file": ("cv.pdf", make_pdf_bytes(), "application/pdf")},
            data={"vacancy_text": "Job description"},
        )
        task_id = create_res.json()["id"]
        res = await client.get(f"/api/tasks/{task_id}")
        assert res.status_code == 200
        assert res.json()["id"] == task_id

    async def test_get_nonexistent(self, client):
        res = await client.get("/api/tasks/9999")
        assert res.status_code == 404


class TestDeleteTask:
    async def test_delete_existing(self, client):
        create_res = await client.post(
            "/api/tasks",
            files={"cv_file": ("cv.pdf", make_pdf_bytes(), "application/pdf")},
            data={"vacancy_text": "Job"},
        )
        task_id = create_res.json()["id"]
        res = await client.delete(f"/api/tasks/{task_id}")
        assert res.status_code == 204

        res = await client.get(f"/api/tasks/{task_id}")
        assert res.status_code == 404

    async def test_delete_nonexistent(self, client):
        res = await client.delete("/api/tasks/9999")
        assert res.status_code == 404


class TestDownload:
    async def test_download_not_completed(self, client):
        create_res = await client.post(
            "/api/tasks",
            files={"cv_file": ("cv.pdf", make_pdf_bytes(), "application/pdf")},
            data={"vacancy_text": "Job"},
        )
        task_id = create_res.json()["id"]
        res = await client.get(f"/api/tasks/{task_id}/download")
        assert res.status_code == 400

    async def test_download_cover_letter_not_completed(self, client):
        create_res = await client.post(
            "/api/tasks",
            files={"cv_file": ("cv.pdf", make_pdf_bytes(), "application/pdf")},
            data={"vacancy_text": "Job"},
        )
        task_id = create_res.json()["id"]
        res = await client.get(f"/api/tasks/{task_id}/download-cover-letter")
        assert res.status_code == 400

    async def test_download_cover_letter_not_found(self, client):
        res = await client.get("/api/tasks/9999/download-cover-letter")
        assert res.status_code == 404
