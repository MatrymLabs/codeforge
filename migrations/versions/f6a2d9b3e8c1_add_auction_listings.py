"""add the auction_listings table (the marketplace: escrowed item + price + expiry)

Revision ID: f6a2d9b3e8c1
Revises: e1c9a4d7f2b6
Create Date: 2026-07-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a2d9b3e8c1"  # pragma: allowlist secret -- an Alembic revision id, not a secret
down_revision: str | Sequence[str] | None = "e1c9a4d7f2b6"  # pragma: allowlist secret -- Alembic id
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: one row per active listing, indexed by seller and by expiry (the sweep reads
    expiry to close lapsed auctions)."""
    op.create_table(
        "auction_listings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("seller", sa.String(), nullable=False, index=True),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("expiry_beat", sa.Integer(), nullable=False, index=True),
        sa.Column("prototype", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("mods", sa.String(), nullable=False, server_default="{}"),
        sa.Column("rarity", sa.String(), nullable=False, server_default="common"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("auction_listings")
