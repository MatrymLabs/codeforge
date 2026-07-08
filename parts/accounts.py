"""CARD: accounts -- names become logins with real password hashing (SQL-backed).

One account = one human = one password (salted pbkdf2-sha256, 600k
iterations, constant-time compare). Characters are masks worn by
their account: membership IS the character row's account column.
Login refusals stay generic -- no enumeration gifts.
"""

import hashlib
import secrets
from typing import Any

from parts.characters import load_character, put_record
from parts.db import AccountRow, CharacterRow, get_session

_ITERATIONS = 600_000


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS).hex()


def _matches(password: str, salt_hex: str, expected: str) -> bool:
    digest = _hash(password, bytes.fromhex(salt_hex))
    return secrets.compare_digest(digest, expected)


# --------------------------------------------------- legacy v1: per-character
def has_password(record: dict[str, Any]) -> bool:
    return bool(record.get("auth"))


def set_password(name: str, password: str) -> str:
    """Attach v1 protection to a character (guest-name path)."""
    if len(password) < 4:
        return "Passwords need at least 4 characters."
    record = load_character(name)
    if record is None:
        return f"No saved character named {name}."
    salt = secrets.token_bytes(16)
    record["auth"] = {"salt": salt.hex(), "hash": _hash(password, salt)}
    put_record(name, record)
    return "This name is now protected. Guard your secret."


def verify_password(name: str, password: str) -> bool:
    record = load_character(name)
    if record is None or not has_password(record):
        return False
    return _matches(password, record["auth"]["salt"], record["auth"]["hash"])


# ------------------------------------------------------------------ accounts
def parse_handle(handle: str) -> tuple[str, str] | None:
    """'matrym@matlabs' -> ('matrym', 'matlabs'); None if malformed."""
    char, at, account = handle.partition("@")
    if not at or not char or not account:
        return None
    return (char, account)


def register(char: str, account: str, password: str) -> str:
    """Create or extend an account with a new character. Returns '' on
    success; the engine tick finishes the character's birth."""
    if len(password) < 4:
        return "Passwords need at least 4 characters."
    if load_character(char) is not None:
        return f"A character named {char} already exists."
    with get_session() as db:
        row = db.get(AccountRow, account)
        if row is None:
            salt = secrets.token_bytes(16)
            db.add(AccountRow(name=account, auth_salt=salt.hex(), auth_hash=_hash(password, salt)))
            db.commit()
        elif not _matches(password, row.auth_salt, row.auth_hash):
            return "That account exists and this is not its password."
    return ""


def login_check(char: str, account: str, password: str) -> bool:
    """One generic verdict: account exists, password matches, and the
    character belongs to that account. Which part failed is a secret."""
    with get_session() as db:
        acct = db.get(AccountRow, account)
        if acct is None or not _matches(password, acct.auth_salt, acct.auth_hash):
            return False
        row = db.get(CharacterRow, char)
        return row is not None and row.account == account


def adopt(char: str, account: str) -> str:
    """Attach an existing character to an account (migration/admin)."""
    with get_session() as db:
        row = db.get(CharacterRow, char)
        if row is None:
            return f"No saved character named {char}."
        row.account = account
        db.commit()
    return f"{char} now belongs to {account}."


def set_account_password(account: str, password: str) -> str:
    """Rotate an account's secret (the codeforge passwd verb)."""
    if len(password) < 4:
        return "Passwords need at least 4 characters."
    with get_session() as db:
        row = db.get(AccountRow, account)
        if row is None:
            return f"No account named {account}."
        salt = secrets.token_bytes(16)
        row.auth_salt = salt.hex()
        row.auth_hash = _hash(password, salt)
        db.commit()
    return f"Password rotated for {account}."


def migrate(char: str, account: str) -> str:
    """Move a v1 character-password onto a NEW account."""
    record = load_character(char)
    if record is None:
        return f"No saved character named {char}."
    if not record.get("auth"):
        return f"{char} has no password to migrate. Set one in-game first: password <secret>"
    with get_session() as db:
        if db.get(AccountRow, account) is not None:
            return f"Account {account} already exists; migration only creates new accounts."
        auth = record["auth"]
        db.add(AccountRow(name=account, auth_salt=auth["salt"], auth_hash=auth["hash"]))
        row = db.get(CharacterRow, char)
        assert row is not None
        row.account = account
        row.auth_salt = None
        row.auth_hash = None
        db.commit()
    return f"{char}@{account} is ready. Log in with the same password."


def import_legacy_json() -> str:
    """One-time importer: characters.json + accounts.json -> SQLite."""
    import json
    from pathlib import Path

    moved = []
    chars = Path("characters.json")
    if chars.exists():
        for name, record in json.loads(chars.read_text()).items():
            put_record(name, record)
            moved.append(name)
    accts = Path("accounts.json")
    if accts.exists():
        with get_session() as db:
            for name, entry in json.loads(accts.read_text()).items():
                if db.get(AccountRow, name) is None and entry.get("auth"):
                    db.add(
                        AccountRow(
                            name=name,
                            auth_salt=entry["auth"]["salt"],
                            auth_hash=entry["auth"]["hash"],
                        )
                    )
                for member in entry.get("characters", []):
                    row = db.get(CharacterRow, member)
                    if row is not None:
                        row.account = name
            db.commit()
    if not moved and not accts.exists():
        return "No legacy JSON found; nothing to import."
    return f"Imported {len(moved)} character(s) into codeforge.db. Legacy files left untouched."


def account_password_ok(account: str, password: str) -> bool:
    """Bare account credential check (no character required) -- the
    HTTP admin surface authenticates accounts, not masks."""
    with get_session() as db:
        row = db.get(AccountRow, account)
        return row is not None and _matches(password, row.auth_salt, row.auth_hash)


def account_has_owner(account: str) -> bool:
    """True if any character on this account holds the owner rank."""
    from sqlalchemy import select

    with get_session() as db:
        rows = db.scalars(select(CharacterRow).where(CharacterRow.account == account))
        return any(row.rank == "owner" for row in rows)
