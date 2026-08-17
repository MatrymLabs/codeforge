"""CARD: party_loot -- share a felled foe's DROPS across the party by a fair round-robin.

The reward-XP half of shared combat pays everyone; this is its loot half. A solo hero's kill still
drops to the floor to be taken (first come, unchanged). But when a party fells a foe together, each
drop is awarded to a party-mate present for the kill, in rotation, so nobody races for the floor
and the haul is shared fairly over a fight instead of hoarded by the fastest `take`.

Round-robin is the DATA-driven policy seam: `assign_drop` implements a per-party turn rotation; it
is the one place an alternative loot rule (need-vs-greed rolls, master looter, free-for-all) would
plug in. Built on the party's `members_in_room` seam and per-player inventory: it moves
a just-spawned drop by reassigning its carrier tag, mutating no world state. It hangs off
combat's single loot-spawn seam (`_spawn_loot`) with one call, so combat stays untouched.
"""

from __future__ import annotations

from kernel.world.events import announce_to
from kernel.world.items import ITEMS, carrier
from kernel.world.party import members_in_room, party_of
from kernel.world.session import SESSIONS, display_name, sentence_case

#: The loot-distribution policy. "round-robin" awards each drop to the next present member in turn.
#: This constant marks the policy seam; a need-vs-greed or master-looter rule branches here.
LOOT_POLICY = "round-robin"

# Per-party loot rotation, keyed by the party's leader id: the index of the next member to receive a
# drop. Transient (like the party itself); an approximate fairness counter, not a persisted ledger.
_TURN: dict[str, int] = {}


def assign_drop(killer_id: str, room: str, iid: str) -> str | None:
    """Award one just-spawned drop to a party-mate by round-robin, moving it into their hands.

    Returns the award line when the drop went to a party member, or None when it should stay on the
    floor (a solo hero, or a partied hero with no co-located mate: first-come loot is unchanged for
    them). An offline member cannot be present, so only online, co-located members share the haul.
    """
    band = party_of(killer_id)
    if band is None:
        return None
    eligible = [m for m in members_in_room(killer_id, room) if SESSIONS.get(m) is not None]
    if len(eligible) < 2:  # solo here: leave it on the floor to be taken (unchanged behavior)  # noqa: E501, PLR2004
        return None
    turn = _TURN.get(band.leader, 0) % len(eligible)
    winner = eligible[turn]
    _TURN[band.leader] = turn + 1
    ITEMS[iid]["location"] = carrier(winner)
    name = sentence_case(ITEMS[iid]["name"])
    line = f"{name} is awarded to {display_name(winner)} (party loot)."
    announce_to([m for m in eligible if m != killer_id], f"\n{line}")
    return line


def _reset() -> None:
    """Clear the loot rotation. For tests, so one test's turn order never leaks into the next."""
    _TURN.clear()
