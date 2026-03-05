"""SQLAlchemy models for CV Creator web app."""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    cv_style: Mapped[str] = mapped_column(String(20), default="executive", nullable=False)
    cv_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tasks: Mapped[list["Task"]] = relationship(back_populates="profile")


class TaskStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("profiles.id"), nullable=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.pending, nullable=False)
    vacancy_text: Mapped[str] = mapped_column(Text, nullable=False)
    background_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_format: Mapped[str] = mapped_column(String(10), default="docx", nullable=False)
    cv_style: Mapped[str] = mapped_column(String(20), default="executive", nullable=False)
    cv_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    output_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cover_letter_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    profile: Mapped[Profile | None] = relationship(back_populates="tasks")
