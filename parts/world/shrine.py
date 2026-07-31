"""CARD: shrine -- pray at a wayshrine for a rest boon (the world reacts to the traveller).

The wilds are full of places to FIND -- standing-stones, springs, old shrine-posts -- but until now
they were only text. A `shrine` room-field turns a chosen few into things you can USE: `pray` at a
wayshrine and its old blessing restores a share of your pools (HP/MP/power), then it falls quiet for
a good while so it is a boon on a journey, not an infinite fountain that trivialises attrition.

It is the non-combat, non-gather sibling of the gather node (parts.world.gather): a room-field, a
verb, and a per-PLAYER cooldown ticked on the world beat (`tick_shrines`, beside gather and zones).
A wayshrine restores a FRACTION of each pool's maximum, so it helps most when you are hurt and does
nothing when you are whole -- a rest stop, not a full heal on demand.

Inputs: a Session (its location + resources). Output: the line the traveller sees. Refuses cleanly
when there is no shrine here, or the shrine is still spent for this player.
"""

from __future__ import annotations

from parts.world.session import Session

# world-beats before a wayshrine's blessing renews for the player who used it
SHRINE_COOLDOWN = 40
# a wayshrine restores maximum // this of each pool -- a rest boon, not a full heal
_RESTORE_DIVISOR = 2
# the pools a wayshrine can mend, in the order they read
_POOLS = ("hp", "mp", "power")


def pray(session: Session) -> str:
    """`pray` -- take the boon of the current room's shrine, if it has one and has renewed. Restores
    a share of each pool toward its maximum. Fails cleanly with no shrine, or when it is spent."""
    from parts.world.world import WORLD

    room = WORLD.get(session.location)
    kind = room.get("shrine") if room else None
    if not kind:
        return "There is no shrine here to pray at."
    left = session.shrine_cooldowns.get(session.location, 0)
    if left > 0:
        return f"The shrine's blessing is spent for now; it will wake again ({left} beats)."

    restored: list[str] = []
    for pool in _POOLS:
        res = session.resources.get(pool)
        if res is None or res.current >= res.maximum:
            continue
        amount = max(1, res.maximum // _RESTORE_DIVISOR)
        before = res.current
        session.resources[pool] = res.heal(amount)
        gained = session.resources[pool].current - before
        if gained:
            restored.append(f"{gained} {pool.upper()}")
    session.shrine_cooldowns[session.location] = SHRINE_COOLDOWN
    boon = " and ".join(restored) if restored else "nothing (you are already whole)"
    return f"You rest at the wayshrine, and its old blessing restores {boon}."


def shrine_hint(location: str) -> str:
    """A one-line `look` hint for a room that holds a shrine, or "". Lets a passing traveller see
    the boon without a full `pray`, mirroring the gather node's hint."""
    from parts.world.world import WORLD

    room = WORLD.get(location)
    return "A wayshrine stands here; you could pray at it." if room and room.get("shrine") else ""


def tick_shrines(session: Session) -> str:
    """On the world beat, renew the player's spent shrines by one beat (drop ready ones). Silent:
    renewal needs no line. Returns '' so it composes into the beat like the other tickers."""
    for room in list(session.shrine_cooldowns):
        session.shrine_cooldowns[room] -= 1
        if session.shrine_cooldowns[room] <= 0:
            del session.shrine_cooldowns[room]
    return ""
