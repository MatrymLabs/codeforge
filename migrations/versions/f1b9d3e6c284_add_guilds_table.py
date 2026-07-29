"""add the guilds table (a guild's shared treasury)

Revision ID: f1b9d3e6c284
Revises: e7a3c1b5f2d8
Create Date: 2026-07-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1b9d3e6c284"  # pragma: allowlist secret -- an Alembic revision id, not a secret
down_revision: str | Sequence[str] | None = "e7a3c1b5f2d8"  # pragma: allowlist secret -- Alembic id
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: one row per guild holding its guild-level state (the treasury)."""
    op.create_table(
        "guilds",
        sa.Column("name", sa.String(), primary_key=True),
        sa.Column("coins", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("guilds")
