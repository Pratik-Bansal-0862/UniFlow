
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_student, get_db
from app.models.agent_action import AgentAction
from app.models.student import Student
from app.schemas.action import ActionCreate, ActionRead
from app.services.action_service import ActionError, create_action
from app.services.approval_service import (
    ApprovalError,
    calculate_payload_hash,
    create_approval,
)

router = APIRouter()


@router.post(
    "",
    response_model=ActionRead,
    status_code=status.HTTP_201_CREATED,
)
def submit_action(
    payload: ActionCreate,
    current_student: Annotated[Student, Depends(get_current_student)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        # Check whether this student has already submitted this key.
        existing = db.execute(
            select(AgentAction).where(
                AgentAction.student_id == current_student.id,
                AgentAction.idempotency_key == payload.idempotency_key,
            )
        ).scalar_one_or_none()

        if existing is not None:
            requested_hash = calculate_payload_hash(
                payload.tool_name,
                payload.arguments,
            )

            if existing.payload_hash != requested_hash:
                raise ActionError(
                    "Idempotency key was already used for a different action."
                )

            # Same key and payload: return the existing action.
            return existing

        # Create a new action and its approval record.
        action = create_action(
            db=db,
            student_id=current_student.id,
            tool_name=payload.tool_name,
            arguments=payload.arguments,
            idempotency_key=payload.idempotency_key,
        )

        create_approval(db, action)

        db.commit()
        db.refresh(action)

        return action

    except (ActionError, ApprovalError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An action with this idempotency key already exists.",
        ) from exc

    except Exception:
        db.rollback()
        raise


@router.get(
    "",
    response_model=list[ActionRead],
)
def list_actions(
    current_student: Annotated[Student, Depends(get_current_student)],
    db: Annotated[Session, Depends(get_db)],
):
    return db.execute(
        select(AgentAction)
        .where(AgentAction.student_id == current_student.id)
        .order_by(AgentAction.created_at.desc())
    ).scalars().all()


@router.get(
    "/{action_id}",
    response_model=ActionRead,
)
def get_action(
    action_id: UUID,
    current_student: Annotated[Student, Depends(get_current_student)],
    db: Annotated[Session, Depends(get_db)],
):
    action = db.execute(
        select(AgentAction).where(
            AgentAction.id == action_id,
            AgentAction.student_id == current_student.id,
        )
    ).scalar_one_or_none()

    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found.",
        )

    return action
