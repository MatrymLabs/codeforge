"""add the bans table (moderation: a banned character is refused at the login gate)

Revision ID: a7d3c9f1b4e2
Revises: f6a2d9b3e8c1
Create Date: 2026-07-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7d3c9f1b4e2"  # pragma: allowlist secret -- an Alembic revision id, not a secret
down_revision: str | Sequence[str] | None = "f6a2d9b3e8c1"  # pragma: allowlist secret -- Alembic id
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: one row per banned character, keyed by name for a fast login-gate check."""
    op.create_table(
        "bans",
        sa.Column("name", sa.String(), primary_key=True),
        sa.Column("reason", sa.String(), nullable=False, server_default=""),
        sa.Column("moderator", sa.String(), nullable=False, server_default=""),
        sa.Column("created_utc", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("bans")
