"""CARD: accounts -- names become logins with real password hashing, over a storage PORT.

One account = one human = one password (salted pbkdf2-sha256, 600k
iterations, constant-time compare). Characters are masks worn by
their account: membership IS the character row's account column.
Login refusals stay generic -- no enumeration gifts.

The crypto and its timing defenses live here and never cross a boundary. This module touches no ORM
row directly: account credential persistence lives behind the `AccountCredentialStore` PORT (adapter
accounts_sql), and account membership -- who owns a character, the owner-rank query, v1-auth
retirement -- lives behind the `MembershipStore` PORT (adapter membership_sql). See
docs/persistence_ports.md.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from kernel.world.characters import load_character, put_record
from kernel.world.membership import MembershipStore

# kernel.world.db is imported lazily inside the functions that touch persistence (below), so a
# DB-free `import forge` (play/command sessions, benchmarks, most tests) never pays the
# ~400ms SQLAlchemy import. The cost shifts to the first real DB touch (e.g. first login),
# measured, not hidden. kernel.world.db owns ORM rows; this only defers WHEN they load. (EXP-003)

_ITERATIONS = 600_000
MIN_PASSWORD_LEN = 8  # NIST SP 800-63B floor: length beats composition rules
_TOO_SHORT = f"Passwords need at least {MIN_PASSWORD_LEN} characters."
_ACCOUNT_MISMATCH_MSG = "That account exists and this is not its password."


def _hash_secret(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS).hex()


def _secret_matches(password: str, salt_hex: str, expected: str) -> bool:
    digest = _hash_secret(password, bytes.fromhex(salt_hex))
    return secrets.compare_digest(digest, expected)


_DECOY_SALT = b"\x00" * 16  # a fixed, non-secret salt, used only to spend time


def _burn_hash(password: str) -> None:
    """Spend a real pbkdf2's worth of time against a decoy, then discard it. When an account or
    character does NOT exist, an auth check calls this before returning False, so its response
    takes the same ~pbkdf2 time as a real check. Without it, a missing name returns ~250,000x
    faster than a real one -- the whole account roster is enumerable by timing the response. The
    decoy is never compared to a real secret; it exists only to level the timing."""
    _hash_secret(password, _DECOY_SALT)


# ------------------------------------------- the account-credential storage PORT
# All AccountRow persistence lives behind this narrow contract. The crypto and timing defenses above
# NEVER cross it: an adapter deals in hex strings, never passwords, and does no hashing. This is the
# assimilation pattern (docs/persistence_ports.md) applied to auth -- the framework (SQLAlchemy) is
# kept behind a boundary so the security policy is read, tested, and reused without it. Character
# membership rows (adopt, the character half of login/migrate, the owner query) are a separate seam,
# the next boundary to extract.


@dataclass(frozen=True)
class AccountSecret:
    """An account's stored credential: salt and pbkdf2 digest, both hex. Never the password."""

    salt_hex: str
    hash_hex: str


@runtime_checkable
class AccountCredentialStore(Protocol):
    """The persistence boundary for account credentials: find an account's stored salt+hash, create
    a new account, rotate an existing one. Deals in hex strings, never passwords -- all crypto and
    timing defenses stay in this module. Any backend (SQL, in-memory) satisfies this narrow
    contract; the domain depends on it, not on a framework."""

    def find(self, account: str) -> AccountSecret | None:
        """The stored salt+hash for an account, or None if it does not exist."""
        ...

    def create(self, account: str, salt_hex: str, hash_hex: str) -> None:
        """Insert a new account (the caller has confirmed it does not exist)."""
        ...

    def set_secret(self, account: str, salt_hex: str, hash_hex: str) -> None:
        """Rotate an existing account's salt+hash; a missing account is a no-op."""
        ...


class InMemoryAccountCredentialStore:
    """A dict-backed AccountCredentialStore: dependency-free, deterministic. Drives the contract
    tests and is a ready reuse for a save-less or test world. Holds hex strings, never passwords."""

    def __init__(self) -> None:
        self._accounts: dict[str, AccountSecret] = {}

    def find(self, account: str) -> AccountSecret | None:
        return self._accounts.get(account)

    def create(self, account: str, salt_hex: str, hash_hex: str) -> None:
        self._accounts[account] = AccountSecret(salt_hex, hash_hex)

    def set_secret(self, account: str, salt_hex: str, hash_hex: str) -> None:
        if account in self._accounts:
            self._accounts[account] = AccountSecret(salt_hex, hash_hex)


