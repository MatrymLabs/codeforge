"""CARD: friends -- a hero's personal friends list (who to look for when you log in).

The social layer's quiet corner. Party and guild are shared groups with a purpose; a friends list
is one hero's own private roster of people worth keeping track of. It is one-directional by design:
your list is yours, and adding someone does not enlist them into anything or touch their list. Its
only power is sight, `friends` shows which of the people you care about are online right now, so a
returning hero can see at a glance who is around to adventure with.

Stored as a comma-joined string of lowercase labels on the character row (serialize/restore mirror
the professions/reputation columns), so the roster survives a logout. It moves no world state and
holds no auth; a name is only added after the store confirms a real hero wears it.
"""

from __future__ import annotations

from kernel.world.session import SESSIONS, Session, display_name

MAX_FRIENDS = 100  # the most names one hero may keep (bounds unbounded list growth)

# kernel.world.characters is imported LAZILY inside the functions that need it: characters imports
# THIS module (for serialize/restore of the friends column), so a top-level import here would form a
# cycle. serialize/restore touch only the session, so they carry no such import.


def _character_exists(name: str) -> bool:
    """True if `name` is a real saved hero (a friend may be offline, so we check the store, not who
    is logged in)."""
    from kernel.world.characters import _default_store  # noqa: PLC0415

    return _default_store().find(name) is not None


def add(session: Session, arg: str) -> str:
    """`friend add <player>`: add a real hero to your list. Fails loud on a missing name, yourself,
    an unknown hero, a duplicate, or a full list."""
    target = arg.strip().lower()
    if not target:
        return "Befriend whom? (friend add <player>)"
    if target == session.player_id:
        return "You are already your own best company."
    if target in session.friends:
        return f"{display_name(target)} is already on your friends list."
    if len(session.friends) >= MAX_FRIENDS:
        return f"Your friends list is full ({MAX_FRIENDS}); remove someone first."
    if not _character_exists(target):
        return f"There is no hero named '{target}' to befriend."
    from kernel.world.characters import save_character  # noqa: PLC0415

    session.friends.append(target)
    save_character(session)
    return f"You add {display_name(target)} to your friends."


def remove(session: Session, arg: str) -> str:
    """`friend remove <player>`: drop a name from your list. Refused if it was never there."""
    target = arg.strip().lower()
    if target not in session.friends:
        return f"{display_name(target) if target else 'Whom'} is not on your friends list."
    from kernel.world.characters import save_character  # noqa: PLC0415

    session.friends.remove(target)
    save_character(session)
    return f"You remove {display_name(target)} from your friends."


def render(session: Session) -> str:
    """The friends list, each marked online or offline, online first so returning heroes see who is
    around at a glance."""
    if not session.friends:
        return "Your friends list is empty. (friend add <player>)"
    online = sorted(n for n in session.friends if n in SESSIONS)
    offline = sorted(n for n in session.friends if n not in SESSIONS)
    lines = [f"Your friends ({len(online)}/{len(session.friends)} online):"]
    lines += [f"  * {display_name(n)} (online)" for n in online]
    lines += [f"    {display_name(n)} (offline)" for n in offline]
    lines.append("(friend add <player>, friend remove <player>)")
    return "\n".join(lines)


def serialize(session: Session) -> str:
    """A hero's friends as a compact persisted string: lowercase labels, comma-joined. Empty for a
    hero who has befriended no one."""
    return ",".join(session.friends)


def restore(session: Session, blob: str) -> None:
    """Rebuild the friends list from `serialize`'s string. Blank entries are dropped (a forgiving
    restore); order is preserved."""
    session.friends = [name for name in blob.split(",") if name]
