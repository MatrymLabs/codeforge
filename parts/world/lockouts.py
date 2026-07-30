"""CARD: lockouts -- daily reset markers, so endgame rewards a return, not a grind (game).

The endgame's first lever against "infinitely farmable, no diminishing returns". A lockout is a
per-hero mark on a key (a boss, a daily) stamped with the UTC date it was claimed. A boss can still
be fought any number of times, but its BONUS pays only on the first kill of the day, then again
tomorrow: the reason to log in daily and the cap on farming a single foe for infinite reward.

State is canonical and per-hero: `session.lockouts[key] = "YYYY-MM-DD"`, persisted on the character
record beside quest state. The period boundary is a UTC date PASSED IN (no wall-clock in pure logic,
mirroring mail's sent_utc), so a test can name the day and a claim is deterministic.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from parts.world.session import Session


def today_utc() -> str:
    """The current UTC date as YYYY-MM-DD. Resolved at the call edge so pure logic never reads the
    wall clock; callers pass the result into claim/is_locked, and a test monkeypatches it."""
    return datetime.now(UTC).strftime("%Y-%m-%d")


def this_week_utc() -> str:
    """The current ISO year-week as 'YYYY-Www' (e.g. '2026-W31'). The weekly reset a raid rides on:
    its full reward pays once per week, then again next week. Resolved at the call edge like
    today_utc, so pure logic stays clock-free and a test can name the week."""
    year, week, _ = datetime.now(UTC).isocalendar()
    return f"{year}-W{week:02d}"


def is_locked(session: Session, key: str, day: str) -> bool:
    """True if this hero already claimed `key` on `day` (the bonus is spent until the day rolls)."""
    return session.lockouts.get(key) == day


def claim(session: Session, key: str, day: str) -> bool:
    """Claim `key` for `day`. Returns True on the FIRST claim of the day (the caller pays the bonus)
    and stamps it; False if it was already claimed today (the caller pays base only)."""
    if session.lockouts.get(key) == day:
        return False
    session.lockouts[key] = day
    return True


def serialize(lockouts: dict[str, str]) -> str:
    """A hero's lockout ledger as a compact JSON string for the character record ('' when empty)."""
    return json.dumps(lockouts, sort_keys=True) if lockouts else ""


def deserialize(raw: str) -> dict[str, str]:
    """Rebuild the ledger from its stored string. A blank or malformed value restores an empty
    ledger rather than crashing a login -- a lost lockout is forgiving, never a locked-out hero."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}
