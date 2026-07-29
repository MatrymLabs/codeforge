"""add the loose_items table (a hero's bag survives logout: Keystone A)

Revision ID: d4b8f1a2c6e9
Revises: c5f2a8d1e9b3
Create Date: 2026-07-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4b8f1a2c6e9"  # pragma: allowlist secret -- an Alembic revision id, not a secret
down_revision: str | Sequence[str] | None = "c5f2a8d1e9b3"  # pragma: allowlist secret -- Alembic id
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: one row per loose (non-worn) item a hero carries, indexed by owner so a whole
    bag loads in one query."""
    op.create_table(
        "loose_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner", sa.String(), nullable=False, index=True),
        sa.Column("prototype", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("mods", sa.String(), nullable=False, server_default="{}"),
        sa.Column("rarity", sa.String(), nullable=False, server_default="common"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("loose_items")
