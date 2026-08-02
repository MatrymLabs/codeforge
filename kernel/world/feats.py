"""CARD: feats -- the deeds a hero has earned, derived from what they have already become.

An MMORPG gives a player long-term goals beyond the next level: milestones to chase and a record of
what they have done. This is that record -- FEATS -- built the derive-don't-store way (Architecture
Law: canonical facts persist, everything else recomputes). A feat is not a stored flag that could
drift; it is a truth read live from the character the player already IS: their level, their calling
and subjob, their sworn Order, their purse, their crown. So the ledger can never lie about a deed,
and it needs no new state to keep -- it simply reads the sheet and reports what it sees.

`feats` shows the whole ledger, earned and still-locked, so a player always has the next deed in
sight. Data-driven: FEATS is a table of (name, blurb, a predicate over the session), so a new deed
is one row. Adding a feat that needs a NEW fact (foes felled, rooms walked) is a later slice with
its own counter; every feat here rides a fact the game already persists.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple

from kernel.world.session import Session

_EMBER = 10_000  # cinders in one ember
_FORGEMARK = 1_000_000  # cinders in one forgemark


class Feat(NamedTuple):
    """One deed: its name, a one-line blurb, and a predicate that reads it live off the session."""

    name: str
    blurb: str
    earned: Callable[[Session], bool]


FEATS: tuple[Feat, ...] = (
    Feat("Called", "take up a calling", lambda s: bool(s.job)),
    Feat("Twin-Souled", "swear a second calling as a subjob", lambda s: bool(s.secondary_job)),
    Feat("Sworn", "join one of the four Orders", lambda s: bool(s.order)),
    Feat("Journeyman", "reach level 10", lambda s: s.level >= 10),
    Feat("Veteran", "reach level 50", lambda s: s.level >= 50),
    Feat("Master", "reach level 100", lambda s: s.level >= 100),
    Feat("Ascendant", "reach the level cap (255)", lambda s: s.level >= 255),
    Feat("Coinbearer", "hold an ember of wealth (10,000 cinders)", lambda s: s.coins >= _EMBER),
    Feat("Forgemarked", "hold a forgemark (1,000,000 cinders)", lambda s: s.coins >= _FORGEMARK),
    Feat("The Maker", "bear the crown of the world's Seed Owner", lambda s: s.rank == "owner"),
)


def earned_feats(session: Session) -> list[Feat]:
    """Every feat this character has earned, live off their current sheet."""
    return [feat for feat in FEATS if feat.earned(session)]


def feats(session: Session) -> str:
    """`feats` -- the hero's deed ledger: what they have earned, and what still awaits."""
    got = earned_feats(session)
    lines = [f"== Feats ({len(got)}/{len(FEATS)}) =="]
    for feat in FEATS:
        mark = "[x]" if feat in got else "[ ]"
        lines.append(f"  {mark} {feat.name} -- {feat.blurb}")
    if not got:
        lines.append("No deeds yet. Take up a calling and make your mark on the world.")
    else:
        # a friendly nudge toward the next unearned deed, if any
        nxt = next((f for f in FEATS if f not in got), None)
        if nxt is not None:
            lines.append(f"Next: {nxt.name} -- {nxt.blurb}.")
    return "\n".join(lines)
