"""add the durable transactional outbox table"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f3b7c1d2e4a"
down_revision: str | Sequence[str] | None = "b8e4f1c2d3a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbox",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Float(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_topic", "outbox", ["topic"])
    op.create_index("ix_outbox_status", "outbox", ["status"])


def downgrade() -> None:
    op.drop_index("ix_outbox_status", table_name="outbox")
    op.drop_index("ix_outbox_topic", table_name="outbox")
    op.drop_table("outbox")
