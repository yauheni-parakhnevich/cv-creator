"""Tests for CV Creator web API."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

import cv_creator.web.database as db_module
from cv_creator.web.models import Base


@pytest.fixture
async def client(tmp_path):
    """Create a test HTTP client with a temporary database."""
    db_module.DATA_DIR = tmp_path
    db_module.UPLOADS_DIR = tmp_path / "uploads"
    db_module.OUTPUTS_DIR = tmp_path / "outputs"
    db_module.PROFILES_DIR = tmp_path / "profiles"
    (tmp_path / "uploads").mkdir()
    (tmp_path / "outputs").mkdir()
    (tmp_path / "profiles").mkdir()

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

    db_module._engine = None
    db_module._async_session = None


def make_pdf_bytes():
    return b"%PDF-1.4 fake pdf content"


async def create_profile(client, name="Test User", cv_style="executive", with_cv=True):
    """Helper to create a profile and return its data."""
    files = {}
    data = {"name": name, "cv_style": cv_style}
    if with_cv:
        files["cv_file"] = ("resume.pdf", make_pdf_bytes(), "application/pdf")
    res = await client.post("/api/profiles", data=data, files=files)
    assert res.status_code == 201
    return res.json()


async def create_task_for_profile(client, profile_id, vacancy="Software Engineer at Acme Corp", **kwargs):
    """Helper to create a task linked to a profile."""
    data = {"vacancy_text": vacancy, "profile_id": str(profile_id), **kwargs}
    res = await client.post("/api/tasks", data=data)
    return res


class TestProfiles:
    async def test_create_profile(self, client):
        profile = await create_profile(client)
        assert profile["name"] == "Test User"
        assert profile["cv_style"] == "executive"
        assert profile["cv_filename"] == "resume.pdf"

    async def test_create_profile_without_cv(self, client):
        profile = await create_profile(client, with_cv=False)
        assert profile["cv_filename"] is None

    async def test_create_profile_duplicate_name(self, client):
        await create_profile(client, name="Alice")
        res = await client.post("/api/profiles", data={"name": "Alice"})
        assert res.status_code == 409

    async def test_list_profiles(self, client):
        await create_profile(client, name="Alice")
        await create_profile(client, name="Bob")
        res = await client.get("/api/profiles")
        assert res.status_code == 200
        profiles = res.json()["profiles"]
        assert len(profiles) == 2

    async def test_get_profile(self, client):
        profile = await create_profile(client)
        res = await client.get(f"/api/profiles/{profile['id']}")
        assert res.status_code == 200
        assert res.json()["name"] == "Test User"

    async def test_get_nonexistent_profile(self, client):
        res = await client.get("/api/profiles/9999")
        assert res.status_code == 404

    async def test_update_profile(self, client):
        profile = await create_profile(client)
        res = await client.put(
            f"/api/profiles/{profile['id']}",
            data={"name": "Updated Name", "cv_style": "normal"},
        )
        assert res.status_code == 200
        assert res.json()["name"] == "Updated Name"
        assert res.json()["cv_style"] == "normal"

    async def test_delete_profile(self, client):
        profile = await create_profile(client)
        res = await client.delete(f"/api/profiles/{profile['id']}")
        assert res.status_code == 204
        res = await client.get(f"/api/profiles/{profile['id']}")
        assert res.status_code == 404


class TestCreateTask:
    async def test_create_task_success(self, client):
        profile = await create_profile(client)
        res = await create_task_for_profile(client, profile["id"])
        assert res.status_code == 201
        data = res.json()
        assert data["status"] == "pending"
        assert data["cv_filename"] == "resume.pdf"
        assert data["vacancy_text"] == "Software Engineer at Acme Corp"
        assert data["cv_style"] == "executive"
        assert data["profile_id"] == profile["id"]

    async def test_create_task_with_background(self, client):
        profile = await create_profile(client)
        res = await create_task_for_profile(
            client, profile["id"],
            vacancy="Data Scientist role",
            background_text="Led ML team at previous company",
            output_format="docx",
        )
        assert res.status_code == 201
        data = res.json()
        assert data["background_text"] == "Led ML team at previous company"
        assert data["output_format"] == "docx"

    async def test_create_task_inherits_profile_style(self, client):
        profile = await create_profile(client, cv_style="normal")
        res = await create_task_for_profile(client, profile["id"])
        assert res.status_code == 201
        assert res.json()["cv_style"] == "normal"

    async def test_create_task_override_style(self, client):
        profile = await create_profile(client, cv_style="executive")
        res = await create_task_for_profile(client, profile["id"], cv_style="normal")
        assert res.status_code == 201
        assert res.json()["cv_style"] == "normal"

    async def test_create_task_rejects_invalid_format(self, client):
        profile = await create_profile(client)
        res = await create_task_for_profile(client, profile["id"], output_format="txt")
        assert res.status_code == 400
        assert "format" in res.json()["detail"].lower()

    async def test_create_task_rejects_empty_vacancy(self, client):
        profile = await create_profile(client)
        res = await create_task_for_profile(client, profile["id"], vacancy="   ")
        assert res.status_code == 400

    async def test_create_task_no_cv_no_profile_cv(self, client):
        profile = await create_profile(client, with_cv=False)
        res = await create_task_for_profile(client, profile["id"])
        assert res.status_code == 400
        assert "No CV" in res.json()["detail"]

    async def test_create_task_with_per_task_cv(self, client):
        profile = await create_profile(client, with_cv=False)
        res = await client.post(
            "/api/tasks",
            data={"vacancy_text": "Job", "profile_id": str(profile["id"])},
            files={"cv_file": ("custom.pdf", make_pdf_bytes(), "application/pdf")},
        )
        assert res.status_code == 201
        assert res.json()["cv_filename"] == "custom.pdf"


class TestListTasks:
    async def test_list_empty(self, client):
        res = await client.get("/api/tasks")
        assert res.status_code == 200
        assert res.json()["tasks"] == []

    async def test_list_filtered_by_profile(self, client):
        p1 = await create_profile(client, name="Alice")
        p2 = await create_profile(client, name="Bob")
        await create_task_for_profile(client, p1["id"], vacancy="Job 1")
        await create_task_for_profile(client, p2["id"], vacancy="Job 2")
        await create_task_for_profile(client, p1["id"], vacancy="Job 3")

        res = await client.get(f"/api/tasks?profile_id={p1['id']}")
        assert res.status_code == 200
        tasks = res.json()["tasks"]
        assert len(tasks) == 2

        res = await client.get(f"/api/tasks?profile_id={p2['id']}")
        tasks = res.json()["tasks"]
        assert len(tasks) == 1

    async def test_list_all_without_filter(self, client):
        p1 = await create_profile(client, name="Alice")
        p2 = await create_profile(client, name="Bob")
        await create_task_for_profile(client, p1["id"])
        await create_task_for_profile(client, p2["id"])
        res = await client.get("/api/tasks")
        assert len(res.json()["tasks"]) == 2


class TestGetTask:
    async def test_get_existing(self, client):
        profile = await create_profile(client)
        create_res = await create_task_for_profile(client, profile["id"])
        task_id = create_res.json()["id"]
        res = await client.get(f"/api/tasks/{task_id}")
        assert res.status_code == 200
        assert res.json()["id"] == task_id

    async def test_get_nonexistent(self, client):
        res = await client.get("/api/tasks/9999")
        assert res.status_code == 404


class TestDeleteTask:
    async def test_delete_existing(self, client):
        profile = await create_profile(client)
        create_res = await create_task_for_profile(client, profile["id"])
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
        profile = await create_profile(client)
        create_res = await create_task_for_profile(client, profile["id"])
        task_id = create_res.json()["id"]
        res = await client.get(f"/api/tasks/{task_id}/download")
        assert res.status_code == 400

    async def test_download_cover_letter_not_completed(self, client):
        profile = await create_profile(client)
        create_res = await create_task_for_profile(client, profile["id"])
        task_id = create_res.json()["id"]
        res = await client.get(f"/api/tasks/{task_id}/download-cover-letter")
        assert res.status_code == 400

    async def test_download_cover_letter_not_found(self, client):
        res = await client.get("/api/tasks/9999/download-cover-letter")
        assert res.status_code == 404