def _default_store() -> AccountCredentialStore:
    """The default backend: the SQL adapter, imported lazily so this module stays engine-free at
    import time (EXP-003 -- the crypto helpers ride the hot `import forge` path)."""
    from kernel.world.accounts_sql import SqlAccountCredentialStore

    return SqlAccountCredentialStore()


def _default_membership() -> MembershipStore:
    """The default membership backend: the SQL adapter, imported lazily (EXP-003). Account-to-
    character linkage lives behind its own port so this module touches no ORM row directly."""
    from kernel.world.membership_sql import SqlMembershipStore

    return SqlMembershipStore()


# --------------------------------------------------- legacy v1: per-character
def has_password(casefile: dict[str, Any]) -> bool:
    return bool(casefile.get("auth"))


def set_password(name: str, password: str) -> str:
    """Attach v1 protection to a character (guest-name path)."""
    if len(password) < MIN_PASSWORD_LEN:
        return _TOO_SHORT
    casefile = load_character(name)
    if casefile is None:
        return f"No saved character named {name}."
    salt = secrets.token_bytes(16)
    casefile["auth"] = {"salt": salt.hex(), "hash": _hash_secret(password, salt)}
    put_record(name, casefile)
    return "This name is now protected. Guard your secret."


def verify_password(name: str, password: str) -> bool:
    casefile = load_character(name)
    if casefile is None or not has_password(casefile):
        _burn_hash(password)  # constant-time: an unknown name costs the same as a real check
        return False
    return _secret_matches(password, casefile["auth"]["salt"], casefile["auth"]["hash"])


# ------------------------------------------------------------------ accounts
def parse_handle(handle: str) -> tuple[str, str] | None:
    """'matrym@matlabs' -> ('matrym', 'matlabs'); None if malformed."""
    char, at, account = handle.partition("@")
    if not at or not char or not account:
        return None
    return (char, account)


def register(
    char: str, account: str, password: str, store: AccountCredentialStore | None = None
) -> str:
    """Create or extend an account with a new character. Returns '' on
    success; the engine tick finishes the character's birth."""
    if len(password) < MIN_PASSWORD_LEN:
        return _TOO_SHORT
    if load_character(char) is not None:
        return f"A character named {char} already exists."
    store = store or _default_store()
    secret = store.find(account)
    if secret is None:
        salt = secrets.token_bytes(16)
        store.create(account, salt.hex(), _hash_secret(password, salt))
    elif not _secret_matches(password, secret.salt_hex, secret.hash_hex):
        return _ACCOUNT_MISMATCH_MSG
    return ""


def password_fixable(register_response: str) -> bool:
    """True when a `register` result is one the visitor can fix by simply typing a
    DIFFERENT password (too short, or the wrong password for an account that already
    exists) -- as opposed to a handle problem (bad or taken name) a new password can
    never solve. The front desks use this to re-prompt the password in place instead
    of abandoning the registration."""
    return register_response in (_TOO_SHORT, _ACCOUNT_MISMATCH_MSG)


def inspect_login(
    char: str,
    account: str,
    password: str,
    store: AccountCredentialStore | None = None,
    membership: MembershipStore | None = None,
) -> bool:
    """One generic verdict: account exists, password matches, and the
    character belongs to that account. Which part failed is a secret."""
    store = store or _default_store()
    secret = store.find(account)
    if secret is None:
        _burn_hash(password)  # constant-time: an unknown account costs the same as a real check
        return False
    if not _secret_matches(password, secret.salt_hex, secret.hash_hex):
        return False
    seat = (membership or _default_membership()).account_of(char)
    return seat is not None and seat == account


