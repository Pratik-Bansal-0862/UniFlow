from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_student, get_db
from app.models.student import Student
from app.schemas.agent_plan import AgentPlan
from app.services.orchestrator_service import OrchestratorService

router = APIRouter()


class PlanRequest(BaseModel):
    objective: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


@router.post("/plan", response_model=AgentPlan)
def create_plan(
    request: PlanRequest,
    student: Annotated[Student, Depends(get_current_student)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentPlan:
    try:
        return OrchestratorService().plan(
            request.objective,
            student_id=str(student.id),
            limit=request.limit,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc