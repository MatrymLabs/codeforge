"""CARD: membership -- which account owns a character, behind a storage PORT.

Account membership IS the character row's `account` column (the accounts card's law). This is the
domain side of reading and writing that link without the framework: a narrow `MembershipStore` PORT
(account_of / set_account / retire_v1_and_set_account / has_owner) and a pure in-memory adapter. The
SQL adapter is membership_sql. Extracting this seals the last CharacterRow access out of the
account/auth domain, so accounts.py becomes framework-free; a character's gameplay columns stay with
characters.py (a larger seam, not this batch). See docs/persistence_ports.md.

The module imports only typing, so it stays engine-free on the hot `import forge` path (EXP-003);
the SQLAlchemy adapter is reached only through the lazily-loaded membership_sql.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class MembershipStore(Protocol):
    """The persistence boundary for account membership: who owns a character, and the owner check.
    Any adapter (SQL, in-memory) satisfies this narrow contract; the domain depends on it, not on a
    framework."""

    def account_of(self, char: str) -> str | None:
        """The account that owns a character, or None if no such character exists."""
        ...

    def set_account(self, char: str, account: str) -> bool:
        """Point a character at an account. False if no such character exists."""
        ...

    def retire_v1_and_set_account(self, char: str, account: str) -> None:
        """Move a character onto a new account and retire its v1 per-character auth. The caller has
        confirmed the character exists."""
        ...

    def has_owner(self, account: str) -> bool:
        """True if any character on the account holds the owner rank."""
        ...


class InMemoryMembershipStore:
    """A dict-backed MembershipStore. Seed it with the characters that exist (name -> (account,
    rank)); dependency-free and deterministic, for the contract tests and a save-less world."""

    def __init__(self, seed: dict[str, tuple[str, str]] | None = None) -> None:
        # char -> {"account": str, "rank": str}
        self._chars: dict[str, dict[str, str]] = {
            name: {"account": account, "rank": rank}
            for name, (account, rank) in (seed or {}).items()
        }

    def account_of(self, char: str) -> str | None:
        record = self._chars.get(char)
        return None if record is None else record["account"]

    def set_account(self, char: str, account: str) -> bool:
        record = self._chars.get(char)
        if record is None:
            return False
        record["account"] = account
        return True

    def retire_v1_and_set_account(self, char: str, account: str) -> None:
        record = self._chars.get(char)
        if record is not None:
            record["account"] = account

    def has_owner(self, account: str) -> bool:
        return any(r["rank"] == "owner" and r["account"] == account for r in self._chars.values())
