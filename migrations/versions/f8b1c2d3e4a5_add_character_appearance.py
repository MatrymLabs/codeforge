"""add characters.appearance (player presentation choices)"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8b1c2d3e4a5"  # pragma: allowlist secret -- Alembic revision id
down_revision: tuple[str, str] = (
    "e2f4a6b8c0d1",
    "f6a2d9b3e8c1",
)  # pragma: allowlist secret -- merge the pre-existing persistence heads
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "characters",
        sa.Column("appearance", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("characters", "appearance")
