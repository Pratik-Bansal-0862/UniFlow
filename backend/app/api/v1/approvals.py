
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.dependencies import get_current_student, get_db
from app.models.student import Student
from app.schemas.approval import ApprovalDecision, ApprovalRead
from app.services.approval_service import (
    ApprovalError,
    decide_approval,
)

router = APIRouter()


@router.post(
    "/{approval_id}/decision",
    response_model=ApprovalRead,
)
def submit_approval_decision(
    approval_id: UUID,
    payload: ApprovalDecision,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    try:
        approval = decide_approval(
            db=db,
            approval_id=approval_id,
            student_id=current_student.id,
            decision=payload.decision,
        )

        db.commit()
        db.refresh(approval)
        return approval

    except ApprovalError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except Exception:
        db.rollback()
        raise
