"""CARD: allocate -- spend the attribute points a level-up grants (build your hero).

Leveling grants attribute points (`STAT_POINTS_PER_LEVEL` per PLvl); this card is where a player
spends them. `allocate <stat> [n]` puts points into one of the six attributes, up to a per-attribute
ceiling that grows with level (`MAX_ALLOC_PER_STAT_PER_LEVEL` x levels gained). The points spent are
the canonical fact (persisted); the resulting StatBlock recomputes from the job base plus the
allocation (jobs.build_stats), so build customization survives a job change and a restart alike.

Derive-don't-store: unspent points are DERIVED (earned by level minus spent), never a stored balance
that could drift. The attribute boost is real in play at once -- strength lifts your strikes,
stamina and magic lift your HP and MP -- so a build decision is felt, not cosmetic.
"""

from __future__ import annotations

import json

from kernel.world.progression import MAX_ALLOC_PER_STAT_PER_LEVEL, STAT_POINTS_PER_LEVEL
from kernel.world.resources import Resource
from kernel.world.session import Session

# The six attributes a point may be spent on (the StatBlock's members).
ATTRIBUTES = ("strength", "speed", "stamina", "magic", "wisdom", "luck")


def earned(level: int) -> int:
    """Total attribute points earned by reaching a level (none at level 1)."""
    return STAT_POINTS_PER_LEVEL * max(0, level - 1)


def spent(session: Session) -> int:
    """Points already put into attributes."""
    return sum(session.allocated.values())


def unspent(session: Session) -> int:
    """Points a character still has to spend."""
    return earned(session.level) - spent(session)


def per_stat_cap(level: int) -> int:
    """The most points one attribute may hold at a level (keeps a build from dumping everything)."""
    return MAX_ALLOC_PER_STAT_PER_LEVEL * max(0, level - 1)


def allocate(session: Session, arg: str) -> str:
    """`allocate <stat> [n]` -- spend n (default 1) into an attribute; bare `allocate` shows the
    pool. Fails loud on no calling, a bad attribute, too few points, or the per-stat cap."""
    if session.stats is None:
        return "You have no calling yet. Type JOBS before you allocate points."
    words = arg.split()
    if not words:
        return _pool(session)
    stat = words[0].lower()
    if stat not in ATTRIBUTES:
        return f"'{stat}' is not an attribute. Choose from: {', '.join(ATTRIBUTES)}."
    n = 1
    if len(words) > 1:
        if not words[1].isdigit() or int(words[1]) < 1:
            return "Allocate how many? Try: allocate <stat> <n> (a positive number)."
        n = int(words[1])
    left = unspent(session)
    if n > left:
        return f"You have only {left} point{'s' if left != 1 else ''} to spend."
    already = session.allocated.get(stat, 0)
    cap = per_stat_cap(session.level)
    if already + n > cap:
        return f"At most {cap} into {stat} at level {session.level} (you have {already} there)."

    session.allocated[stat] = already + n
    _apply(session, stat, n)
    if session.named:
        from kernel.world.characters import save_character

        save_character(session)
    remaining = unspent(session)
    return f"You steel your {stat} (+{n}). {remaining} point{'s' if remaining != 1 else ''} left."


def _apply(session: Session, stat: str, n: int) -> None:
    """Rebuild the StatBlock with the new allocation, and grow HP/MP when the point went into
    stamina/magic (so a defensive build is felt immediately, not only next level-up)."""
    from kernel.world.jobs import build_stats

    session.stats = build_stats(session.job, session.allocated)
    if stat == "stamina":
        hp = session.resources["hp"]
        session.resources["hp"] = Resource("hp", hp.current + n, hp.maximum + n)
    elif stat == "magic":
        mp = session.resources["mp"]
        session.resources["mp"] = Resource("mp", mp.current + n, mp.maximum + n)


def _pool(session: Session) -> str:
    """The bare `allocate` view: unspent points, the per-stat cap, and each attribute's standing."""
    assert session.stats is not None
    lines = [
        f"Attribute points: {unspent(session)} unspent "
        f"({STAT_POINTS_PER_LEVEL}/level; up to {per_stat_cap(session.level)} per attribute now)."
    ]
    for attr in ATTRIBUTES:
        put = session.allocated.get(attr, 0)
        mark = f"  (+{put})" if put else ""
        lines.append(f"  {attr}: {session.stats.get(attr).base}{mark}")
    lines.append("Spend with: allocate <stat> [n]")
    return "\n".join(lines)


def serialize(session: Session) -> str:
    """The allocation as JSON for persistence (or "" when nothing is spent)."""
    return json.dumps(session.allocated, sort_keys=True) if session.allocated else ""


def restore(session: Session, raw: str) -> None:
    """Load a saved allocation onto a session (before its stats are built). Tolerates a blank or an
    unknown attribute (a cross-seed / legacy save), keeping only real attributes."""
    session.allocated = {}
    if not raw:
        return
    saved = json.loads(raw)
    session.allocated = {k: int(v) for k, v in saved.items() if k in ATTRIBUTES and int(v) > 0}
