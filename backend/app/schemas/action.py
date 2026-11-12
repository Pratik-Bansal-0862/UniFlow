
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ActionCreate(BaseModel):
    tool_name: str = Field(min_length=1, max_length=100)
    arguments: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=128)


class ActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tool_name: str
    arguments: dict[str, Any]
    payload_hash: str
    status: Literal[
        "pending_approval",
        "approved",
        "executing",
        "succeeded",
        "failed",
        "rejected",
    ]
    result: dict[str, Any] | None = None
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime
    executed_at: datetime | None = None
