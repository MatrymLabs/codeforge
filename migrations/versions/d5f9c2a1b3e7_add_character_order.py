"""add characters.order (the sworn Order / guild-allegiance)

Revision ID: d5f9c2a1b3e7
Revises: c3e8b1a2f5d4
Create Date: 2026-07-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5f9c2a1b3e7"  # pragma: allowlist secret -- an Alembic revision id, not a secret
down_revision: str | Sequence[str] | None = "c3e8b1a2f5d4"  # pragma: allowlist secret -- Alembic id
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Column is "sworn_order" (ORDER is a SQL reserved word); the ORM attribute is `order`.
    op.add_column(
        "characters",
        sa.Column("sworn_order", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("characters", "sworn_order")
