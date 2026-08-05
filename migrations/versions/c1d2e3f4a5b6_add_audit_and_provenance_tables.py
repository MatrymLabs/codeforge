"""add durable audit and source provenance tables

Revision ID: c1d2e3f4a5b6
Revises: ab7e2c4d91f0
Create Date: 2026-08-05 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "ab7e2c4d91f0"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "seed_sources",
        sa.Column("seed_id", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("source_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("seed_id", "source_id"),
    )
    op.create_table(
        "audit_events",
        sa.Column("sequence", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("prior_hash", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("sequence"),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("seed_sources")
