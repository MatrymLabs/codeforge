"""CARD: inns -- give every settlement a door to step through: a warm inn and its keeper.

The settlement generator filled the map's towns with people, but each town was still one open
plaza, nowhere to step INTO. An inn is the smallest interior that makes a town a place and not a
signpost: a room off the plaza with a hearth, a keeper to greet the road-weary, and a natural
gathering point now that heroes travel in parties and can shout across the world. This is the town's
twin of the depths' delve: where a dungeon mouth sinks `down` into danger, a hub opens `in` to rest.

Pure additive generation, mirroring the delve generator: `raise_inns` returns (rooms, npcs) to
merge, and `wire_inn_doors` opens each town hub's `in` exit into its inn, in place. Deterministic
and composed by settlement, so a town always grows the same inn: reproducible like every other
world generator, merged before the link audit so the new rooms and exits pass the authored gate.
"""

from __future__ import annotations

from typing import Any

from kernel.world.seed import Npc, Room
from kernel.world.session import Session

_INN_SUFFIX = "_inn"  # every generated inn room ends in this (a label convention, like the depths)


def is_inn_room(label: str) -> bool:
    """True if `label` is one of this generator's inn interiors (the `_inn` suffix convention)."""
    return label.endswith(_INN_SUFFIX)


def _restore(session: Session) -> None:
    """Heal one hero's every depleting resource to its maximum (combat's own heal-to-max idiom)."""
    for name, resource in session.resources.items():
        session.resources[name] = resource.heal(resource.maximum)


def rest(session: Session) -> str:
    """`rest`: at an inn's hearth, restore a hero's depleting resources (HP/MP/focus) to full, and
    any party-mates resting here too. The inn's whole purpose in play; refused anywhere else, since
    only a hearth mends a hero. Reuses combat's heal-to-max idiom; moves no world state."""
    if not is_inn_room(session.location):
        return "There is no hearth here to rest at. Find an inn (a town's `in` door), then REST."
    _restore(session)  # the caller is always mended, party or not
    mates = _rest_party_mates(session)
    if mates:
        return f"Your party settles by the hearth. You and {len(mates)} more return to full."
    return "You settle by the hearth and rest. Your strength and focus return in full."


def _rest_party_mates(session: Session) -> list[str]:
    """Mend the caller's party-mates resting in the same inn (never the caller), and tell them.
    Returns the mates healed. Empty for a solo hero. Reuses the party's members_in_room seam."""
    from kernel.world.events import announce_to
    from kernel.world.party import members_in_room
    from kernel.world.session import SESSIONS, display_name

    mates: list[str] = []
    for pid in members_in_room(session.player_id, session.location):
        if pid == session.player_id:
            continue
        mate = SESSIONS.get(pid)
        if mate is not None:
            _restore(mate)
            mates.append(pid)
    if mates:
        announce_to(mates, f"\nYou rest by the hearth with {display_name(session.player_id)}.")
    return mates


_INN_DESC = (
    "The {town} Inn. A low fire mutters in the hearth and the long tables are worn smooth by "
    "years of travellers' elbows. It is the warm heart of {town}, where the road's dust is "
    "shaken off and the day's tales are traded before the next stretch of the Forgeward Road. A "
    "door leads back OUT to the plaza."
)


def _keeper(inn_label: str, town: str) -> tuple[str, Npc]:
    """The innkeeper: a peaceful host with a word about rest, the roads, and the company that
    gathers here (a nod to parties on the road and the world channel's chatter)."""
    keeper = Npc(
        name=f"the keeper of the {town} Inn",
        keywords=["keeper", "innkeeper", "host"],
        location=inn_label,
        dialogue=[f'The keeper wipes a mug. "Rest easy, traveller. {town} keeps a warm hearth."'],
        next_line=0,
        hp=0,  # a host is never a fight
        hp_now=0,
        xp=0,
        atk=0,
        topics={
            "rest": ["Take a seat by the fire. The road is long and the beasts do not sleep."],
            "roads": [
                f"The Forgeward Road runs on past {town}. Bands of heroes pass through daily; "
                "many find their party over a cup here before they set out."
            ],
            "inn": ["A bed, a fire, and news from every road. What more does a traveller need?"],
        },
    )
    return f"{inn_label}_keeper", keeper


def raise_inns(configs: list[dict[str, Any]]) -> tuple[dict[str, Room], dict[str, Npc]]:
    """Build one inn interior per settlement, each with its keeper. Returns (rooms, npcs) to merge
    into the world; `wire_inn_doors` opens each town hub's `in` exit into its inn."""
    rooms: dict[str, Room] = {}
    npcs: dict[str, Npc] = {}
    for cfg in configs:
        hub, town = cfg["room"], str(cfg["name"])
        inn_label = f"{hub}_inn"
        rooms[inn_label] = Room(
            name=f"the {town} Inn",
            desc=_INN_DESC.format(town=town),
            exits={"out": hub},  # back to the plaza
        )
        label, keeper = _keeper(inn_label, town)
        npcs[label] = keeper
    return rooms, npcs


def wire_inn_doors(world: dict[str, Room], configs: list[dict[str, Any]]) -> None:
    """Open each town hub `in` into its inn, in place. A seed may omit a settlement's hub room; skip
    it rather than fail the boot (the same tolerance the delve wiring keeps)."""
    for cfg in configs:
        hub = cfg["room"]
        if hub in world:
            world[hub]["exits"].setdefault("in", f"{hub}_inn")
