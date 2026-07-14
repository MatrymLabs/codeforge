"""CARD: hashchain -- a tamper-evident, append-only, hash-chained ledger (stdlib only).

The reusable primitive harvested from the Chronicle (`parts/chronicle.py`, the ship's memory):
each entry carries a sha256 over its own payload AND the previous entry's hash, so any edit,
reorder, or removal of a PAST record is detected the next time the log is read. Zero dependencies
(hashlib + json). The Chronicle is this pattern's specialized proving-ground; it shares this
module's canonical `content_hash`, so there is one hashing algorithm on the ship, not two.

Honest bounds -- this proves INTEGRITY, not everything:
- Detected: a changed payload (hash mismatch), a reordered or inserted record, a deleted MIDDLE
  record (the next record's prior-hash no longer links).
- NOT detected by the chain alone: dropping the LAST record(s) -- anchor the head hash elsewhere
  (a receipt, a second store) if truncation must be caught. And integrity is not authenticity:
  sign the head hash to prove WHO wrote it.
Any break fails loud with `HashChainError` rather than returning a dishonest history.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GENESIS = ""  # the prior_hash of the first link: nothing precedes it
_FIELDS = ("seq", "payload", "prior_hash", "content_hash")


class HashChainError(Exception):
    """Raised when the ledger is malformed or its chain is broken. Names the exact record."""


@dataclass(frozen=True)
class Link:
    """One entry in the chain: its position, its data, and the hashes that bind it to the past."""

    seq: int
    payload: dict[str, Any]
    prior_hash: str
    content_hash: str


def content_hash(payload: Mapping[str, Any]) -> str:
    """A deterministic sha256 over a JSON-serializable mapping (canonical: sorted keys, no spaces).

    This is the ship's one canonical content hash -- `parts/chronicle.py` computes its record
    digest through here, so the two ledgers can never drift to different hashing."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _digest(seq: int, payload: Mapping[str, Any], prior_hash: str) -> str:
    return content_hash({"seq": seq, "payload": payload, "prior_hash": prior_hash})


def append(path: Path, payload: dict[str, Any]) -> Link:
    """Validate, hash-chain, and append one record; return the new Link. The chain is verified
    before it is extended, so appending to a tampered ledger fails loud rather than hiding it."""
    if not isinstance(payload, dict):
        raise HashChainError("payload must be a JSON object (dict)")
    existing = read(path)  # verifies the chain first
    prior = existing[-1].content_hash if existing else GENESIS
    seq = len(existing)
    try:
        digest = _digest(seq, payload, prior)
    except (TypeError, ValueError) as exc:
        raise HashChainError(f"payload is not JSON-serializable: {exc}") from exc
    link = Link(seq=seq, payload=payload, prior_hash=prior, content_hash=digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_as_row(link), sort_keys=True) + "\n")
    return link


def read(path: Path) -> list[Link]:
    """Read every record, verifying the chain as it goes. Fails loud (`HashChainError`) on a
    tampered payload, a broken/reordered chain, or a malformed line. Empty/missing store -> []."""
    if not path.exists():
        return []
    links: list[Link] = []
    prev_hash = GENESIS
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HashChainError(f"line {lineno} is unreadable JSON: {exc}") from exc
        if not isinstance(row, dict) or not all(field in row for field in _FIELDS):
            raise HashChainError(f"line {lineno} is a malformed record (missing fields)")
        expected_seq = len(links)
        if row["seq"] != expected_seq:
            raise HashChainError(
                f"record {row['seq']} is out of order (expected seq {expected_seq})"
            )
        if _digest(row["seq"], row["payload"], row["prior_hash"]) != row["content_hash"]:
            raise HashChainError(f"record {row['seq']} was tampered: content hash mismatch")
        if row["prior_hash"] != prev_hash:
            raise HashChainError(f"broken chain at record {row['seq']}: prior hash does not link")
        links.append(Link(row["seq"], row["payload"], row["prior_hash"], row["content_hash"]))
        prev_hash = row["content_hash"]
    return links


def verify(path: Path) -> bool:
    """True if the ledger reads clean end to end, False if the chain is broken or a line is bad."""
    try:
        read(path)
        return True
    except HashChainError:
        return False


def _as_row(link: Link) -> dict[str, Any]:
    return {
        "seq": link.seq,
        "payload": link.payload,
        "prior_hash": link.prior_hash,
        "content_hash": link.content_hash,
    }
