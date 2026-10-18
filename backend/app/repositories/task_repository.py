from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate


def create_task(
    db: Session,
    student_id: UUID,
    case_id: UUID,
    data: TaskCreate,
) -> Task | None:
    case = db.scalars(
        select(Case).where(
            Case.id == case_id,
            Case.student_id == student_id,
        )
    ).first()

    if case is None:
        return None

    task = Task(
        student_id=student_id,
        case_id=case_id,
        title=data.title,
        description=data.description,
        priority=data.priority,
        due_at=data.due_at,
        status="pending",
    )

    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(
    db: Session,
    student_id: UUID,
    task_id: UUID,
    data: TaskUpdate,
) -> Task | None:
    task = db.scalars(
        select(Task).where(
            Task.id == task_id,
            Task.student_id == student_id,
        )
    ).first()

    if task is None:
        return None

    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(task, field, value)

    if "status" in changes:
        if task.status == "completed":
            task.completed_at = datetime.now(UTC)
        else:
            task.completed_at = None

    db.commit()
    db.refresh(task)
    return task