def verify_account(
    account: str, password: str, store: AccountCredentialStore | None = None
) -> bool:
    """Verify an account credential for the account-level character selector.

    The result is deliberately generic: an unknown account burns the same password-hash work as a
    known account, so the selector cannot become an account-enumeration oracle.
    """
    store = store or _default_store()
    secret = store.find(account)
    if secret is None:
        _burn_hash(password)
        return False
    return _secret_matches(password, secret.salt_hex, secret.hash_hex)


def adopt(char: str, account: str, membership: MembershipStore | None = None) -> str:
    """Attach an existing character to an account (migration/admin)."""
    if not (membership or _default_membership()).set_account(char, account):
        return f"No saved character named {char}."
    return f"{char} now belongs to {account}."


def rotate_account_secret(
    account: str, password: str, store: AccountCredentialStore | None = None
) -> str:
    """Rotate an account's secret (the codeforge passwd verb)."""
    if len(password) < MIN_PASSWORD_LEN:
        return _TOO_SHORT
    store = store or _default_store()
    if store.find(account) is None:
        return f"No account named {account}."
    salt = secrets.token_bytes(16)
    store.set_secret(account, salt.hex(), _hash_secret(password, salt))
    return f"Password rotated for {account}."


def reforge_secret(
    account: str, old: str, new: str, store: AccountCredentialStore | None = None
) -> str:
    """Self-service rotation: prove the current secret, then set a new
    one. Returns '' on success or the reason it was refused. The old
    password is verified constant-time; the new one is salted afresh.
    Refusal on a bad old password stays generic -- no enumeration."""
    if len(new) < MIN_PASSWORD_LEN:
        return _TOO_SHORT
    store = store or _default_store()
    secret = store.find(account)
    if secret is None or not _secret_matches(old, secret.salt_hex, secret.hash_hex):
        return "That is not your current password."
    salt = secrets.token_bytes(16)
    store.set_secret(account, salt.hex(), _hash_secret(new, salt))
    return ""


def migrate(
    char: str,
    account: str,
    store: AccountCredentialStore | None = None,
    membership: MembershipStore | None = None,
) -> str:
    """Move a v1 character-password onto a NEW account."""
    casefile = load_character(char)
    if casefile is None:
        return f"No saved character named {char}."
    if not casefile.get("auth"):
        return f"{char} has no password to migrate. Set one in-game first: password <secret>"
    store = store or _default_store()
    if store.find(account) is not None:
        return f"Account {account} already exists; migration only creates new accounts."
    auth = casefile["auth"]
    store.create(account, auth["salt"], auth["hash"])
    (membership or _default_membership()).retire_v1_and_set_account(char, account)
    return f"{char}@{account} is ready. Log in with the same password."


def import_legacy_json(
    store: AccountCredentialStore | None = None, membership: MembershipStore | None = None
) -> str:
    """One-time importer: characters.json + accounts.json -> SQLite."""
    import json
    from pathlib import Path

    moved = []
    chars = Path("characters.json")
    if chars.exists():
        for name, casefile in json.loads(chars.read_text(encoding="utf-8")).items():
            put_record(name, casefile)
            moved.append(name)
    accts = Path("accounts.json")
    if accts.exists():
        store = store or _default_store()
        membership = membership or _default_membership()
        for name, entry in json.loads(accts.read_text(encoding="utf-8")).items():
            if store.find(name) is None and entry.get("auth"):
                store.create(name, entry["auth"]["salt"], entry["auth"]["hash"])
            for member in entry.get("characters", []):
                membership.set_account(member, name)  # a no-op if the member has no record
    if not moved and not accts.exists():
        return "No legacy JSON found; nothing to import."
    return f"Imported {len(moved)} character(s) into codeforge.db. Legacy files left untouched."


def account_password_ok(
    account: str, password: str, store: AccountCredentialStore | None = None
) -> bool:
    """Bare account credential check (no character required) -- the
    HTTP admin surface authenticates accounts, not masks."""
    store = store or _default_store()
    secret = store.find(account)
    if secret is None:
        _burn_hash(password)  # constant-time: an unknown account costs the same as a real check
        return False
    return _secret_matches(password, secret.salt_hex, secret.hash_hex)


def account_has_owner(account: str, membership: MembershipStore | None = None) -> bool:
    """True if any character on this account holds the owner rank."""
    return (membership or _default_membership()).has_owner(account)
