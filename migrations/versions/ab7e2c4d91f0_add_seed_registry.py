"""add generic Seed registry

Revision ID: ab7e2c4d91f0
Revises: 9f3b7c1d2e4a
Create Date: 2026-08-05 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision: str = "ab7e2c4d91f0"
down_revision: str | None = "9f3b7c1d2e4a"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "seed_registry",
        sa.Column("seed_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("owner", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("product_type", sa.String(), nullable=False),
        sa.Column("domain_modules", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.String(), nullable=False),
        sa.Column("stopped_at", sa.String(), nullable=False),
        sa.Column("audit", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "status IN ('created', 'running', 'stopped', 'archived')",
            name="ck_seed_registry_status",
        ),
        sa.PrimaryKeyConstraint("seed_id"),
    )
    op.create_index("ix_seed_registry_owner", "seed_registry", ["owner"])
    op.create_index("ix_seed_registry_status", "seed_registry", ["status"])


def downgrade() -> None:
    op.drop_index("ix_seed_registry_status", table_name="seed_registry")
    op.drop_index("ix_seed_registry_owner", table_name="seed_registry")
    op.drop_table("seed_registry")
