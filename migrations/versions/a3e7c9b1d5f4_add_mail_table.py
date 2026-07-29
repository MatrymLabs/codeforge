"""add the mail table (asynchronous player-to-player letters)

Revision ID: a3e7c9b1d5f4
Revises: f1b9d3e6c284
Create Date: 2026-07-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3e7c9b1d5f4"  # pragma: allowlist secret -- an Alembic revision id, not a secret
down_revision: str | Sequence[str] | None = "f1b9d3e6c284"  # pragma: allowlist secret -- Alembic id
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: one row per delivered letter, indexed by recipient for a fast inbox read."""
    op.create_table(
        "mail",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("recipient", sa.String(), nullable=False, index=True),
        sa.Column("sender", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("sent_utc", sa.String(), nullable=False),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("mail")
