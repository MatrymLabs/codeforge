"""add characters.checksum (durable record integrity metadata)

Revision ID: f8a9c0d1e2f3
Revises: b8e4f1c2d3a9
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8a9c0d1e2f3"  # pragma: allowlist secret -- an Alembic revision id, not a secret
down_revision: str | Sequence[str] | None = "b8e4f1c2d3a9"  # pragma: allowlist secret -- Alembic id
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add blank legacy integrity metadata without rewriting any character row."""
    op.add_column(
        "characters",
        sa.Column("checksum", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Remove the additive checksum column."""
    op.drop_column("characters", "checksum")
