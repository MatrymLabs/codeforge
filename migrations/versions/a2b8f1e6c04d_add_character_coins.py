"""add characters.coins (the purse)

Revision ID: a2b8f1e6c04d
Revises: e7a3c9d21f8b
Create Date: 2026-07-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2b8f1e6c04d"  # pragma: allowlist secret -- an Alembic revision id, not a secret
down_revision: str | Sequence[str] | None = "e7a3c9d21f8b"  # pragma: allowlist secret -- Alembic id
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "characters",
        sa.Column("coins", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("characters", "coins")
