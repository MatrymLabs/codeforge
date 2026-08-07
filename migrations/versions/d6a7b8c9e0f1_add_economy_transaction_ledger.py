"""add idempotent economy transactions and currency ledger

Revision ID: d6a7b8c9e0f1
Revises: f8b1c2d3e4a5
Create Date: 2026-08-06 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision: str = "d6a7b8c9e0f1"
down_revision: str | None = "f8b1c2d3e4a5"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "economy_transactions",
        sa.Column("transaction_id", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("request_hash", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("destination", sa.String(), nullable=False),
        sa.Column("currency_amount", sa.Integer(), nullable=False),
        sa.Column("item_ids", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("transaction_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_economy_transaction_idempotency"),
    )
    op.create_index(
        "ix_economy_transactions_idempotency_key",
        "economy_transactions",
        ["idempotency_key"],
    )
    op.create_index("ix_economy_transactions_actor", "economy_transactions", ["actor"])
    op.create_table(
        "currency_ledger",
        sa.Column("entry_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("transaction_id", sa.String(), nullable=False),
        sa.Column("account", sa.String(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("destination", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("entry_id"),
    )
    op.create_index("ix_currency_ledger_transaction_id", "currency_ledger", ["transaction_id"])
    op.create_index("ix_currency_ledger_account", "currency_ledger", ["account"])


def downgrade() -> None:
    op.drop_index("ix_currency_ledger_account", table_name="currency_ledger")
    op.drop_index("ix_currency_ledger_transaction_id", table_name="currency_ledger")
    op.drop_table("currency_ledger")
    op.drop_index("ix_economy_transactions_actor", table_name="economy_transactions")
    op.drop_index("ix_economy_transactions_idempotency_key", table_name="economy_transactions")
    op.drop_table("economy_transactions")
