"""CARD: creator_workshop -- the Creator's Workshop: a protected admin dimension, owner-only.

Every generated CodeForge world carries one canonical, private place the players never see: the
Creator's Workshop, reached through the Creator's Door inside the Grand Library. It is the in-game
half of the Creator Experience (its outside-the-game twin is the Creator Console): an administrative
space represented THROUGH the game itself, where the world's owner shapes NPCs, quests, items, and
difficulty without editing files or touching a terminal.

This module is the foundation the workshop's stations will later hang on: it PLACES the canonical
rooms into any world and it GUARDS the barrier. The rules the prompt makes absolute:

  - The Grand Library is a normal, discoverable room (every world links it to the spawn).
  - The Creator's Door is CONCEALED: it is not one of the Library's listed exits, so players cannot
    discover, observe, or reveal it. The owner crosses by naming it (`go door`), not by chance.
  - Only the authenticated Seed Owner (the `owner` crown) may cross. Everyone else, whether they
    guess the door or try to teleport past it, receives exactly:
        "The barrier does not acknowledge your presence."
  - The Workshop is an isolated instance: its only tie to the world is the concealed door and a
    plain `out` exit back to the Library, so no ordinary movement or teleport reaches it.

State is data and text is a projection (Architecture Law 1): this module only assembles rooms and
answers the barrier question; the tick performs the crossing. The barrier check reads `session.rank`
directly (the Seed Owner holds the top crown) rather than importing `ranks`, which would form an
import cycle -- `ranks` may guard teleport by importing THIS module instead.
"""

from __future__ import annotations

from parts.world.seed import Room
from parts.world.session import Session

# --- Canonical labels (frozen identity strings; never restyle -- persisted contract) ------------
GRAND_LIBRARY = "grand_library"
CREATOR_WORKSHOP = "creator_workshop"

# The exact refusal the barrier gives everyone who is not the Seed Owner. Frozen by the prompt.
_BARRIER_REFUSAL = "The barrier does not acknowledge your presence."

# The words that name the concealed Creator's Door out of the Grand Library. Kept OUT of the room's
# `exits` so the door never renders; a player cannot discover it, only the owner (who is told) names
# it. "door" is safe here because door_destination only fires while standing in the Grand Library.
_DOOR_WORDS = frozenset({"door"})

# The rooms that live behind the barrier. Membership is what teleport and any future reveal-vector
# must refuse for non-owners.
WORKSHOP_ROOMS = frozenset({CREATOR_WORKSHOP})


def is_workshop_room(room_id: str) -> bool:
    """Whether a room lives behind the barrier (the isolated administrative instance)."""
    return room_id in WORKSHOP_ROOMS


def is_seed_owner(session: Session) -> bool:
    """Whether this session is the authenticated Seed Owner: the authority the barrier honours.

    The Seed Owner holds the `owner` crown (the top rank); a wizard is not enough, by design."""
    return session.rank == "owner"


def barrier_refusal() -> str:
    """The exact message the barrier gives anyone who is not the Seed Owner."""
    return _BARRIER_REFUSAL


def door_destination(location: str, word: str) -> str | None:
    """The room the Creator's Door opens onto if `word` names it from `location`, else None.

    Returns the Workshop only when standing in the Grand Library and naming the concealed door; None
    everywhere else, so normal movement handles every other word. This never checks authority -- the
    caller consults `is_seed_owner` and either crosses or returns `barrier_refusal()`; the door is
    NAMEABLE by anyone, but CROSSABLE only by the owner (a guessing player still meets the wall)."""
    if location == GRAND_LIBRARY and word in _DOOR_WORDS:
        return CREATOR_WORKSHOP
    return None


def install_workshop(world: dict[str, Room]) -> None:
    """Place the canonical Grand Library and Workshop into `world`, in place and idempotent.

    The Grand Library links to the world's spawn (its first room) with a `library` noun exit both
    ways, so every world -- whatever its geography -- makes the Library reachable ("walk into the
    Grand Library"). The Workshop is added as an isolated instance: reachable ONLY across the
    concealed door (never wired into `exits`) with a plain `out` exit back to the Library so the
    owner can leave. Called during world assembly, after the seed and generators, before the link
    audit -- so the new rooms pass the same gates as authored ones."""
    if GRAND_LIBRARY in world:  # idempotent: never place the Library twice
        return
    if not world:  # a world with no rooms has no spawn to anchor the Library to
        raise WorkshopError("cannot install the Creator's Workshop into an empty world")
    spawn = next(iter(world))

    world[GRAND_LIBRARY] = Room(
        name="The Grand Library",
        desc=(
            "Ten thousand shelves spiral up into shadow, every ledger the world has ever kept "
            "waiting to be read. The air is warm with lamp oil and old paper. A quiet place; the "
            "world hums somewhere below."
        ),
        exits={"library": spawn, "out": spawn},
    )
    world[CREATOR_WORKSHOP] = Room(
        name="The Creator's Workshop",
        desc=(
            "A wide, bright workshop that answers to no map. Drafting tables, a world atlas under "
            "glass, a forge banked and waiting, shelves of blueprints and ideas. This is "
            "where the world is shaped. The Grand Library lies back through the door (`out`)."
        ),
        exits={"out": GRAND_LIBRARY},
    )
    # Make the Library discoverable from spawn (a plain, listed noun exit both ways).
    world[spawn]["exits"].setdefault("library", GRAND_LIBRARY)


class WorkshopError(ValueError):
    """The Creator's Workshop could not be installed (e.g. into an empty world). Fails loud."""
