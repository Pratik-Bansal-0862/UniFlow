from typing import Literal
from pydantic import BaseModel, Field


class PlannedStep(BaseModel):
    step_id: str
    description: str
    tool_name: str | None = None
    requires_approval: bool = False
    depends_on: list[str] = Field(default_factory=list)


class AgentPlan(BaseModel):
    objective: str
    status: Literal["draft", "ready", "blocked"] = "draft"
    steps: list[PlannedStep] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)