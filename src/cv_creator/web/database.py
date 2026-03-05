"""Async SQLAlchemy database setup for CV Creator web app."""

import logging
import os
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("CV_CREATOR_DATA_DIR", "./data"))
UPLOADS_DIR = DATA_DIR / "uploads"
OUTPUTS_DIR = DATA_DIR / "outputs"
PROFILES_DIR = DATA_DIR / "profiles"

_engine = None
_async_session = None


def get_engine():
    global _engine
    if _engine is None:
        db_path = DATA_DIR / "cv_creator.db"
        _engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    return _engine


def get_session_factory():
    global _async_session
    if _async_session is None:
        _async_session = async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _async_session


def set_engine(engine):
    """Override engine and session factory (used in tests)."""
    global _engine, _async_session
    _engine = engine
    _async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Create database tables and data directories."""
    from cv_creator.web.models import Base

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Migrate: add profile_id column to tasks if missing (pre-profiles schema)
    async with get_engine().begin() as conn:
        try:
            result = await conn.execute(text("PRAGMA table_info(tasks)"))
            columns = {row[1] for row in result}
            if "profile_id" not in columns:
                await conn.execute(text("ALTER TABLE tasks ADD COLUMN profile_id INTEGER REFERENCES profiles(id)"))
                logger.info("Migrated tasks table: added profile_id column")
        except Exception:
            logger.debug("Migration check skipped (table may not exist yet)")
