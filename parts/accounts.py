"""CARD: accounts -- names become logins with real password hashing.

Ranks made impersonation into privilege escalation, so protected
names now demand proof. Rules that never bend:

1. Plaintext passwords are NEVER stored -- only pbkdf2_hmac(sha256)
   with a per-user random salt and 600k iterations (stdlib; we do
   not roll our own crypto).
2. Verification happens BEFORE a session re-keys to a name.
3. Legacy passwordless records still restore, with a nag to protect.

LAN honesty: the transport is plaintext telnet, so this protects
against casual impersonation, not wire sniffing. TLS is a future
gateway concern.
"""

import hashlib
import json
import secrets
from pathlib import Path
from typing import Any

from parts.characters import load_character, put_record

_ITERATIONS = 600_000


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS).hex()


def has_password(record: dict[str, Any]) -> bool:
    return bool(record.get("auth"))


def set_password(name: str, password: str) -> str:
    """Attach protection to a saved character. Owner of the name only
    (the engine tick enforces that the caller IS that character)."""
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
    """True only if the record is protected AND the password matches."""
    record = load_character(name)
    if record is None or not has_password(record):
        return False
    salt = bytes.fromhex(record["auth"]["salt"])
    expected = record["auth"]["hash"]
    return secrets.compare_digest(_hash(password, salt), expected)


# ---------------------------------------------------------------- accounts
# An account is the HUMAN: one password, many characters. Login is
# character@account -- the mask, worn by its owner.

ACCOUNTS_PATH = Path("accounts.json")


def _read_accounts(path: Path | None = None) -> dict[str, dict[str, Any]]:
    path = path or ACCOUNTS_PATH
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _write_accounts(data: dict[str, dict[str, Any]], path: Path | None = None) -> None:
    path = path or ACCOUNTS_PATH
    path.write_text(json.dumps(data, indent=2))


def parse_handle(handle: str) -> tuple[str, str] | None:
    """'matrym@matlabs' -> ('matrym', 'matlabs'); None if malformed."""
    char, at, account = handle.partition("@")
    if not at or not char or not account:
        return None
    return (char, account)


def register(char: str, account: str, password: str) -> str:
    """Create or extend an account with a new character.

    New account: password becomes the account's secret.
    Existing account: password must match before a character is added.
    Character names are globally unique -- no hijacking saved heroes."""
    if len(password) < 4:
        return "Passwords need at least 4 characters."
    if load_character(char) is not None:
        return f"A character named {char} already exists."
    accounts = _read_accounts()
    entry = accounts.get(account)
    if entry is None:
        salt = secrets.token_bytes(16)
        entry = {"auth": {"salt": salt.hex(), "hash": _hash(password, salt)}, "characters": []}
        accounts[account] = entry
    else:
        if not _verify_account_entry(entry, password):
            return "That account exists and this is not its password."
    entry["characters"].append(char)
    _write_accounts(accounts)
    return ""  # empty string means success; the tick finishes the birth


def _verify_account_entry(entry: dict[str, Any], password: str) -> bool:
    salt = bytes.fromhex(entry["auth"]["salt"])
    return secrets.compare_digest(_hash(password, salt), entry["auth"]["hash"])


def login_check(char: str, account: str, password: str) -> bool:
    """One generic verdict. Never reveals WHICH part was wrong --
    'no such account' vs 'bad password' is a gift to attackers."""
    accounts = _read_accounts()
    entry = accounts.get(account)
    if entry is None:
        return False
    if char not in entry["characters"]:
        return False
    return _verify_account_entry(entry, password)


def migrate(char: str, account: str, path: Path | None = None) -> str:
    """Host-shell tool: move a v1 character-password onto an account.
    The character's own auth is retired; the account takes over."""
    record = load_character(char)
    if record is None:
        return f"No saved character named {char}."
    if not record.get("auth"):
        return f"{char} has no password to migrate. Set one in-game first: password <secret>"
    accounts = _read_accounts(path)
    if account in accounts:
        return f"Account {account} already exists; migration only creates new accounts."
    accounts[account] = {"auth": record.pop("auth"), "characters": [char]}
    _write_accounts(accounts, path)
    put_record(char, record)
    return f"{char}@{account} is ready. Log in with the same password."


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 4 and sys.argv[1] == "migrate":
        print(migrate(sys.argv[2], sys.argv[3]))
    else:
        print("Usage: python3 -m parts.accounts migrate <character> <account>")
