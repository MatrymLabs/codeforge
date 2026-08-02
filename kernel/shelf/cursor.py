"""CARD: cursor -- keyset pagination over a sort key + tiebreaker; opaque cursor, no offset drift.

Clean-room reconstruction of the keyset/seek pagination pattern and the
opaque-cursor convention (GraphQL Relay connections, Stripe `starting_after`).
Standard library only.

A cursor encodes the (sort_value, tiebreaker) of the last row a client saw. The
next page is the keyset query `WHERE (sort_col, id) > (sort_value, tiebreaker)
ORDER BY sort_col, id LIMIT size`. Unlike offset, rows inserted or deleted before
the boundary never shift later pages, and deep pages are O(1) seeks, not scans.

The cursor is opaque, not secret. Pass a signing key to make it tamper-evident.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

# A JSON-serializable sort value (str/int/float) plus a tiebreaker id.
SortValue = Any
Tiebreak = Any
Boundary = tuple[SortValue, Tiebreak]

MAX_PAGE_SIZE = 1000
_SIG_BYTES = 16  # truncated HMAC length


class CursorError(ValueError):
    """Raised when a cursor is malformed, tampered, or a page size is invalid."""


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    try:
        return base64.urlsafe_b64decode(text + pad)
    except (binascii.Error, ValueError) as exc:
        raise CursorError(f"malformed cursor encoding: {text!r}") from exc


def _sign(payload: bytes, key: bytes) -> bytes:
    return hmac.new(key, payload, hashlib.sha256).digest()[:_SIG_BYTES]


def encode_cursor(sort_value: SortValue, tiebreaker: Tiebreak, *, key: bytes | None = None) -> str:
    """Encode a boundary into an opaque token. Sign it when a key is given."""
    try:
        payload = json.dumps([sort_value, tiebreaker], separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CursorError(f"cursor values must be JSON-serializable: {exc}") from exc
    token = _b64url_encode(payload)
    if key is None:
        return token
    return token + "." + _b64url_encode(_sign(payload, key))


def decode_cursor(token: str, *, key: bytes | None = None) -> Boundary:
    """Decode an opaque token back to (sort_value, tiebreaker).

    When a key is given, the token MUST carry a valid HMAC or CursorError is raised.
    When no key is given, the token MUST NOT carry a signature section.
    """
    if not isinstance(token, str) or not token:
        raise CursorError("cursor must be a non-empty string")
    parts = token.split(".")
    if key is None:
        if len(parts) != 1:
            raise CursorError("unexpected signature on an unsigned cursor")
        payload = _b64url_decode(parts[0])
    else:
        if len(parts) != 2:
            raise CursorError("signed cursor must be '<payload>.<sig>'")
        payload = _b64url_decode(parts[0])
        given = _b64url_decode(parts[1])
        if not hmac.compare_digest(given, _sign(payload, key)):
            raise CursorError("cursor signature does not verify (tampered or wrong key)")
    try:
        decoded = json.loads(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        raise CursorError("malformed cursor payload") from exc
    if not isinstance(decoded, list) or len(decoded) != 2:
        raise CursorError("cursor payload must be [sort_value, tiebreaker]")
    return decoded[0], decoded[1]


def validate_size(size: int) -> int:
    """Return size if valid, else raise. Guards against unbounded page requests."""
    if isinstance(size, bool) or not isinstance(size, int):
        raise CursorError("page size must be a non-bool int")
    if size <= 0:
        raise CursorError("page size must be >= 1")
    if size > MAX_PAGE_SIZE:
        raise CursorError(f"page size {size} exceeds max {MAX_PAGE_SIZE}")
    return size


@dataclass(frozen=True)
class Page:
    """One page of results plus the cursor to fetch the next page."""

    items: Sequence[Any]
    next_cursor: str | None
    has_more: bool


def paginate_keyset(
    rows: Sequence[Any],
    *,
    sort_key: Callable[[Any], SortValue],
    tiebreak: Callable[[Any], Tiebreak],
    size: int,
    after: str | None = None,
    sign_key: bytes | None = None,
) -> Page:
    """Reference in-memory keyset paginator.

    `rows` must already be ordered ascending by (sort_key(row), tiebreak(row)) -
    exactly the order the equivalent SQL `ORDER BY sort_col, id` would produce.
    Returns up to `size` rows strictly after the decoded `after` boundary, plus a
    next_cursor built from the last returned row.
    """
    validate_size(size)
    start = 0
    if after is not None:
        boundary = decode_cursor(after, key=sign_key)
        # advance past every row <= the boundary, keyed on (sort, tiebreak)
        for i, row in enumerate(rows):
            if (sort_key(row), tiebreak(row)) > boundary:
                start = i
                break
        else:
            start = len(rows)
    window = rows[start : start + size]
    has_more = start + size < len(rows)
    next_cursor = None
    if window and has_more:
        last = window[-1]
        next_cursor = encode_cursor(sort_key(last), tiebreak(last), key=sign_key)
    return Page(items=window, next_cursor=next_cursor, has_more=has_more)
