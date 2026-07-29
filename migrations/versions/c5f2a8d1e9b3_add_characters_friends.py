"""add characters.friends (a hero's personal friends list, comma-joined labels)

Revision ID: c5f2a8d1e9b3
Revises: a3e7c9b1d5f4
Create Date: 2026-07-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5f2a8d1e9b3"  # pragma: allowlist secret -- an Alembic revision id, not a secret
down_revision: str | Sequence[str] | None = "a3e7c9b1d5f4"  # pragma: allowlist secret -- Alembic id
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: one additive gameplay column for the friends list."""
    op.add_column(
        "characters",
        sa.Column("friends", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("characters", "friends")
