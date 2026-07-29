"""add characters.guild + guild_rank (the player-guild a hero belongs to)

Revision ID: e7a3c1b5f2d8
Revises: b8e3d1f0a95c
Create Date: 2026-07-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7a3c1b5f2d8"  # pragma: allowlist secret -- an Alembic revision id, not a secret
down_revision: str | Sequence[str] | None = "b8e3d1f0a95c"  # pragma: allowlist secret -- Alembic id
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: two additive gameplay columns for guild membership."""
    op.add_column(
        "characters",
        sa.Column("guild", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "characters",
        sa.Column("guild_rank", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("characters", "guild_rank")
    op.drop_column("characters", "guild")
