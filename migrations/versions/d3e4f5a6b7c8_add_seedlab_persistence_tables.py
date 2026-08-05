"""add durable SeedLab model, run, artifact, and manifest evidence tables

Revision ID: d3e4f5a6b7c8
Revises: c1d2e3f4a5b6
Create Date: 2026-08-05 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "seed_models",
        sa.Column("seed_id", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("model_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("seed_id", "model_id"),
    )
    op.create_table(
        "seed_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("seed_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("run_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_seed_runs_seed_id", "seed_runs", ["seed_id"])
    op.create_index("ix_seed_runs_kind", "seed_runs", ["kind"])
    op.create_table(
        "seed_artifacts",
        sa.Column("seed_id", sa.String(), nullable=False),
        sa.Column("artifact_id", sa.String(), nullable=False),
        sa.Column("artifact_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("seed_id", "artifact_id"),
    )
    op.create_table(
        "seed_manifest_evidence",
        sa.Column("seed_id", sa.String(), nullable=False),
        sa.Column("evidence_id", sa.String(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("seed_id", "evidence_id"),
    )


def downgrade() -> None:
    op.drop_table("seed_manifest_evidence")
    op.drop_table("seed_artifacts")
    op.drop_index("ix_seed_runs_kind", table_name="seed_runs")
    op.drop_index("ix_seed_runs_seed_id", table_name="seed_runs")
    op.drop_table("seed_runs")
    op.drop_table("seed_models")
