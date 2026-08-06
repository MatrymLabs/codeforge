"""add durable Seed connector lifecycle records

Revision ID: e2f4a6b8c0d1
Revises: d3e4f5a6b7c8
Create Date: 2026-08-05 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision: str = "e2f4a6b8c0d1"
down_revision: str | None = "d3e4f5a6b7c8"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "seed_connectors",
        sa.Column("seed_id", sa.String(), nullable=False),
        sa.Column("registration_id", sa.String(), nullable=False),
        sa.Column("registration_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("seed_id", "registration_id"),
    )


def downgrade() -> None:
    op.drop_table("seed_connectors")
