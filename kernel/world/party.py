"""CARD: party -- the fellowship: a transient band of heroes who adventure as one.

The world was multiplayer in presence but solo in purpose: players shared rooms, never a cause. The
party is the first shared-purpose primitive -- a small, leader-led band with its own chat channel,
and the foundation the shared-combat, dungeon, and raid layers will build on.

Transient by design (a party is a moment, not a record). All party state lives in this module's own
registry keyed by player id, never in the database and never on the Session, so it dissolves cleanly
when a hero leaves or logs out, exactly like the afflictions it sits beside. One responsibility:
own who is banded with whom, and speak to a band. It reads live session presence (`SESSIONS`) and
delivers through the event bus (`events.announce_to`); it mutates no world state and persists none.

Extension points (documented, not built): shared combat/XP splitting hangs off `members_in_room`;
`party kick` and party-loot rules hang off the leader check; a guild is the persisted big sibling of
this transient primitive.
"""

from __future__ import annotations

from kernel.shelf.cohort import Cohort, CohortRegistry
from kernel.world.events import announce_to, push_channel, push_gmcp
from kernel.world.session import SESSIONS, display_name

#: The largest a party may grow. Five is the genre-standard small-group (dungeon) size; a raid tier
#: would be a separate, larger cohort, not a bigger party.
MAX_PARTY = 5

# Membership is the Hardware Store's transient cohort primitive (kernel/shelf/cohort): party bolts
# invites, chat, and logout cleanup onto it. `_REGISTRY` owns who is banded with whom; `_INVITES`
# maps an invited player id to the set of inviter ids who have a pending offer out to them.
_REGISTRY = CohortRegistry(MAX_PARTY)
_INVITES: dict[str, set[str]] = {}


def party_of(player_id: str) -> Cohort | None:
    """The party a hero belongs to, or None if they run alone. The one read other systems use."""
    return _REGISTRY.cohort_of(player_id)


def roster_frame(band: Cohort) -> dict[str, object]:
    """The Char.Party GMCP payload for a band: {members, leader, size}, display-named. The one shape
    both the state report (gmcp.party_report) and the live push below emit, so they never drift."""
    return {
        "members": [display_name(m) for m in band.members],
        "leader": display_name(band.leader),
        "size": len(band.members),
    }


def _push_roster(band: Cohort) -> None:
    """Push the fresh roster to every member's client the instant the band changes (not on their
    next tick), so a party panel stays live for everyone, not just whoever just acted."""
    push_gmcp(band.members, "Char.Party", roster_frame(band))


def _clear_party(player_ids: list[str]) -> None:
    """Push an empty Char.Party to players who just left or were disbanded, clearing their panel."""
    push_gmcp(player_ids, "Char.Party", {})


def members_in_room(player_id: str, room: str) -> list[str]:
    """This hero's party-mates who are present in `room` (the seam shared combat/XP will read). An
    empty list when they are unpartied or alone here, so a caller never special-cases 'no party'."""
    band = _REGISTRY.cohort_of(player_id)
    if band is None:
        return [m for m in [player_id] if SESSIONS.get(player_id) and _here(player_id, room)]
    return [m for m in band.members if _here(m, room)]


def _here(player_id: str, room: str) -> bool:
    session = SESSIONS.get(player_id)
    return session is not None and session.location == room


def invite(actor: str, target_name: str) -> str:  # noqa: PLR0911
    """Offer `target_name` a place in the actor's band (forming one, with the actor as leader, if
    they run alone). Fails loud (a returned message) on a self-invite, an offline target, a target
    already banded, or a full party."""
    target = target_name.strip().lower()
    if not target:
        return "Invite whom? (party invite <player>)"
    if target == actor:
        return "You cannot invite yourself."
    if SESSIONS.get(target) is None:
        return f"No one named '{target}' is here to invite."
    if _REGISTRY.cohort_of(target) is not None:
        return f"{display_name(target)} is already in a party."
    band = _REGISTRY.cohort_of(actor)
    if band is None:
        band = _REGISTRY.form(actor)  # the invite forms the band, with the actor leading
    elif band.leader != actor:
        return "Only the party leader may invite."
    if _REGISTRY.is_full(band):
        return f"Your party is full ({MAX_PARTY})."
    _INVITES.setdefault(target, set()).add(actor)
    announce_to(
        [target],
        f"\n{display_name(actor)} invites you to join their party. (party join {actor})",
    )
    return f"You invite {display_name(target)} to your party."


