"""CARD: maintenance -- the game adapter for the change ledger: a world-maintenance log.

`maintenance` shows the world's own change log: fixes and tweaks to the world moving through the
gated change lifecycle. It uses a `ChangeLedger` (parts/change_ledger), so every world change is
recorded and governed like a software patch. The SAME ledger core tracks real software patches in a
practical app (parts/patch_tracker); only the adapter differs.
"""

from __future__ import annotations

from parts.change_ledger import ChangeLedger
from parts.world.session import Session


def _build_log() -> ChangeLedger:
    ledger = ChangeLedger()
    ledger.open("WM-001", "Reinforce the training dummy respawn", "config", "low", "matrym")
    ledger.advance("WM-001", "triage")
    ledger.open("WM-002", "Rebalance the Gate boss counter-attack", "version", "medium", "matrym")
    ledger.advance("WM-002", "triage")
    ledger.advance("WM-002", "approve", actor="approver")
    return ledger


def maintenance(session: Session, arg: str = "") -> str:
    """The `maintenance` verb: the world's change log and each entry's lifecycle state."""
    ledger = _build_log()
    lines = ["World maintenance log:"]
    for change in ledger.all():
        lines.append(
            f"  [{change.status:<9}] {change.change_id}  {change.title} ({change.severity})"
        )
    return "\n".join(lines)
