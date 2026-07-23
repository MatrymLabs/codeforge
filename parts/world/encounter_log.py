"""CARD: encounter_log -- the after-action log: a bounded, NON-chained trace of combat encounters.

The "observed" leg of the aggression loop. Two facts about this module are the whole design:

1. **The player's tick writes here, so it must NEVER touch the Chronicle.** The Chronicle
   (parts/chronicle) is tamper-evident precisely because every append comes from a trusted
   (owner/CI) actor. A per-encounter write from `handle_command` would hand any player a write
   path into the hash-chained ledger -- the exact poisoning surface the design forbids. So this
   log is a separate, un-chained store, and it imports nothing from chronicle.

2. **It is bounded and ephemeral by design.** A capped in-memory ring holds the most recent
   encounters (older ones roll off), so a flood just rotates the ring instead of growing without
   limit. Alongside the ring, running TALLIES count encounters by kind; a trusted boundary
   (parts/encounter_flush, an owner command / `make daily`) later reads those tallies and records
   ONE aggregate metric into the Chronicle -- never per event, never from the tick.

State is world-scoped (like NPCS/SESSIONS) and mutated only by validated engine logic; rendering
never mutates it. Stdlib-only.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass

from parts.world.session import sentence_case

# The observed encounter beats. A kind outside this set is a wiring bug, not player input, so it
# fails loud (the call sites use these constants; a typo turns a test red instead of logging junk).
KINDS = ("open_strike", "leash_break", "fall", "defeat")

CAP = 100  # the ring holds this many recent encounters; older ones roll off under load


class EncounterError(ValueError):
    """An encounter of an unknown kind: fail loud rather than log a mis-typed beat."""


@dataclass(frozen=True)
class EncounterEvent:
    """One witnessed encounter beat: what happened and to/by whom. A projection request for the
    after-action render, never a mutation and never an evidence claim."""

    kind: str  # one of KINDS
    who: str  # the NPC's authored name (the aggressor, the felling foe, or the fallen)
    detail: str = ""  # a short human line, optional


_ring: deque[EncounterEvent] = deque(maxlen=CAP)
_tally: Counter[str] = Counter()


def witness(kind: str, who: str, detail: str = "") -> EncounterEvent:
    """Record one encounter beat: append it to the bounded ring and bump its running tally.
    Called from the tick; deliberately reaches nothing trusted. Returns the filed event."""
    if kind not in KINDS:
        raise EncounterError(f"unknown encounter kind '{kind}', not in {KINDS}")
    if not who.strip():
        raise EncounterError("an encounter needs a 'who'")
    event = EncounterEvent(kind=kind, who=who, detail=detail)
    _ring.append(event)
    _tally[kind] += 1
    return event


def recent(limit: int = CAP) -> list[EncounterEvent]:
    """The most recent encounters, newest last, at most `limit` of them (a read-only view)."""
    events = list(_ring)
    return events[-limit:] if limit < len(events) else events


def tally() -> dict[str, int]:
    """A copy of the running counts by kind (what the trusted flush later aggregates)."""
    return {kind: _tally.get(kind, 0) for kind in KINDS}


def render_recent(limit: int = 10) -> str:
    """The after-action log as player-facing text: the last few encounters plus the run tallies."""
    events = recent(limit)
    if not events:
        return "No encounters logged yet."
    lines = ["Recent encounters (after-action log):"]
    for e in events:
        tail = f" -- {e.detail}" if e.detail else ""
        lines.append(f"  [{e.kind}] {sentence_case(e.who)}{tail}")
    counts = tally()
    summary = ", ".join(f"{kind}: {counts[kind]}" for kind in KINDS if counts[kind])
    lines.append(f"\nTallies -> {summary}" if summary else "\nTallies -> none")
    return "\n".join(lines)


def clear_tally() -> None:
    """Zero the running tallies WITHOUT touching the ring. The trusted boundary
    (parts/encounter_flush) calls this after it has aggregated a period's tallies into the
    Chronicle, so the next period counts from zero while the live ring still shows recent beats."""
    _tally.clear()


def reset() -> None:
    """Clear the ring and the tallies. Test hook, and a full wipe when a fresh slate is wanted."""
    _ring.clear()
    _tally.clear()
