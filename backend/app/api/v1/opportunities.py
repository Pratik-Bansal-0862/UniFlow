from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_student, get_db
from app.models.opportunity import Opportunity
from app.models.student import Student
from app.services.opportunity_discovery import discover_and_save
from app.schemas.opportunity import (
    OpportunityCreate,
    OpportunityRead,
    OpportunityUpdate,
)

router = APIRouter(tags=["Opportunities"])




@router.post("/discover", status_code=status.HTTP_200_OK)
def discover_opportunities(
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[Student, Depends(get_current_student)],
) -> dict:
    """Discover public student/early-career listings from multiple sources."""
    return discover_and_save(db, student)

@router.post(
    "",
    response_model=OpportunityRead,
    status_code=status.HTTP_201_CREATED,
)
def create_opportunity(
    payload: OpportunityCreate,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[Student, Depends(get_current_student)],
) -> Opportunity:
    values = payload.model_dump()
    if values.get("application_url") is not None:
        values["application_url"] = str(values["application_url"])

    item = Opportunity(student_id=student.id, **values)
    db.add(item)
    try:
        db.commit()
        db.refresh(item)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This source item already exists for your account",
        ) from None
    return item


@router.get("", response_model=list[OpportunityRead])
def list_opportunities(
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[Student, Depends(get_current_student)],
    opportunity_status: Annotated[
        str | None,
        Query(alias="status", pattern="^(discovered|saved|applied|dismissed|expired)$"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Opportunity]:
    statement = select(Opportunity).where(
        Opportunity.student_id == student.id
    )
    if opportunity_status:
        statement = statement.where(Opportunity.status == opportunity_status)
    statement = statement.order_by(
        Opportunity.deadline.asc().nulls_last(),
        Opportunity.created_at.desc(),
    ).offset(offset).limit(limit)
    return list(db.scalars(statement).all())


@router.get("/{opportunity_id}", response_model=OpportunityRead)
def get_opportunity(
    opportunity_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[Student, Depends(get_current_student)],
) -> Opportunity:
    item = db.scalar(
        select(Opportunity).where(
            Opportunity.id == opportunity_id,
            Opportunity.student_id == student.id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return item


@router.patch("/{opportunity_id}", response_model=OpportunityRead)
def update_opportunity(
    opportunity_id: UUID,
    payload: OpportunityUpdate,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[Student, Depends(get_current_student)],
) -> Opportunity:
    item = db.scalar(
        select(Opportunity).where(
            Opportunity.id == opportunity_id,
            Opportunity.student_id == student.id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    changes = payload.model_dump(exclude_unset=True)
    if changes.get("application_url") is not None:
        changes["application_url"] = str(changes["application_url"])
    for field, value in changes.items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return item


@router.delete("/{opportunity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_opportunity(
    opportunity_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[Student, Depends(get_current_student)],
) -> None:
    item = db.scalar(
        select(Opportunity).where(
            Opportunity.id == opportunity_id,
            Opportunity.student_id == student.id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    db.delete(item)
    db.commit()


