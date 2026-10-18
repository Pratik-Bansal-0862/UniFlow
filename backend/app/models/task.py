
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    and_,
    func,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.core.database import Base


class Task(Base):
    __tablename__ = "tasks"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'cancelled')",
            name="ck_tasks_status",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'urgent')",
            name="ck_tasks_priority",
        ),
        Index("ix_tasks_student_status", "student_id", "status"),
        Index("ix_tasks_student_due_date", "student_id", "due_date"),
        ForeignKeyConstraint(
            ["case_id", "student_id"],
            ["cases.id", "cases.student_id"],
            name="fk_tasks_case_student",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        default="medium",
        nullable=False,
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    student: Mapped["Student"] = relationship(
        back_populates="tasks",
        foreign_keys=[student_id],
    )
    case: Mapped["Case"] = relationship(
        back_populates="tasks",
        primaryjoin="and_(Task.case_id == Case.id, Task.student_id == Case.student_id)",
        foreign_keys="Task.case_id",
    )
