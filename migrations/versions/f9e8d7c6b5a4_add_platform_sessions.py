"""add durable platform session identity records

Revision ID: f9e8d7c6b5a4
Revises: d6a7b8c9e0f1
Create Date: 2026-08-08 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision: str = "f9e8d7c6b5a4"
down_revision: str | None = "d6a7b8c9e0f1"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "platform_sessions",
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("identity_json", sa.Text(), nullable=False),
        sa.Column("state", sa.String(), nullable=False, server_default="active"),
        sa.Column("updated_at", sa.String(), nullable=False, server_default=""),
        sa.Column("invalidated_by", sa.String(), nullable=False, server_default=""),
        sa.Column("invalidation_reason", sa.String(), nullable=False, server_default=""),
        sa.CheckConstraint(
            "state IN ('active', 'invalidated')",
            name="ck_platform_sessions_state",
        ),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("ix_platform_sessions_state", "platform_sessions", ["state"])


def downgrade() -> None:
    op.drop_index("ix_platform_sessions_state", table_name="platform_sessions")
    op.drop_table("platform_sessions")
