"""add job_progress: per-job level, JP, and TP per character

Revision ID: 9c4d1f6ab7e2
Revises: f70a020a8288
Create Date: 2026-07-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c4d1f6ab7e2"
down_revision: str | Sequence[str] | None = "f70a020a8288"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "job_progress",
        sa.Column("character_name", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("job_level", sa.Integer(), nullable=False),
        sa.Column("jp", sa.Integer(), nullable=False),
        sa.Column("tp", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["character_name"], ["characters.name"]),
        sa.PrimaryKeyConstraint("character_name", "job_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("job_progress")
