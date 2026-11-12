
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "reject"]


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    action_id: UUID
    student_id: UUID
    payload_hash: str
    status: Literal["pending", "approved", "rejected", "expired"]
    expires_at: datetime | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
