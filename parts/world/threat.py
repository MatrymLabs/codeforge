"""CARD: threat -- who a foe wants to hit: a per-NPC aggro table (the trinity's tank seam).

Reactive combat answers a blow; aggression strikes on the beat. Both used to hit whoever's tick was
running -- so in a group fight a foe effectively swung at random. This is the missing piece of the
holy trinity: a foe remembers how much menace each hero has shown it, and strikes the one at the top
of that table. Damage generates threat; a taunt spikes it so a tank can pull a foe off the healer.

State is canonical and per-foe: `_THREAT[nid][player_id] = score`. Renderers never touch it; only
validated combat logic adds. A felled foe's table is cleared (it reassembles with no grudge), and a
hero who leaves is dropped, so the table is bounded by who is actually fighting.
"""

from __future__ import annotations

from parts.world.session import Session

_THREAT: dict[str, dict[str, int]] = {}  # nid -> {player_id -> accumulated threat}


def add(nid: str, player_id: str, amount: int) -> None:
    """Accrue the threat a hero has shown a foe (damage dealt, a heal cast nearby, a taunt). A
    non-positive amount is ignored, so a blocked or absorbed blow never moves the table."""
    if amount <= 0:
        return
    table = _THREAT.setdefault(nid, {})
    table[player_id] = table.get(player_id, 0) + amount


def score(nid: str, player_id: str) -> int:
    """How much threat one hero holds on one foe (0 if none)."""
    return _THREAT.get(nid, {}).get(player_id, 0)


def top_target(nid: str, present: dict[str, Session]) -> Session | None:
    """The session the foe most wants to hit: the highest-threat hero currently in the room. Ties
    break by player_id so the target does not jitter beat to beat. None if no present hero has any
    threat yet (the caller then falls back to whoever provoked it)."""
    table = _THREAT.get(nid)
    if not table:
        return None
    ranked = [(pid, table[pid]) for pid in present if table.get(pid, 0) > 0]
    if not ranked:
        return None
    top_pid = max(ranked, key=lambda kv: (kv[1], kv[0]))[0]
    return present[top_pid]


def taunt(nid: str, player_id: str, present_ids: list[str]) -> int:
    """Force the foe onto the taunter: set their threat one above the highest present hero's.
    Returns the taunter's new threat. This is the tank's lever -- it overrides raw damage threat."""
    table = _THREAT.setdefault(nid, {})
    current_top = max((table.get(pid, 0) for pid in present_ids), default=0)
    table[player_id] = max(table.get(player_id, 0), current_top + 1)
    return table[player_id]


def drop(nid: str, player_id: str) -> None:
    """Forget a hero's threat on a foe (they left the room, or logged out)."""
    table = _THREAT.get(nid)
    if table is not None:
        table.pop(player_id, None)
        if not table:
            del _THREAT[nid]


def clear(nid: str) -> None:
    """Forget all threat on a foe (it was felled, or reassembled -- no grudge survives)."""
    _THREAT.pop(nid, None)


def _reset() -> None:
    """Empty the whole table (tests, so one fight's grudges never leak to the next)."""
    _THREAT.clear()
