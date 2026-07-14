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

# parts.db is imported lazily inside the functions that touch persistence (below), so a
# DB-free `import forge` (play/command sessions, benchmarks, most tests) never pays the
# ~400ms SQLAlchemy import. The cost shifts to the first real DB touch (e.g. first login),
# measured, not hidden. parts.db owns the ORM rows; this only defers WHEN they load. (EXP-003)

_ITERATIONS = 600_000
MIN_PASSWORD_LEN = 8  # NIST SP 800-63B floor: length beats composition rules
_TOO_SHORT = f"Passwords need at least {MIN_PASSWORD_LEN} characters."


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


def register(char: str, account: str, password: str) -> str:
    """Create or extend an account with a new character. Returns '' on
    success; the engine tick finishes the character's birth."""
    if len(password) < MIN_PASSWORD_LEN:
        return _TOO_SHORT
    if load_character(char) is not None:
        return f"A character named {char} already exists."
    from parts.db import AccountRow, open_archive_session

    with open_archive_session() as db:
        account_row = db.get(AccountRow, account)
        if account_row is None:
            salt = secrets.token_bytes(16)
            db.add(
                AccountRow(
                    name=account, auth_salt=salt.hex(), auth_hash=_hash_secret(password, salt)
                )
            )
            db.commit()
        elif not _secret_matches(password, account_row.auth_salt, account_row.auth_hash):
            return "That account exists and this is not its password."
    return ""


def inspect_login(char: str, account: str, password: str) -> bool:
    """One generic verdict: account exists, password matches, and the
    character belongs to that account. Which part failed is a secret."""
    from parts.db import AccountRow, CharacterRow, open_archive_session

    with open_archive_session() as db:
        account_row = db.get(AccountRow, account)
        if account_row is None:
            _burn_hash(password)  # constant-time: an unknown account costs the same as a real check
            return False
        if not _secret_matches(password, account_row.auth_salt, account_row.auth_hash):
            return False
        hero_row = db.get(CharacterRow, char)
        return hero_row is not None and hero_row.account == account


def adopt(char: str, account: str) -> str:
    """Attach an existing character to an account (migration/admin)."""
    from parts.db import CharacterRow, open_archive_session

    with open_archive_session() as db:
        hero_row = db.get(CharacterRow, char)
        if hero_row is None:
            return f"No saved character named {char}."
        hero_row.account = account
        db.commit()
    return f"{char} now belongs to {account}."


def rotate_account_secret(account: str, password: str) -> str:
    """Rotate an account's secret (the codeforge passwd verb)."""
    if len(password) < MIN_PASSWORD_LEN:
        return _TOO_SHORT
    from parts.db import AccountRow, open_archive_session

    with open_archive_session() as db:
        account_row = db.get(AccountRow, account)
        if account_row is None:
            return f"No account named {account}."
        salt = secrets.token_bytes(16)
        account_row.auth_salt = salt.hex()
        account_row.auth_hash = _hash_secret(password, salt)
        db.commit()
    return f"Password rotated for {account}."


def reforge_secret(account: str, old: str, new: str) -> str:
    """Self-service rotation: prove the current secret, then set a new
    one. Returns '' on success or the reason it was refused. The old
    password is verified constant-time; the new one is salted afresh.
    Refusal on a bad old password stays generic -- no enumeration."""
    if len(new) < MIN_PASSWORD_LEN:
        return _TOO_SHORT
    from parts.db import AccountRow, open_archive_session

    with open_archive_session() as db:
        account_row = db.get(AccountRow, account)
        if account_row is None or not _secret_matches(
            old, account_row.auth_salt, account_row.auth_hash
        ):
            return "That is not your current password."
        salt = secrets.token_bytes(16)
        account_row.auth_salt = salt.hex()
        account_row.auth_hash = _hash_secret(new, salt)
        db.commit()
    return ""


def migrate(char: str, account: str) -> str:
    """Move a v1 character-password onto a NEW account."""
    casefile = load_character(char)
    if casefile is None:
        return f"No saved character named {char}."
    if not casefile.get("auth"):
        return f"{char} has no password to migrate. Set one in-game first: password <secret>"
    from parts.db import AccountRow, CharacterRow, open_archive_session

    with open_archive_session() as db:
        if db.get(AccountRow, account) is not None:
            return f"Account {account} already exists; migration only creates new accounts."
        auth = casefile["auth"]
        db.add(AccountRow(name=account, auth_salt=auth["salt"], auth_hash=auth["hash"]))
        hero_row = db.get(CharacterRow, char)
        assert hero_row is not None
        hero_row.account = account
        hero_row.auth_salt = None
        hero_row.auth_hash = None
        db.commit()
    return f"{char}@{account} is ready. Log in with the same password."


def import_legacy_json() -> str:
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
        from parts.db import AccountRow, CharacterRow, open_archive_session

        with open_archive_session() as db:
            for name, entry in json.loads(accts.read_text(encoding="utf-8")).items():
                if db.get(AccountRow, name) is None and entry.get("auth"):
                    db.add(
                        AccountRow(
                            name=name,
                            auth_salt=entry["auth"]["salt"],
                            auth_hash=entry["auth"]["hash"],
                        )
                    )
                for member in entry.get("characters", []):
                    hero_row = db.get(CharacterRow, member)
                    if hero_row is not None:
                        hero_row.account = name
            db.commit()
    if not moved and not accts.exists():
        return "No legacy JSON found; nothing to import."
    return f"Imported {len(moved)} character(s) into codeforge.db. Legacy files left untouched."


def account_password_ok(account: str, password: str) -> bool:
    """Bare account credential check (no character required) -- the
    HTTP admin surface authenticates accounts, not masks."""
    from parts.db import AccountRow, open_archive_session

    with open_archive_session() as db:
        account_row = db.get(AccountRow, account)
        if account_row is None:
            _burn_hash(password)  # constant-time: an unknown account costs the same as a real check
            return False
        return _secret_matches(password, account_row.auth_salt, account_row.auth_hash)


def account_has_owner(account: str) -> bool:
    """True if any character on this account holds the owner rank."""
    from sqlalchemy import select

    from parts.db import CharacterRow, open_archive_session

    with open_archive_session() as db:
        archive_rows = db.scalars(select(CharacterRow).where(CharacterRow.account == account))
        return any(archive_row.rank == "owner" for archive_row in archive_rows)
