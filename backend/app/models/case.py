
import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    and_,
    func,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.core.database import Base


class Case(Base):
    __tablename__ = "cases"

    __table_args__ = (
        UniqueConstraint("id", "student_id", name="uq_cases_id_student_id"),
        CheckConstraint(
            "status IN ('active', 'in_progress', 'completed', 'cancelled', 'archived')",
            name="ck_cases_status",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'urgent')",
            name="ck_cases_priority",
        ),
        Index("ix_cases_student_status", "student_id", "status"),
        Index("ix_cases_student_deadline", "student_id", "deadline"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    case_type: Mapped[str] = mapped_column(
        String(50),
        default="general",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default="active",
        nullable=False,
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        default="medium",
        nullable=False,
    )
    deadline: Mapped[date | None] = mapped_column(Date)
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
        back_populates="cases",
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        primaryjoin="and_(Case.id == foreign(Task.case_id), Case.student_id == Task.student_id)",
    )
