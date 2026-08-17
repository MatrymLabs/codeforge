"""CARD: accounts_sql -- the SQLAlchemy adapter for the AccountCredentialStore port.

The framework kept behind the auth boundary. `accounts` (the domain) owns all the credential policy
-- salted pbkdf2, constant-time compare, the missing-principal timing decoy, the generic refusals --
and never touches an ORM row for it. This adapter is the only place that reads or writes the
`accounts` table: find an account's stored salt+hash, create a new one, rotate an existing one. It
deals in hex strings, never passwords, and performs no crypto -- the security decisions stay in the
domain, provable by the timing-spy tests that hook `accounts._hash_secret`.

SQLAlchemy and kernel.world.db are imported LAZILY inside methods, so importing this adapter (and
so the domain module that lazily reaches it) never triggers the ~400ms SQLAlchemy import on the hot
`import forge` path (EXP-003).

Scope note: this seals the `accounts`-table (AccountRow) access only. Character-membership row
access (the account column on a character, the owner-rank query, the v1 per-character auth columns)
is a separate seam -- the next boundary the campaign will extract (see docs/persistence_ports.md).
"""

from __future__ import annotations

from kernel.world.accounts import AccountSecret


class SqlAccountCredentialStore:
    """An AccountCredentialStore backed by the SQL `accounts` table (one row per account)."""

    def find(self, account: str) -> AccountSecret | None:
        """The stored salt+hash for an account, or None if no such account exists."""
        from kernel.world.db import AccountRow, open_archive_session

        with open_archive_session() as db:
            row = db.get(AccountRow, account)
            return None if row is None else AccountSecret(row.auth_salt, row.auth_hash)

    def create(self, account: str, salt_hex: str, hash_hex: str) -> None:
        """Insert a brand-new account row. The caller has already confirmed it does not exist."""
        from kernel.world.db import AccountRow, open_archive_session

        with open_archive_session() as db:
            db.add(AccountRow(name=account, auth_salt=salt_hex, auth_hash=hash_hex))
            db.commit()

    def set_secret(self, account: str, salt_hex: str, hash_hex: str) -> None:
        """Rotate an existing account's salt+hash. A missing account is a silent no-op (the caller
        has already resolved existence and its own refusal message)."""
        from kernel.world.db import AccountRow, open_archive_session

        with open_archive_session() as db:
            row = db.get(AccountRow, account)
            if row is not None:
                row.auth_salt = salt_hex
                row.auth_hash = hash_hex
                db.commit()
