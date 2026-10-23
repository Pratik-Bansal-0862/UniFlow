"""Create persistent student profiles.

Revision ID: c34d5e6f7890
Revises: b12a4c6d8e90
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c34d5e6f7890"
down_revision: Union[str, Sequence[str], None] = "b12a4c6d8e90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_profile_data",
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column(
            "profile",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "sources",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(40),
            server_default="not_generated",
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("student_id"),
    )


def downgrade() -> None:
    op.drop_table("student_profile_data")