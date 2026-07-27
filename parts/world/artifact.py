"""CARD: artifact -- the Maker's Signet, the Seed Owner's legendary bond to the world.

Part III of the Player Experience campaign: the Creator Artifact. A world has one maker, and the
maker bears one relic -- the MAKER'S SIGNET, a ring of cooled ember struck at the world's first
kindling. It is not an object you carry; it is bound to the hand that shaped the world, so it
answers the campaign's absolutes for free: only the Seed Owner bears it, and it cannot be traded,
stolen, copied, destroyed, or dropped on death, because it was never a takeable thing: it is the
owner's authority made legendary.

Where the Creator's Workshop gathers the maker's tools in one place (parts.world.creator_workshop),
the Signet carries a WINDOW to them ANYWHERE: `signet` opens the Creator Interface from any room,
and `signet <function>` channels a workshop tool remotely (today the read-only lens: the world's
shape and its live play). It leaves world state untouched; mutating still happens through the
validated apply-path. A non-owner who names it is simply told the signet does not know them --
there is nothing here to take.
"""

from __future__ import annotations

from parts.world import creator_workshop
from parts.world.session import Session

# What the Signet channels remotely: a keyword -> (label, the report it opens). Read-only functions
# only, for now; the mutating create/publish tools stay station-bound to the Workshop itself.
_FUNCTIONS: dict[str, tuple[str, str]] = {
    "survey": ("Survey", "the world's shape -- rooms, zones, inhabitants, scale"),
    "activity": ("Activity", "the world's live play -- who is exploring, and where"),
}


def bears_signet(session: Session) -> bool:
    """Whether this session bears the Maker's Signet -- the Seed Owner, and only ever the owner."""
    return creator_workshop.is_seed_owner(session)


def signet(session: Session, arg: str) -> str:
    """`signet [function]` -- the Creator Interface, borne anywhere. Bare opens the interface; a
    function channels a workshop tool remotely. Refuses anyone but the owner."""
    if not bears_signet(session):
        return "You bear no such relic. The Maker's Signet does not know your hand."
    word = arg.strip().lower()
    if not word:
        return _interface()
    if word not in _FUNCTIONS:
        opts = ", ".join(_FUNCTIONS)
        return f"The Signet holds no power called '{word}'. It offers: {opts}."
    if word == "survey":
        return creator_workshop.world_survey(session)
    return creator_workshop.live_activity(session)


def _interface() -> str:
    """The Creator Interface the Signet opens: the maker's legend and the powers at hand."""
    lines = [
        "== The Maker's Signet ==",
        "The ring warms; the world lays itself open to you. From anywhere, you may:",
    ]
    for word, (label, blurb) in _FUNCTIONS.items():
        lines.append(f"  signet {word:<9} {label} -- {blurb}")
    lines.append("(The forging tools -- create, publish -- still await in the Workshop itself.)")
    return "\n".join(lines)
