from typing import Any, Literal
from pydantic import BaseModel, Field


class ToolRequest(BaseModel):
    tool_name: str
    student_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    approval_id: str | None = None
    idempotency_key: str


class ToolResult(BaseModel):
    status: Literal[
        "succeeded",
        "failed",
        "pending_approval",
        "unverified",
    ]
    data: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    message: str | None = None
    external_reference: str | None = None
    verified: bool = False