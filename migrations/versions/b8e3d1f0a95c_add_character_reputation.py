"""add characters.reputation (standing with the Orders)

Revision ID: b8e3d1f0a95c
Revises: f4a9c1e0b7d2
Create Date: 2026-07-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e3d1f0a95c"  # pragma: allowlist secret -- an Alembic revision id, not a secret
down_revision: str | Sequence[str] | None = "f4a9c1e0b7d2"  # pragma: allowlist secret -- Alembic id
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "characters",
        sa.Column("reputation", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("characters", "reputation")
