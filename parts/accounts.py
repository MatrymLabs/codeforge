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
import secrets
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
