from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_student, get_db
from app.models.student import Student
from app.services.academic_service import (
    AcademicPlanRequest,
    AcademicPlanResponse,
    AcademicService,
)
from app.services.communication_service import (
    CommunicationDraftRequest,
    CommunicationDraftResponse,
    CommunicationService,
)

router = APIRouter(prefix="/agents", tags=["Agents"])

academic_service = AcademicService()
communication_service = CommunicationService()


@router.post("/academic/plan", response_model=AcademicPlanResponse)
def create_academic_plan(
    payload: AcademicPlanRequest,
    db: Annotated[Session, Depends(get_db)],
    current_student: Annotated[Student, Depends(get_current_student)],
) -> AcademicPlanResponse:
    try:
        return academic_service.generate_academic_plan(
            db=db,
            student_id=str(current_student.id),
            request=payload,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Academic Agent error: {str(e)}",
        )


@router.post("/communication/draft", response_model=CommunicationDraftResponse)
def create_communication_draft(
    payload: CommunicationDraftRequest,
    db: Annotated[Session, Depends(get_db)],
    current_student: Annotated[Student, Depends(get_current_student)],
) -> CommunicationDraftResponse:
    try:
        return communication_service.generate_draft(
            db=db,
            student_id=str(current_student.id),
            request=payload,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Communication Agent error: {str(e)}",
        )