"""Checksum a durable record and classify whether its stored digest still matches.

The checksum is metadata held by the persistence boundary, never a field on the record it checks.
That keeps the durable domain record checksum-free while allowing a read to refuse a row whose
canonical facts no longer match what was written.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Any


class IntegrityVerdict(StrEnum):
    """A verdict over the gameplay-state scope, never ownership or credentials."""

    INTACT = "gameplay-state:intact"
    CORRUPT = "gameplay-state:corrupt"
    UNVERIFIED = "gameplay-state:unverified"


class SaveIntegrityError(RuntimeError):
    """A durable record cannot be returned as trusted state."""

    def __init__(self, verdict: IntegrityVerdict) -> None:
        self.verdict = verdict
        super().__init__(f"character record integrity verdict ({verdict.value})")


def checksum_of(record: Mapping[str, Any]) -> str:
    """The stable SHA-256 digest of a record's canonical JSON representation."""
    canonical = json.dumps(
        dict(record),
        default=str,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_record(record: Mapping[str, Any], stored: str | None) -> IntegrityVerdict:
    """Classify a record without treating an absent legacy checksum as corruption."""
    if not stored:
        return IntegrityVerdict.UNVERIFIED
    if hmac.compare_digest(checksum_of(record), stored):
        return IntegrityVerdict.INTACT
    return IntegrityVerdict.CORRUPT
