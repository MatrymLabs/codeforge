"""CARD: party_rewards -- share a felled foe's reward across the killer's co-located party.

Fighting together should pay. When a hero in a party fells a foe, this spreads the kill's reward to
their party-mates present in the same room, so grouping is worthwhile rather than a way to split one
prize thinner. It is the reward half of shared combat, built on the party's
`members_in_room` seam and the leveling engine's award functions, and it hangs off combat's single
kill/reward seam (`combat.land_hit`) so combat itself stays untouched.

The share policy is DATA, not hard-coded logic: `share_kill` implements the full-credit model (every
present member earns the full reward -- helping is purely rewarding, the point of grouping), and it
is the one seam an alternative world-economy (even-split, diminishing returns, level-scaled) would
replace. Progression only: XP/JP/TP flow through the same award path a solo kill uses; coins and
loot are not auto-split here (loot rules are their own feature and extension point). It mutates no
world state of its own.
"""

from __future__ import annotations

from kernel.world.events import announce_to
from kernel.world.party import members_in_room, party_of
from kernel.world.progression_awards import award_jp, award_tp, award_xp
from kernel.world.session import SESSIONS, display_name

#: The kill-reward share policy. "full" = every present member earns the full reward (the tag-credit
#: model that makes grouping purely rewarding). This constant marks the policy seam; an alternative
#: economy (even-split, diminishing returns) would branch here rather than editing the callers.
SHARE_POLICY = "full"


def share_kill(killer_id: str, room: str, npc_name: str, xp: int, jp: int, tp: int) -> str:
    """Spread a kill's advancement reward to the killer's party-mates present in `room`.

    Each present mate earns the full reward (full-credit policy) and is told so on their own line;
    an offline or callingless mate earns nothing (they cannot advance) and is skipped without error.
    Returns a one-line summary for the killer, or "" when the kill was solo, the killer's mates are
    elsewhere, or no eligible mate was present. The killer's own reward is awarded by the caller
    (`combat.land_hit`); this only reaches the mates, so the seam adds sharing without doubling it.
    """
    if party_of(killer_id) is None:
        return ""  # a solo hero: nothing to share
    mates = [m for m in members_in_room(killer_id, room) if m != killer_id]
    shared_with = 0
    for mate in mates:
        session = SESSIONS.get(mate)
        if session is None or session.stats is None:  # offline, or no calling to earn on
            continue
        lines = [award_xp(session, xp)]
        lines += [line for line in (award_jp(session, jp), award_tp(session, tp)) if line]
        announce_to(
            [mate],
            f"\n{display_name(killer_id)}'s party fells {npc_name}; you share the kill.\n"
            + "\n".join(lines),
        )
        shared_with += 1
    if not shared_with:
        return ""
    allies = "ally" if shared_with == 1 else "allies"
    return f"Your party shares the kill ({shared_with} {allies})."
