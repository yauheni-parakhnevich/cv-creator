"""FastAPI application factory for CV Creator web app."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from cv_creator.web.database import init_db
from cv_creator.web.routes import router
from cv_creator.web.worker import recover_stuck_tasks, worker_loop

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database, recover stuck tasks, and start background worker."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    await init_db()
    await recover_stuck_tasks()
    worker_task = asyncio.create_task(worker_loop())
    logger.info("CV Creator web app started")
    yield
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    logger.info("CV Creator web app stopped")


def create_app(use_lifespan: bool = True) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="CV Creator", version="0.3.0", lifespan=lifespan if use_lifespan else None)
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def index():
        return FileResponse(STATIC_DIR / "login.html")

    @app.get("/app")
    async def main_app():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/tasks/{task_id}")
    async def task_detail(task_id: int):
        return FileResponse(STATIC_DIR / "detail.html")

    return app


app = create_app()
