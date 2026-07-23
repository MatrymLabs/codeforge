"""CARD: ranks -- authority, and the wizard verbs it makes legal.

Capability without authorization is a bug. Ranks order power
(player < wizard < owner); the engine tick checks rank BEFORE any
@-verb runs. Ranks live on the session and persist in the character
record, so authority survives restarts.

Bootstrap rule: the first crown is granted from the host shell
(python3 -m parts.world.characters grant <name> owner). Physical access
to the machine is the one authority the engine cannot outrank.
"""

from collections.abc import Sequence

from parts.world.characters import save_character
from parts.world.events import SHUTDOWN, announce, broadcast
from parts.world.session import SESSIONS, Session, display_name
from parts.world.world import WORLD

# The '@'-verbs this router handles directly. The rest of the admin verbs live on the command
# spine (@sg, @forge, @arch, ...); wizard_command receives them so its "known verbs" listing is
# the full set, derived, never a hand-kept list that omits half the surface.
_LEGACY_WIZARD_VERBS = ("@teleport", "@grant", "@shutdown")

RANK_ORDER = {"player": 0, "wizard": 1, "owner": 2}


def has_rank(session: Session, needed: str) -> bool:
    return RANK_ORDER.get(session.rank, 0) >= RANK_ORDER[needed]


def teleport(session: Session, word: str) -> str:
    """Wizard movement: anywhere, instantly, witnessed as vanish/appear."""
    room = word.strip().lower()
    if room not in WORLD:
        return f"There is no room labeled '{room}'."
    me = display_name(session.player_id)
    announce(session.location, f"{me} vanishes.", exclude=session.player_id)
    session.location = room
    announce(room, f"{me} appears from nowhere.", exclude=session.player_id)
    return f"You step between places.\nYou are now in: {WORLD[room]['name']}"


def grant(session: Session, words: str) -> str:
    """Owner verb: crown or demote a connected player. Persists."""
    parts = words.split()
    if len(parts) != 2:
        return "Usage: @grant <player> <rank>   (ranks: player, wizard, owner)"
    target_name, rank = parts
    if rank not in RANK_ORDER:
        return f"'{rank}' is not a rank. Ranks: player, wizard, owner."
    target = SESSIONS.get(target_name)
    if target is None:
        return f"No one called {display_name(target_name)} is connected."
    target.rank = rank
    save_character(target)
    announce(
        target.location,
        f"{display_name(target_name)} is invested with the rank of {rank}.",
        exclude=session.player_id,
    )
    return f"{display_name(target_name)} is now rank: {rank}."


def shutdown_world(session: Session) -> str:
    """Owner verb: save every named soul, tell the world, stop the server."""
    broadcast("The world is going to sleep. Your deeds are remembered.")
    for player in SESSIONS.values():
        save_character(player)
        player.alive = False
    hook = SHUTDOWN.get("hook")
    if hook is not None:
        hook()
    return "The world sleeps."


def wizard_command(session: Session, raw: str, spine_admin_verbs: Sequence[str] = ()) -> str:
    """Route the legacy @-verbs this module owns. Authorization happens HERE, before any verb
    runs. The spine's ADMIN verbs are dispatched upstream; they're passed in only so an unknown
    verb's "known" listing names the full admin surface instead of this module's slice of it."""
    verb, _, rest = raw.partition(" ")
    if verb == "@teleport":
        if not has_rank(session, "wizard"):
            return "You lack the authority for that."
        return teleport(session, rest)
    if verb == "@grant":
        if not has_rank(session, "owner"):
            return "You lack the authority for that."
        return grant(session, rest)
    if verb == "@shutdown":
        if not has_rank(session, "owner"):
            return "You lack the authority for that."
        return shutdown_world(session)
    known = sorted({*_LEGACY_WIZARD_VERBS, *spine_admin_verbs})
    return f"Unknown wizard verb. Known: {', '.join(known)}."
