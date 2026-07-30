"""add the character lockouts column (daily boss/daily bonus cap: endgame is a return, not a grind)

Revision ID: b8e4f1c2d3a9
Revises: a7d3c9f1b4e2
Create Date: 2026-07-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e4f1c2d3a9"  # pragma: allowlist secret -- an Alembic revision id, not a secret
down_revision: str | Sequence[str] | None = "a7d3c9f1b4e2"  # pragma: allowlist secret -- Alembic id
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: a JSON lockout ledger on each character, '' for a new hero."""
    op.add_column(
        "characters",
        sa.Column("lockouts", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("characters", "lockouts")
