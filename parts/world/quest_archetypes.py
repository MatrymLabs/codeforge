"""CARD: quest_archetypes -- the data-driven catalog of quest ARCHETYPES the world generates.

The world grows quests from GENERATORS, not one-offs: a bounty per foe, a cull per zone-and-kind, a
forage per node, a tale per zone, one main road. This is the LIBRARY those generators belong to --
one record per archetype naming its purpose, narrative role, gameplay loop, success, rewards, and
replay value, plus the predicate that recognises a live quest as a member. It turns an ad-hoc set
of generators into a legible, extensible framework: a new archetype is a new record here, and the
completeness test proves every quest a booted world posts classifies to exactly one of them (so no
archetype ever ships uncatalogued). Data, not behavior -- the generators stay where they live;
this names and organises them. `classify(quest_id)` maps any quest to its archetype key.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from parts.world.bounties import is_bounty
from parts.world.cull import is_cull
from parts.world.delivery import is_delivery
from parts.world.errands import is_errand
from parts.world.forage import is_forage
from parts.world.spine import is_spine
from parts.world.storylines import is_storyline

AUTHORED = "authored"  # the fallback: hand-written arcs (quest.yaml) and the built-in contract


@dataclass(frozen=True)
class Archetype:
    """One quest archetype: what it is FOR, how it PLAYS, and how a live quest is recognised as one.

    The narrative/design fields are the same the design doc (docs/quest_archetypes.md) records, kept
    here beside the code so the catalog and the doc cannot drift. `member` is the generator's own
    `is_<x>` predicate; `scope` names what the generator iterates to reach volume."""

    key: str  # stable slug, e.g. "cull"
    name: str  # display name, e.g. "Cull Contract"
    purpose: str  # why it exists in the world
    narrative_role: str  # what it says about the place
    loop: str  # the moment-to-moment gameplay loop
    success: str  # the win condition
    rewards: str  # what completing it grants
    replay: str  # its replay value (one-shot / repeatable / campaign)
    scope: str  # what the generator iterates over to reach volume
    member: Callable[[str], bool]  # recognises a live quest id as this archetype


# The SHIPPED archetypes, in rough player-progression order. Order matters: `classify` returns the
# first match, so more specific predicates (spine before storyline) must precede broader ones.
CATALOG: tuple[Archetype, ...] = (
    Archetype(
        key="spine",
        name="The Main Road",
        purpose="Give the sprawling world a guided through-line from the meadow to the endgame.",
        narrative_role="The campaign spine the side-content hangs on: where the world wants you.",
        loop="Arrive in each zone in level order; the road ticks onward and names the next region.",
        success="Reach the final zone.",
        rewards="A large XP capstone scaled to the endgame zone.",
        replay="Campaign: one per world, walked once.",
        scope="the whole zone set, ordered by level",
        member=is_spine,
    ),
    Archetype(
        key="storyline",
        name="Zone Tale",
        purpose="Give every zone a small three-beat narrative woven from its own geography.",
        narrative_role="The region's story: its dungeon, its terror, its town under threat.",
        loop="Reach the zone's dungeon, slay its deep boss, bear word home for the reward.",
        success="Deliver word to the town after felling the warden.",
        rewards="XP scaled to the zone's level cap.",
        replay="One-shot per zone.",
        scope="each zone that pairs a town with a dungeon",
        member=is_storyline,
    ),
    Archetype(
        key="bounty",
        name="Hunt Contract",
        purpose="Turn every named foe into a posted target, so the wilds are worth hunting.",
        narrative_role="A named threat the locals want gone.",
        loop="Seek the named foe by its bounty and fell it.",
        success="Defeat the named foe.",
        rewards="XP scaled to the foe's level.",
        replay="One-shot per foe.",
        scope="every non-ambient (named) foe",
        member=is_bounty,
    ),
    Archetype(
        key="cull",
        name="Cull Contract",
        purpose="The MMO staple at volume: thin a creature TYPE that plagues a region.",
        narrative_role="The land is overrun; a region asks you to push the wild back.",
        loop="Fell N creatures of the named kind, anywhere in the zone; the count climbs per kill.",
        success="Fell the full count of the kind in the zone.",
        rewards="XP scaled to the count and the zone's level.",
        replay="Repeatable-feeling: many per zone across kinds and count-tiers.",
        scope="each zone x each creature type of its biome x count-tier",
        member=is_cull,
    ),
    Archetype(
        key="forage",
        name="Forage Contract",
        purpose="The non-combat volume archetype: supply a region's makers with raw materials.",
        narrative_role="The crafters need stock; the land provides if you work it.",
        loop="Gather N of the named material at the zone's nodes; the count climbs per harvest.",
        success="Gather the full count of the material in the zone.",
        rewards="XP scaled to the count and the zone's level.",
        replay="Repeatable-feeling: many per zone across materials and count-tiers.",
        scope="each zone x each material its biome yields x count-tier",
        member=is_forage,
    ),
    Archetype(
        key="errand",
        name="Travel Errand",
        purpose="Carry the notice board beyond combat: send a courier across the map.",
        narrative_role="The roads are open, and word must move between the settlements.",
        loop="Travel to the named destination (a town, dungeon mouth, or waystone hub).",
        success="Arrive at the destination.",
        rewards="XP scaled to the poster's level band.",
        replay="One-shot per settlement.",
        scope="each settlement, to a distinct destination",
        member=is_errand,
    ),
    Archetype(
        key="delivery",
        name="Courier Delivery",
        purpose="The two-beat courier staple: carry a consignment between neighbouring towns.",
        narrative_role="Trade binds the settlements; goods and word move along the roads.",
        loop="Take the parcel up in the source town, carry it, and hand it over at the target.",
        success="Arrive at the destination town carrying the parcel.",
        rewards="XP scaled to the source town's level.",
        replay="One-shot per settlement (to its trade-partner).",
        scope="each settlement, to its level-adjacent trade-partner",
        member=is_delivery,
    ),
)

_BY_KEY = {a.key: a for a in CATALOG}


def archetype(key: str) -> Archetype | None:
    """The archetype record for a key, or None (AUTHORED is the fallback, not a catalog entry)."""
    return _BY_KEY.get(key)


def classify(quest_id: str) -> str:
    """The archetype KEY a live quest belongs to, or AUTHORED for a hand-written / built-in arc.
    First match wins, so CATALOG is ordered specific-before-broad."""
    for arch in CATALOG:
        if arch.member(quest_id):
            return arch.key
    return AUTHORED
