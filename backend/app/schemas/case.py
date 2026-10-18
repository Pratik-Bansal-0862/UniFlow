from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    case_type: str = Field(min_length=1, max_length=100)
    priority: str = "medium"
    deadline: datetime | None = None


class CaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    title: str
    description: str | None
    case_type: str
    status: str
    priority: str
    deadline: datetime | None
    created_at: datetime
    updated_at: datetime