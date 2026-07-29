"""add mail item-attachment columns (a letter can carry a parcel: Phase 2)

Revision ID: e1c9a4d7f2b6
Revises: d4b8f1a2c6e9
Create Date: 2026-07-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1c9a4d7f2b6"  # pragma: allowlist secret -- an Alembic revision id, not a secret
down_revision: str | Sequence[str] | None = "d4b8f1a2c6e9"  # pragma: allowlist secret -- Alembic id
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: four columns for an optional attached item (a snapshot). An empty
    attach_proto means the letter carries no parcel."""
    op.add_column("mail", sa.Column("attach_proto", sa.String(), nullable=False, server_default=""))
    op.add_column("mail", sa.Column("attach_name", sa.String(), nullable=False, server_default=""))
    op.add_column(
        "mail", sa.Column("attach_mods", sa.String(), nullable=False, server_default="{}")
    )
    op.add_column(
        "mail", sa.Column("attach_rarity", sa.String(), nullable=False, server_default="common")
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("mail", "attach_rarity")
    op.drop_column("mail", "attach_mods")
    op.drop_column("mail", "attach_name")
    op.drop_column("mail", "attach_proto")
