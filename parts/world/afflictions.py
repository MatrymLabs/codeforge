"""CARD: afflictions -- harmful statuses the PLAYER suffers: damage-over-time and daze.

The foe side of combat already had status effects a player INFLICTS (a `brand` burn, a `daze` that
skips a foe's strikes); the player side had only buffs (barrier, analyzed). This is the mirror: the
boss's venom that saps you each beat, the stunning blow that costs you an action. It is the
substrate a telegraphed boss special needs to actually threaten a hero -- the prerequisite for
richer encounter mechanics.

Player afflictions age on the WORLD BEAT (like foe burns via tick_burns), not the combat clock, so
they progress whether or not you keep swinging (`tick_afflictions`, wired beside the other tickers).
A damage-over-time never fells you on its own (HP floored at 1) -- it wears you down for the foe's
blow to finish, the same discipline the foe-side burn keeps. A daze blocks your offensive actions
until it wears off. `maybe_inflict` is the door an NPC blow rolls to lay one on you.
"""

from __future__ import annotations

import random

from parts.world.session import Session

#: Default beats a damage-over-time affliction lasts. A boss may name its own.
DOT_TICKS = 3

#: Runtime RNG for the infliction roll: game variety, not security. Tests seed or replace it.
_AFFLICT_RNG = random.Random()  # nosec B311 -- combat variety, not cryptographic


def apply_dot(session: Session, name: str, damage: int, ticks: int = DOT_TICKS) -> None:
    """Lay (or refresh) a damage-over-time affliction on the player -- poison, bleed, a lingering
    burn. It saps `damage` HP each world beat for `ticks` beats. A fresh application refreshes it
    rather than stacking, so being hit again resets the clock, never doubles the damage."""
    session.afflictions[name] = {"damage": max(1, damage), "ticks": max(1, ticks)}


def apply_regen(session: Session, name: str, heal: int, ticks: int = DOT_TICKS) -> None:
    """Lay (or refresh) a heal-over-time BOON on a hero: it restores `heal` HP each world beat for
    `ticks` beats (capped at maximum). The friendly mirror of `apply_dot`. It lives in
    `session.regens`, NOT `session.afflictions`, so `cleanse` (which purges harm) never strips it."""
    session.regens[name] = {"heal": max(1, heal), "ticks": max(1, ticks)}


def tick_regens(session: Session) -> str:
    """On the world beat: restore each heal-over-time boon (capped at max HP), age it, drop the
    expired. Returns the lines the player sees, or ''. The mirror of `tick_afflictions`."""
    lines: list[str] = []
    for name in list(session.regens):
        boon = session.regens[name]
        hp = session.resources.get("hp")
        if hp is not None and hp.current < hp.maximum:
            before = hp.current
            session.resources["hp"] = hp.heal(boon["heal"])
            gained = session.resources["hp"].current - before
            hp = session.resources["hp"]
            lines.append(f"The {name} mends you for {gained}. (HP {hp.current}/{hp.maximum})")
        boon["ticks"] -= 1
        if boon["ticks"] <= 0:
            del session.regens[name]
            lines.append(f"The {name} fades.")
    return "\n".join(lines)


def apply_daze(session: Session, beats: int) -> None:
    """Daze the player for `beats` world beats: their offensive actions are lost until it wears off.
    Refreshes to the LONGER of current and new duration, so a fresh daze never shortens a stun."""
    session.dazed = max(session.dazed, max(1, beats))


def is_dazed(session: Session) -> bool:
    """True while the player is dazed and cannot take an offensive action."""
    return session.dazed > 0


def cleanse(session: Session) -> list[str]:
    """Purge every affliction from a hero at once -- each damage-over-time AND the daze. Returns the
    names cleared (sorted, 'daze' included when it was up), or [] when nothing ailed them. The
    support role's reactive counter to a boss's venom and stuns (the `cleanse` ability)."""
    cleared = sorted(session.afflictions)
    session.afflictions.clear()
    if session.dazed > 0:
        session.dazed = 0
        cleared.append("daze")
    return cleared


def maybe_inflict(session: Session, inflicts: dict | None) -> str | None:
    """Roll an NPC's `inflicts` spec on a landed blow and, on a hit, lay the affliction on the
    player. Returns the line the player sees, or None (no spec, or the chance roll missed). The
    spec: {status, chance?, damage?, ticks?, beats?} -- status 'daze' stuns, any other is a DoT of
    that name. A None/empty spec is a clean no-op, so combat can call it unconditionally. The roll
    draws from the module `_AFFLICT_RNG` (tests monkeypatch it for an exact outcome)."""
    if not inflicts:
        return None
    chance = int(inflicts.get("chance", 1))
    if chance > 1 and _AFFLICT_RNG.randrange(chance) != 0:
        return None  # the blow lands, but the affliction does not take this time
    return inflict(session, inflicts)


def inflict(session: Session, inflicts: dict) -> str:
    """Lay an affliction on the player UNCONDITIONALLY (no chance roll), from an `inflicts` spec --
    the door a guaranteed effect uses (a boss's telegraphed special always connects). `status`
    'daze' stuns for `beats`; any other name is a damage-over-time of that name."""
    status = str(inflicts["status"])
    if status == "daze":
        apply_daze(session, int(inflicts.get("beats", 1)))
        return "You reel, dazed!"
    damage, ticks = int(inflicts.get("damage", 1)), int(inflicts.get("ticks", DOT_TICKS))
    apply_dot(session, status, damage, ticks)
    return f"You are afflicted with {status}!"


def tick_afflictions(session: Session) -> str:
    """On the world beat: sap each damage-over-time from the player, age it, drop the expired; and
    age the daze. A DoT never fells the player on its own -- HP is floored at 1, so the foe's blow
    lands the finishing hit, not an untended tick. Returns the lines the player sees, or ''."""
    lines: list[str] = []
    for name in list(session.afflictions):
        aff = session.afflictions[name]
        hp = session.resources.get("hp")
        if hp is not None and hp.current > 1:
            dmg = min(aff["damage"], hp.current - 1)  # floor at 1: a DoT never kills
            session.resources["hp"] = hp.damage(dmg)
            hp = session.resources["hp"]
            lines.append(f"The {name} saps you for {dmg}. (HP {hp.current}/{hp.maximum})")
        aff["ticks"] -= 1
        if aff["ticks"] <= 0:
            del session.afflictions[name]
            lines.append(f"The {name} fades.")
    if session.dazed > 0:
        session.dazed -= 1
        if session.dazed == 0:
            lines.append("You shake off the daze.")
    return "\n".join(lines)


def render_afflictions(session: Session) -> str:
    """A one-line summary of what ails the player (for a status view), or '' when hale. Names each
    damage-over-time with its beats left, and the daze if it holds."""
    parts = [f"{name} ({aff['ticks']})" for name, aff in sorted(session.afflictions.items())]
    if session.dazed > 0:
        parts.append(f"dazed ({session.dazed})")
    return "Afflicted: " + ", ".join(parts) if parts else ""
