"""CARD: score_sheet_model -- the character score-sheet view model (plain, validated data).

The data half of the score sheet, split from its renderer (parts/score_sheet.py) so the two
evolve and are consumed independently: the model serves the engine-coupled builder
(character_view) and equipment, while the renderer serves the CLI. This is the "decoupled view
model" the Hardware Store card names, made literal.

A `CharacterSheet` holds everything the sheet displays and nothing the renderer must compute.
Formulas live elsewhere; this part only carries the shape. `sheet_from_mapping` builds one from a
plain mapping (a JSON fixture today, a live-state projection tomorrow), keeping the model's input
decoupled from any one source.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

# The canonical attribute and derived-stat order, and the resistance grid order.
ATTR_ORDER = ("STR", "SPD", "MAG", "STA", "WIS", "LUCK")
DERIVED_ORDER = ("ATK", "DEF", "EVA", "MAG DEF", "ACC")
RESIST_ORDER = ("FIR", "ICE", "LGT", "WND", "ERT", "WTR", "HLY", "DRK", "PSN", "CRS")


@dataclass(frozen=True)
class JobTP:
    """One job's training-progress row: how far toward the next milestone."""

    label: str
    current: int
    required: int


@dataclass(frozen=True)
class JobLine:
    """One unlocked job's standing, for the `jobs` view: its level, JP, and TP."""

    name: str
    level: int
    jp: int
    tp: int


@dataclass(frozen=True)
class EquipmentLoadout:
    """The equipped items by slot. An empty string means the slot is bare."""

    weapon: str = ""
    body: str = ""
    head: str = ""
    arm: str = ""
    accessory_1: str = ""
    accessory_2: str = ""


@dataclass(frozen=True)
class CharacterSheet:
    """The character-sheet view model: everything the standard sheet displays, and nothing
    the renderer must compute. Populate it from live state or a fixture; the renderer only
    reads it. Optional data is honestly optional: `mp=None` has no MP line, `guild=None`
    omits the guild, `secondary_job=None` reads Unassigned, a missing resistance is unknown.
    """

    display_name: str
    player_level: int
    current_xp: int
    next_level_xp: int | None
    hp: tuple[int, int]
    jp: int
    race: str
    primary_job: str
    primary_job_level: int
    counter: str
    movement: str
    inherent: str
    signature: str
    mp: tuple[int, int] | None = None
    power: tuple[int, int] | None = None  # a custom resource (Power Cells), if the job has one
    guild: str | None = None
    rank_title: str = ""
    secondary_job: str | None = None
    tp_rows: tuple[JobTP, ...] = ()
    attributes: dict[str, int] = field(default_factory=dict)
    derived: dict[str, int] = field(default_factory=dict)
    equipment: EquipmentLoadout = field(default_factory=EquipmentLoadout)
    resistances: dict[str, str] = field(default_factory=dict)
    key_item: str = ""
    jobs: tuple[JobLine, ...] = ()  # every unlocked job, for the `jobs` view


def sheet_from_mapping(data: Mapping[str, Any]) -> CharacterSheet:
    """Build a view model from a plain mapping (a JSON fixture, or a future state builder).

    Keeps the model's input decoupled from any one source: the same shape can come from a
    saved fixture today or a live-character projection tomorrow.
    """
    hp = tuple(data["hp"])
    mp = tuple(data["mp"]) if data.get("mp") is not None else None
    tp_rows = tuple(
        JobTP(label=str(r["label"]), current=int(r["current"]), required=int(r["required"]))
        for r in data.get("tp_rows", [])
    )
    return CharacterSheet(
        display_name=str(data["display_name"]),
        player_level=int(data["player_level"]),
        current_xp=int(data["current_xp"]),
        next_level_xp=(None if data.get("next_level_xp") is None else int(data["next_level_xp"])),
        hp=(int(hp[0]), int(hp[1])),
        mp=(None if mp is None else (int(mp[0]), int(mp[1]))),
        jp=int(data["jp"]),
        race=str(data["race"]),
        guild=(None if data.get("guild") is None else str(data["guild"])),
        rank_title=str(data.get("rank_title", "")),
        primary_job=str(data["primary_job"]),
        primary_job_level=int(data["primary_job_level"]),
        secondary_job=(None if data.get("secondary_job") is None else str(data["secondary_job"])),
        counter=str(data["counter"]),
        movement=str(data["movement"]),
        inherent=str(data["inherent"]),
        signature=str(data["signature"]),
        tp_rows=tp_rows,
        attributes={str(k): int(v) for k, v in data.get("attributes", {}).items()},
        derived={str(k): int(v) for k, v in data.get("derived", {}).items()},
        equipment=EquipmentLoadout(
            **{str(k): str(v) for k, v in data.get("equipment", {}).items()}
        ),
        resistances={str(k): str(v) for k, v in data.get("resistances", {}).items()},
        key_item=str(data.get("key_item", "")),
    )
