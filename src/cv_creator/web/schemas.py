"""Pydantic schemas for CV Creator web API."""

from datetime import datetime

from pydantic import BaseModel


class TaskResponse(BaseModel):
    id: int
    status: str
    vacancy_text: str
    background_text: str | None
    output_format: str
    cv_style: str
    cv_filename: str
    company_name: str | None
    output_filename: str | None
    cover_letter_filename: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
