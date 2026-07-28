"""CARD: zone_story -- assemble a zone's scattered content into one STORY dossier (the framework).

Every zone already carries its pieces -- a tale, a dungeon and its warden, a surface monument, a
depths inscription, a board of culls and forages -- but they live in six different generators. This
is the Zone Story Framework the campaign asks for: it gathers those pieces from the live world into
one `ZoneStory`, and renders a dossier that tells a player (or a designer) the history, dangers, and
opportunities of a place at a glance. Read-only and derived -- it invents nothing, it COMPOSES what
the generators already placed, so a zone's story is exactly the sum of its filed content.

`assemble(zone_label)` returns the dossier data; `region_view(session)` renders the player's current
zone. The completeness test pins that every dungeon-bearing zone reports its full narrative set.
"""

from __future__ import annotations

from dataclasses import dataclass

from parts.world import items, quest
from parts.world.cull import CULL_PREFIX
from parts.world.forage import FORAGE_PREFIX
from parts.world.npcs import NPCS
from parts.world.session import Session
from parts.world.wardens import DEEP_BOSS_SUFFIX
from parts.world.zones import ZONES, zone_of


@dataclass(frozen=True)
class ZoneStory:
    """One zone's story, composed from the live world: its place, tale, depths, and board."""

    label: str
    name: str
    region: str
    biome: str
    level_min: int
    level_max: int
    rooms: int
    tale: str | None  # the storyline's hook, if the zone pairs a town with a dungeon
    warden: str | None  # the deep boss's name, if the zone holds a dungeon
    inscription: str | None  # the depths lore, if any
    landmark: str | None  # the surface monument's lore, if any
    culls: int  # cull-contracts scoped to this zone
    forages: int  # forage-contracts scoped to this zone


def _dungeon_room(rooms: list[str]) -> str | None:
    """The zone room that mouths a delve (the one whose deep boss exists), or None."""
    return next((r for r in rooms if f"{r}{DEEP_BOSS_SUFFIX}" in NPCS), None)


def _settlement_room(rooms: list[str]) -> str | None:
    """A zone room that is a settlement (the one with a merchant), or None."""
    return next((r for r in rooms if f"{r}_merchant" in NPCS), None)


def _lore(label: str) -> str | None:
    """The readable lore on a placed item (a landmark or inscription), or None if absent."""
    item = items.ITEMS.get(label)
    return item.get("lore") if item else None


def assemble(zone_label: str) -> ZoneStory | None:
    """Gather a zone's story from the live world, or None for an unknown zone label. Derived, not
    stored: every field is read from the content the generators already placed."""
    zone = ZONES.get(zone_label)
    if zone is None:
        return None
    rooms = list(zone.get("rooms", []))
    dungeon = _dungeon_room(rooms)
    town = _settlement_room(rooms)
    warden = NPCS[f"{dungeon}{DEEP_BOSS_SUFFIX}"]["name"] if dungeon else None
    tale = quest.hook_of(f"story_{town}") if town else None
    culls = sum(1 for qid in quest.all_ids() if qid.startswith(f"{CULL_PREFIX}{zone_label}_"))
    forages = sum(1 for qid in quest.all_ids() if qid.startswith(f"{FORAGE_PREFIX}{zone_label}_"))
    return ZoneStory(
        label=zone_label,
        name=str(zone.get("name", zone_label)),
        region=str(zone.get("region", zone.get("name", ""))),
        biome=str(zone.get("biome", "")),
        level_min=int(zone.get("level_min", 1)),
        level_max=int(zone.get("level_max", 1)),
        rooms=len(rooms),
        tale=tale,
        warden=warden,
        inscription=_lore(f"inscription_{dungeon}") if dungeon else None,
        landmark=_lore(f"landmark_{rooms[0]}") if rooms else None,
        culls=culls,
        forages=forages,
    )


def render(story: ZoneStory) -> str:
    """A readable dossier of a zone's story -- its place, tale, depths, and the work it offers."""
    lines = [f"== {story.name} ({story.region}) =="]
    band = f"level {story.level_min}-{story.level_max}"
    lines.append(f"A {story.biome or 'storied'} land for heroes of {band}. ({story.rooms} rooms)")
    if story.tale:
        lines.append(f"Its tale: {story.tale}")
    if story.warden:
        lines.append(f"Its depths are held by {story.warden}.")
    if story.inscription:
        lines.append(f"Carved below: {story.inscription}")
    if story.landmark:
        lines.append(f"At its heart: {story.landmark}")
    work = []
    if story.culls:
        work.append(f"{story.culls} cull-contracts")
    if story.forages:
        work.append(f"{story.forages} forage-contracts")
    if work:
        lines.append("Work here: " + ", ".join(work) + ".")
    return "\n".join(lines)


def region_view(session: Session) -> str:
    """`region` -- the story dossier of the zone the player currently stands in. A plain line when
    the player is in the untracked wilds (a room that belongs to no named area)."""
    label = zone_of(session.location)
    if label is None:
        return "You stand in untracked wilds, far from any storied region."
    story = assemble(label)
    return render(story) if story else "This region keeps no story yet."