def join(actor: str, inviter_name: str) -> str:
    """Accept a pending invitation from `inviter_name` and join their band. Fails loud on no such
    invite, an inviter who is offline or no longer in a party, or a party since filled."""
    inviter = inviter_name.strip().lower()
    if not inviter:
        return "Join whose party? (party join <player>)"
    if _REGISTRY.cohort_of(actor) is not None:
        return "You are already in a party; leave it first."
    if inviter not in _INVITES.get(actor, set()):
        return f"You have no invitation from '{inviter}'."
    band = _REGISTRY.cohort_of(inviter)
    if band is None or SESSIONS.get(inviter) is None:
        _INVITES.get(actor, set()).discard(inviter)
        return f"{display_name(inviter)}'s party is no longer forming."
    if _REGISTRY.is_full(band):
        return f"{display_name(inviter)}'s party is full ({MAX_PARTY})."
    _REGISTRY.add(band, actor)
    _INVITES.pop(actor, None)  # accepting one offer clears all pending offers to this hero
    announce_to(band.members, f"\n{display_name(actor)} joins the party.", exclude=actor)
    _push_roster(band)  # every member's panel, including the newcomer, updates at once
    return f"You join {display_name(inviter)}'s party."


def leave(actor: str) -> str:
    """Leave your band. If you were the leader and others remain, leadership passes to the next
    member; if you were the last, the party disbands. A no-op message when you run alone."""
    if _REGISTRY.cohort_of(actor) is None:
        return "You are not in a party."
    band, was_leader = _REGISTRY.leave(actor)
    _clear_party([actor])  # the leaver's own panel empties either way
    if band is None:
        return "You leave the party. It disbands."
    announce_to(band.members, f"\n{display_name(actor)} leaves the party.")
    if was_leader:
        announce_to(band.members, f"{display_name(band.leader)} now leads the party.")
    _push_roster(band)  # the remaining members see the smaller roster (and any new leader) at once
    return "You leave the party."


def disband(actor: str) -> str:
    """Leader-only: dissolve the whole band for everyone. Fails loud if the actor is unpartied or
    not the leader."""
    band = _REGISTRY.cohort_of(actor)
    if band is None:
        return "You are not in a party."
    if band.leader != actor:
        return "Only the party leader may disband the party."
    members = _REGISTRY.disband(band)
    announce_to(members, "\nThe party disbands.", exclude=actor)
    _clear_party(members)  # every former member's party panel empties at once
    return "You disband the party."


def party_say(actor: str, message: str) -> str:
    """Speak on the party channel. Fails loud when unpartied or the message is empty."""
    band = _REGISTRY.cohort_of(actor)
    if band is None:
        return "You are not in a party. (party invite <player> to form one)"
    text = message.strip()
    if not text:
        return "Say what to the party? (psay <message>)"
    announce_to(band.members, f"\n[Party] {display_name(actor)}: {text}", exclude=actor)
    push_channel(band.members, "party", display_name(actor), text)  # structured, for a chat pane
    return f"[Party] You: {text}"


def render_party(actor: str) -> str:
    """The read-only roster: who is in the band, the leader marked, and who is currently online."""
    band = _REGISTRY.cohort_of(actor)
    if band is None:
        return "You are not in a party. (party invite <player> to form one)"
    lines = [f"Your party ({len(band.members)}/{MAX_PARTY}):"]
    for member in band.members:
        mark = " (leader)" if member == band.leader else ""
        here = "" if SESSIONS.get(member) is not None else "  [offline]"
        lines.append(f"  {display_name(member)}{mark}{here}")
    return "\n".join(lines)


def on_disconnect(player_id: str) -> None:
    """Logout cleanup: a hero who leaves the world leaves their party (with leadership handoff), and
    any pending invitations to or from them are dropped. Called from the gateway teardown so a party
    never carries a ghost. Silent (no return): the disconnect path is not a command."""
    if _REGISTRY.cohort_of(player_id) is not None:
        leave(player_id)
    _INVITES.pop(player_id, None)  # drop invites TO the leaver
    for pending in _INVITES.values():  # drop invites FROM the leaver
        pending.discard(player_id)


def _reset() -> None:
    """Clear all party state. For tests only, so one test's bands never leak into the next."""
    _REGISTRY.clear()
    _INVITES.clear()
