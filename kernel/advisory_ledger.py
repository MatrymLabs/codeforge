"""CARD: advisory_ledger -- track each dependency advisory's lifecycle so posture can measure MTTR.

RD-2026-0002 (the posture-gap store). kernel/posture.py reports oldest_open_advisory_days,
mean_time_to_remediate, and expired_exception_count as NOT_COMPUTABLE because nothing records WHEN
an advisory first appeared or was fixed - pip-audit only says what is open right now. This is the
persistent store that closes those gaps: for every advisory id it records `first_seen` and (once it
disappears from a scan) `resolved`, so the fleet can compute how long its oldest exposure has stood
and its mean time to a DEPLOYED fix (the DoD metric: deployed, not closed-ticket).

The integration is `reconcile(states, open_ids, today)`: feed it the advisory ids from the latest
pip-audit scan; it stamps new ones seen today and auto-resolves ones no longer present. Idempotent
- a second reconcile on the same scan changes nothing. Persistence is stdlib JSONL (no new dep); the
store is INJECTED as a dict in `reconcile`/the computations, so tests never touch disk.

Honest scope: `resolved` means "no longer reported by the scanner", which is the deployed-fix signal
available from evidence we already produce; a re-introduced advisory simply re-opens with a new
first_seen. Clean-room, stdlib only (json, datetime, pathlib).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

# a store is a mapping advisory_id -> AdvisoryState (kept simple + JSON-serializable)
Store = dict[str, "AdvisoryState"]


class AdvisoryLedgerError(ValueError):
    """Raised on a malformed advisory record on disk."""


@dataclass(frozen=True)
class AdvisoryState:
    """One advisory's lifecycle: when we first saw it and (if fixed) when it left the scan."""

    advisory_id: str
    first_seen: date
    resolved: date | None = None

    @property
    def is_open(self) -> bool:
        return self.resolved is None


def ids_from_pip_audit(data: Any) -> set[str]:
    """Extract the set of advisory ids from a parsed pip-audit json (the `vulns[].id` values)."""
    deps = data.get("dependencies", []) if isinstance(data, dict) else data
    ids: set[str] = set()
    for dep in deps if isinstance(deps, list) else []:
        if isinstance(dep, dict):
            for vuln in dep.get("vulns", []):
                if isinstance(vuln, dict) and vuln.get("id"):
                    ids.add(str(vuln["id"]))
    return ids


def reconcile(states: Store, open_ids: set[str], today: date) -> Store:
    """Update the store against the current scan's open advisory ids (idempotent).

    A new id is stamped first_seen=today; an id in the store that is no longer open and not yet
    resolved is stamped resolved=today; a re-appearing resolved id re-opens (new first_seen).
    Returns a NEW store (the input is not mutated)."""
    out: Store = dict(states)
    for aid in open_ids:
        cur = out.get(aid)
        if cur is None or not cur.is_open:
            out[aid] = AdvisoryState(aid, first_seen=today)
    for aid, st in out.items():
        if aid not in open_ids and st.is_open:
            out[aid] = replace(st, resolved=today)
    return out


def oldest_open_first_seen(states: Store) -> date | None:
    """The earliest first_seen among still-open advisories (posture's oldest-advisory input)."""
    open_dates = [s.first_seen for s in states.values() if s.is_open]
    return min(open_dates) if open_dates else None


def remediation_days(states: Store) -> tuple[int, ...]:
    """Days from first_seen to resolved for every fixed advisory (posture's MTTR input)."""
    return tuple(
        (s.resolved - s.first_seen).days for s in states.values() if s.resolved is not None
    )


def open_count(states: Store) -> int:
    return sum(1 for s in states.values() if s.is_open)


def load(path: Path | str) -> Store:
    """Read the JSONL advisory ledger (one record per line); an absent file is an empty store."""
    p = Path(path)
    if not p.exists():
        return {}
    states: Store = {}
    for lineno, line in enumerate(p.read_text("utf-8").splitlines(), 1):
        line = line.strip()  # noqa: PLW2901
        if not line:
            continue
        try:
            row = json.loads(line)
            aid = str(row["advisory_id"])
            resolved = row.get("resolved")
            states[aid] = AdvisoryState(
                advisory_id=aid,
                first_seen=date.fromisoformat(row["first_seen"]),
                resolved=date.fromisoformat(resolved) if resolved else None,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            raise AdvisoryLedgerError(f"{p}:{lineno}: malformed advisory record: {exc}") from exc
    return states


def save(path: Path | str, states: Store) -> None:
    """Write the store as JSONL (sorted by id, so the file is diff-stable)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for aid in sorted(states):
        st = states[aid]
        lines.append(
            json.dumps(
                {
                    "advisory_id": st.advisory_id,
                    "first_seen": st.first_seen.isoformat(),
                    "resolved": st.resolved.isoformat() if st.resolved else None,
                }
            )
        )
    p.write_text("\n".join(lines) + ("\n" if lines else ""), "utf-8")


def render(states: Store, today: date) -> str:
    """A human-readable advisory-lifecycle summary."""
    oldest = oldest_open_first_seen(states)
    rem = remediation_days(states)
    lines = [
        f"advisory ledger: {open_count(states)} open, {len(rem)} resolved",
    ]
    if oldest is not None:
        lines.append(f"  oldest open advisory exposed {(today - oldest).days}d (since {oldest})")
    if rem:
        lines.append(f"  MTTR {round(sum(rem) / len(rem), 1)}d over {len(rem)} fixes")
    return "\n".join(lines)
