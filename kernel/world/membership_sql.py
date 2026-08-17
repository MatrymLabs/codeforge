"""CARD: membership_sql -- the SQLAlchemy adapter for the MembershipStore port.

The framework kept behind the membership boundary. `membership` (the domain) names the narrow
`MembershipStore` port; this adapter is the only place the account/owner/v1-auth columns of the
`characters` table are read or written for auth purposes. Column-scoped, per the merge-save law:
set_account touches only the account column; retire_v1_and_set_account additionally nulls the v1
per-character auth columns; neither touches a character's gameplay fields (those stay in chars).

SQLAlchemy and kernel.world.db are imported LAZILY inside methods, so importing this adapter (and
so the domain modules that lazily reach it) never triggers the ~400ms SQLAlchemy import on the hot
`import forge` path (EXP-003).
"""

from __future__ import annotations


class SqlMembershipStore:
    """A MembershipStore backed by the account/rank columns of the SQL `characters` table."""

    def account_of(self, char: str) -> str | None:
        """The account owning a character, or None if the character has no row."""
        from kernel.world.db import CharacterRow, open_archive_session

        with open_archive_session() as db:
            row = db.get(CharacterRow, char)
            return None if row is None else row.account

    def set_account(self, char: str, account: str) -> bool:
        """Point a character at an account. False if the character has no row."""
        from kernel.world.db import CharacterRow, open_archive_session

        with open_archive_session() as db:
            row = db.get(CharacterRow, char)
            if row is None:
                return False
            row.account = account
            db.commit()
            return True

    def retire_v1_and_set_account(self, char: str, account: str) -> None:
        """Move a character onto a new account and null its v1 per-character auth columns. The
        caller has confirmed the character exists."""
        from kernel.world.db import CharacterRow, open_archive_session

        with open_archive_session() as db:
            row = db.get(CharacterRow, char)
            assert row is not None
            row.account = account
            row.auth_salt = None
            row.auth_hash = None
            db.commit()

    def has_owner(self, account: str) -> bool:
        """True if any character on the account holds the owner rank."""
        from sqlalchemy import select

        from kernel.world.db import CharacterRow, open_archive_session

        with open_archive_session() as db:
            rows = db.scalars(select(CharacterRow).where(CharacterRow.account == account))
            return any(row.rank == "owner" for row in rows)
