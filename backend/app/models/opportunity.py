import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        CheckConstraint(
            "source IN ('gmail', 'external', 'manual')",
            name="ck_opportunities_source",
        ),
        CheckConstraint(
            "status IN ('discovered', 'saved', 'applied', 'dismissed', 'expired')",
            name="ck_opportunities_status",
        ),
        CheckConstraint(
            "match_score IS NULL OR (match_score >= 0 AND match_score <= 100)",
            name="ck_opportunities_match_score",
        ),
        UniqueConstraint(
            "student_id", "source", "source_id",
            name="uq_opportunities_student_source_item",
        ),
        Index("ix_opportunities_student_status", "student_id", "status"),
        Index("ix_opportunities_student_deadline", "student_id", "deadline"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(250))
    description: Mapped[str | None] = mapped_column(Text)
    application_url: Mapped[str | None] = mapped_column(String(2000))
    location: Mapped[str | None] = mapped_column(String(250))
    opportunity_type: Mapped[str | None] = mapped_column(String(80))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(20), default="discovered", nullable=False
    )
    match_score: Mapped[int | None] = mapped_column()
    match_rationale: Mapped[str | None] = mapped_column(Text)
    missing_requirements: Mapped[list] = mapped_column(
        JSONB, default=list, nullable=False
    )
    source_metadata: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )
