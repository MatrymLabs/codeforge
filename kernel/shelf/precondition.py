"""CARD: precondition -- reject a stale write (lost-update prevention) via ETag/If-Match.

Clean-room reconstruction of HTTP conditional requests (RFC 7232: ETag,
If-Match, If-None-Match) and the optimistic-locking pattern. Standard library
only.

Two faces of one mechanism:
  - HTTP conditional request: derive an ETag from a version or payload, parse the
    client's If-Match / If-None-Match, enforce the precondition.
  - Optimistic lock: an integer version compare-and-set for non-HTTP writes
    (the world tick) via require_version / next_version.

A Precondition is an integrity guard, not an auth check; authorization runs first.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

# A valid entity-tag is a quoted string, optionally weak-prefixed: W/"..."
# RFC 7232 etagc: any VCHAR except '"', plus obs-text; we accept a pragmatic set.
_ETAG = re.compile(r'\A(W/)?"([^"]*)"\Z')
_STAR = "*"


class PreconditionError(ValueError):
    """Raised when an ETag or conditional header is malformed."""


class PreconditionFailed(Exception):  # noqa: N818
    """The precondition did not hold. Maps to HTTP 412 Precondition Failed."""


class StaleWrite(PreconditionFailed):
    """A version guard saw a stale expected version. Maps to HTTP 409 Conflict."""


# ------------------------------------------------------------------ ETag value
@dataclass(frozen=True)
class ETag:
    """A parsed entity-tag: an opaque value plus its weak/strong flag."""

    value: str
    weak: bool = False

    def format(self) -> str:
        prefix = "W/" if self.weak else ""
        return f'{prefix}"{self.value}"'

    def strong_equals(self, other: ETag) -> bool:
        # RFC 7232: strong comparison requires BOTH to be strong and values equal.
        return not self.weak and not other.weak and self.value == other.value

    def weak_equals(self, other: ETag) -> bool:
        # Weak comparison ignores the weak flag; only the values must match.
        return self.value == other.value


def parse_etag(raw: str) -> ETag:
    """Parse a single entity-tag like '"abc"' or 'W/"abc"'."""
    if not isinstance(raw, str):
        raise PreconditionError(f"etag must be a string, got {type(raw).__name__}")  # noqa: TRY003
    m = _ETAG.match(raw.strip())
    if not m:
        raise PreconditionError(f"malformed etag: {raw!r} (expected a quoted value)")  # noqa: TRY003
    return ETag(value=m.group(2), weak=m.group(1) is not None)


def etag_for_version(version: int) -> ETag:
    """A strong ETag whose value is the record's integer version."""
    if isinstance(version, bool) or not isinstance(version, int):
        raise PreconditionError("version must be a non-bool int")  # noqa: TRY003
    if version < 0:
        raise PreconditionError("version must be >= 0")  # noqa: TRY003
    return ETag(value=str(version), weak=False)


def etag_for_payload(payload: bytes, *, weak: bool = False) -> ETag:
    """A content ETag: a short strong (or weak) hash of the serialized payload."""
    if not isinstance(payload, (bytes, bytearray)):
        raise PreconditionError("payload must be bytes")  # noqa: TRY003
    digest = hashlib.blake2b(bytes(payload), digest_size=16).hexdigest()
    return ETag(value=digest, weak=weak)


# ------------------------------------------------- conditional-header parsing
def _parse_tag_list(header: str) -> tuple[bool, list[ETag]]:
    """Return (is_star, tags). A malformed member raises PreconditionError."""
    if not isinstance(header, str):
        raise PreconditionError("conditional header must be a string")  # noqa: TRY003
    trimmed = header.strip()
    if trimmed == "":
        raise PreconditionError("conditional header must not be empty")  # noqa: TRY003
    if trimmed == _STAR:
        return True, []
    tags = [parse_etag(part) for part in trimmed.split(",")]
    return False, tags


# ---------------------------------------------------------------- enforcement
def if_match(current: ETag | None, header: str) -> None:
    """Enforce If-Match (strong comparison). Raise PreconditionFailed on mismatch.

    current is the resource's current ETag, or None if it does not exist.
    """
    is_star, tags = _parse_tag_list(header)
    if is_star:
        if current is None:
            raise PreconditionFailed("If-Match: * but resource does not exist")  # noqa: TRY003
        return
    if current is None:
        raise PreconditionFailed("If-Match given but resource does not exist")  # noqa: TRY003
    if any(current.strong_equals(t) for t in tags):
        return
    raise PreconditionFailed("If-Match did not match the current ETag")  # noqa: TRY003


def if_none_match(current: ETag | None, header: str) -> None:
    """Enforce If-None-Match (weak comparison). Raise PreconditionFailed if it matches.

    `*` means "only if the resource does not already exist" (safe create).
    """
    is_star, tags = _parse_tag_list(header)
    if is_star:
        if current is not None:
            raise PreconditionFailed("If-None-Match: * but resource already exists")  # noqa: TRY003
        return
    if current is None:
        return
    if any(current.weak_equals(t) for t in tags):
        raise PreconditionFailed("If-None-Match matched the current ETag")  # noqa: TRY003


# ------------------------------------------------------- optimistic lock (int)
def require_version(expected: int, actual: int) -> None:
    """Compare-and-set guard for non-HTTP writes. Raise StaleWrite on mismatch."""
    for label, v in (("expected", expected), ("actual", actual)):
        if isinstance(v, bool) or not isinstance(v, int):
            raise PreconditionError(f"{label} version must be a non-bool int")  # noqa: TRY003
    if expected != actual:
        raise StaleWrite(f"stale write: expected version {expected}, current is {actual}")  # noqa: TRY003


def next_version(current: int) -> int:
    """The version to store after a successful guarded write."""
    if isinstance(current, bool) or not isinstance(current, int):
        raise PreconditionError("current version must be a non-bool int")  # noqa: TRY003
    if current < 0:
        raise PreconditionError("current version must be >= 0")  # noqa: TRY003
    return current + 1
