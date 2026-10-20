"""Create opportunities table.

Revision ID: b12a4c6d8e90
Revises: 933a3064623c
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b12a4c6d8e90"
down_revision: Union[str, Sequence[str], None] = "933a3064623c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("source_id", sa.String(500), nullable=True),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("organization", sa.String(250), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("application_url", sa.String(2000), nullable=True),
        sa.Column("location", sa.String(250), nullable=True),
        sa.Column("opportunity_type", sa.String(80), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), server_default="discovered", nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=True),
        sa.Column("match_rationale", sa.Text(), nullable=True),
        sa.Column(
            "missing_requirements",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "source_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('gmail', 'external', 'manual')",
            name="ck_opportunities_source",
        ),
        sa.CheckConstraint(
            "status IN ('discovered', 'saved', 'applied', 'dismissed', 'expired')",
            name="ck_opportunities_status",
        ),
        sa.CheckConstraint(
            "match_score IS NULL OR (match_score >= 0 AND match_score <= 100)",
            name="ck_opportunities_match_score",
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "student_id", "source", "source_id",
            name="uq_opportunities_student_source_item",
        ),
    )
    op.create_index(
        "ix_opportunities_student_status", "opportunities",
        ["student_id", "status"], unique=False,
    )
    op.create_index(
        "ix_opportunities_student_deadline", "opportunities",
        ["student_id", "deadline"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_opportunities_student_deadline", table_name="opportunities")
    op.drop_index("ix_opportunities_student_status", table_name="opportunities")
    op.drop_table("opportunities")
