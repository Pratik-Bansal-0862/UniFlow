from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.schemas.case import CaseCreate


def create_case(
    db: Session,
    student_id: UUID,
    data: CaseCreate,
) -> Case:
    case = Case(
        student_id=student_id,
        title=data.title,
        description=data.description,
        case_type=data.case_type,
        priority=data.priority,
        deadline=data.deadline,
        status="active",
    )

    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def list_cases(
    db: Session,
    student_id: UUID,
) -> list[Case]:
    statement = (
        select(Case)
        .where(Case.student_id == student_id)
        .order_by(Case.created_at.desc())
    )
    return list(db.scalars(statement).all())


def get_case(
    db: Session,
    student_id: UUID,
    case_id: UUID,
) -> Case | None:
    statement = select(Case).where(
        Case.id == case_id,
        Case.student_id == student_id,
    )
    return db.scalars(statement).first()