"""CARD: gather -- harvest crafting materials from the wilds (the maker's non-combat source).

The crafting loop (kernel.world.crafting) had only one source of materials: kill a foe and hope it
drops an ember-shard. This is the other source the loop was missing -- GATHERING. A room may carry a
`node` (a material prototype); `gather` there mints one into the Forger's hands, and the node renews
after a short cooldown, so a single spot is not an infinite well. A player who would rather forage
than fight can still fuel the forge: gather -> craft -> equip, with no blood spilled.

The cooldown is per PLAYER (an MMO node is not contested), tracked on the session and ticked down
on the world beat (`tick_gather`, beside burns/menace/zones). The gathered materials are the
seed's own crafting inputs, so gathering feeds real recipes; nothing new is invented here.
"""

from __future__ import annotations

from kernel.world.session import Session

GATHER_COOLDOWN = 6  # world-beats before a node renews for the player who worked it


def gather(session: Session) -> str:
    """`gather` -- harvest the current room's node into your hands, if it has one and has renewed.
    Fails cleanly when there is nothing here, or the node is still spent."""
    from kernel.world.world import WORLD

    room = WORLD.get(session.location)
    node = room.get("node") if room else None
    if not node:
        return "There is nothing to gather here."
    left = session.gather_cooldowns.get(session.location, 0)
    if left > 0:
        return f"You have worked this node bare; give it a while to renew ({left} beats)."

    from kernel.world import items

    try:
        iid = items.clone(node, items.carrier(session.player_id))
    except items.ItemError:
        return "There is nothing to gather here."  # a node naming an unknown material: fail soft
    session.gather_cooldowns[session.location] = GATHER_COOLDOWN
    line = f"You gather {items.ITEMS[iid]['name']}."
    # Working a material advances the gather trade that claims it (mining/herbalism/prospecting);
    # a rank-up appends its own line, a no-op is silent (kernel.world.professions).
    from kernel.world.professions import advance, trade_for_gather

    rose = advance(session, trade_for_gather(str(node)))
    if rose:
        line = f"{line}\n{rose}"
    # A forage contract ('gather N of a material HERE') advances on the harvest, scoped to this zone
    # -- the non-combat twin of a cull (kernel.world.forage). Cheap: an unrouted key is a dict miss.
    from kernel.world import quest
    from kernel.world.cull import scope_key
    from kernel.world.zones import zone_of

    zone = zone_of(session.location)
    if zone:
        forage_line = quest.on_event(session, "forage", scope_key(zone, str(node)))
        if forage_line:
            line = f"{line}\n{forage_line}"
    return line


def gather_hint(location: str) -> str:
    """A one-line look hint for a room with a gather node (the material by name), or "". Lets a
    forager SEE what a place offers instead of guessing with `gather`."""
    from kernel.world import items
    from kernel.world.world import WORLD

    room = WORLD.get(location)
    node = room.get("node") if room else None
    if not node or node not in items.PROTOTYPES:
        return ""
    return f"You could gather {items.PROTOTYPES[node]['name']} here."


def tick_gather(session: Session) -> str:
    """On the world beat, renew the player's gather nodes by one beat (drop the ready ones). Silent:
    node renewal needs no line. Returns '' so it composes into the beat like the other tickers."""
    for room in list(session.gather_cooldowns):
        session.gather_cooldowns[room] -= 1
        if session.gather_cooldowns[room] <= 0:
            del session.gather_cooldowns[room]
    return ""
