"""CARD: canon -- Aethryn's LOCKED world canon, machine-checkable so nothing may silently break it.

The prompt's first law: established canon (the world's name, the regions, the deliberate divine
strike, Netharion the first artificial god, the Seven Crowns and their functions) may NEVER be
overwritten by generated content. This module makes that enforceable. It loads
seeds/aethryn/canon.yaml (the single source of locked canon), validates its shape at load (fail
loud, like every seed loader), and exposes the canon plus a `check_canon` drift validator that
confirms the shipped world still corresponds to it.

The authority ladder every world record's `canon_status` draws from:
  CANON_LOCKED    -- names, regions, the strike, the Seven Crowns; a generator may not change these.
  CANON_WORKING   -- mythic titles, working terms; revisable later without a destructive migration.
  AUTHORED_LOCAL  -- developer local lore that does not redefine global canon.
  GENERATED_LOCAL -- deterministically generated caves, rooms, minor NPCs, rumours, treasures.
  RUMOR           -- in-world information that may be false, distorted, ideological, or incomplete.

Readable canon prose lives in docs/aethryn_lore_bible.md; THIS is the checkable data behind it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from kernel.world.seed import SEEDS_ROOT, BlueprintError, _UniqueKeyLoader

# Aethryn's canon lives with the aethryn seed, whichever game the engine is currently booted into
# (the canon describes THAT world, not the active seed). Anchor to it explicitly.
AETHRYN_DIR = SEEDS_ROOT / "aethryn"

# The authority ladder, most-protected first.
CANON_STATUSES = (
    "CANON_LOCKED",
    "CANON_WORKING",
    "AUTHORED_LOCAL",
    "GENERATED_LOCAL",
    "RUMOR",
)

_CANON_PATH = AETHRYN_DIR / "canon.yaml"
_CROWN_FIELDS = ("id", "map_name", "mythic_title", "region", "ancient_function", "modern_condition")
_REGION_FIELDS = ("id", "name", "threat_min", "threat_max")


def load_canon(path: Path | None = None) -> dict[str, Any]:
    """Read and VALIDATE the locked canon. Fails loud (BlueprintError) on any malformed record, so a
    canon file that could mislead a generator never loads silently. Returns the parsed mapping."""
    where = path if path is not None else _CANON_PATH
    if not where.exists():
        raise BlueprintError(f"Canon file not found: {where}")
    data = yaml.load(where.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    if not isinstance(data, dict):
        raise BlueprintError(f"Canon file is not a mapping: {where}")

    def _status(record: dict[str, Any], label: str) -> None:
        status = record.get("canon_status")
        if status not in CANON_STATUSES:
            raise BlueprintError(
                f"canon {label}: canon_status must be one of {CANON_STATUSES}, got {status!r}"
            )

    world = data.get("world")
    if not isinstance(world, dict) or world.get("id") != "aethryn":
        raise BlueprintError("canon: 'world' must name id 'aethryn'")
    _status(world, "world")

    crowns = data.get("seven_crowns")
    if not isinstance(crowns, list) or len(crowns) != 7:
        raise BlueprintError(
            f"canon: 'seven_crowns' must list exactly 7 sites, got {len(crowns or [])}"
        )
    for crown in crowns:
        for field in _CROWN_FIELDS:
            if not crown.get(field):
                raise BlueprintError(
                    f"canon crown {crown.get('id')!r}: missing required field {field!r}"
                )
        if crown.get("canon_status") != "CANON_LOCKED":
            raise BlueprintError(
                f"canon crown {crown['id']!r}: a Seven Crown site must be CANON_LOCKED"
            )

    world_regions = data.get("regions")
    if not isinstance(world_regions, list) or len(world_regions) != 14:
        raise BlueprintError(
            f"canon: 'regions' must list exactly 14 regions, got {len(world_regions or [])}"
        )
    for region in world_regions:
        for field in _REGION_FIELDS:
            if region.get(field) is None:
                raise BlueprintError(
                    f"canon region {region.get('id')!r}: missing required field {field!r}"
                )
        if region["threat_min"] > region["threat_max"]:
            raise BlueprintError(f"canon region {region['id']!r}: threat_min exceeds threat_max")
        _status(region, f"region {region['id']!r}")

    for fact in data.get("facts", []):
        if not fact.get("id") or not fact.get("text"):
            raise BlueprintError(f"canon fact {fact.get('id')!r}: needs an id and text")
        _status(fact, f"fact {fact.get('id')!r}")

    for term in data.get("collective_names", []):
        if not term.get("name") or not term.get("usage"):
            raise BlueprintError(
                f"canon collective name {term.get('id')!r}: needs a name and usage"
            )
        _status(term, f"collective name {term.get('id')!r}")

    for faction in data.get("world_factions", []):
        if not faction.get("id") or not faction.get("name") or not faction.get("stance"):
            raise BlueprintError(
                f"canon faction {faction.get('id')!r}: needs an id, name, and stance"
            )
        _status(faction, f"faction {faction.get('id')!r}")
    return data


def seven_crowns(canon: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """The seven principal sites of the old civilisation, each with its map name, mythic title,
    region, ancient function, and modern condition."""
    return list((canon or load_canon())["seven_crowns"])


def regions(canon: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """The 14 canon regions with their locked names and threat bands."""
    return list((canon or load_canon())["regions"])


def locked_region_names(canon: dict[str, Any] | None = None) -> set[str]:
    """The region names a generator may never rename or reuse (CANON_LOCKED)."""
    return {r["name"] for r in regions(canon)}


def unresolved_questions(canon: dict[str, Any] | None = None) -> list[str]:
    """The questions the world keeps OPEN: generated content may raise them only as RUMOR."""
    return list((canon or load_canon()).get("unresolved_questions", []))


def collective_names(canon: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """The six names for the Seven Crowns, each with its own tier and the worldview that uses it.
    The neutral names are CANON_LOCKED; the ideological ones are RUMOR (belief, not fact)."""
    return list((canon or load_canon()).get("collective_names", []))


def world_factions(canon: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """The provisional world-scale factions (CANON_WORKING): each an id, name, and stance."""
    return list((canon or load_canon()).get("world_factions", []))


def world_faction_ids(canon: dict[str, Any] | None = None) -> set[str]:
    """The set of known faction ids, so a reference to a faction can be validated against canon."""
    return {f["id"] for f in world_factions(canon)}


def is_generated_status(status: str) -> bool:
    """True for a status a generator is allowed to stamp on the content it makes."""
    return status in ("AUTHORED_LOCAL", "GENERATED_LOCAL", "RUMOR")


def check_canon() -> list[str]:
    """The `check-canon` guardrail: confirm the shipped world still corresponds to the locked
    canon, so a drift (a renamed region, a missing Seven Crown site) is caught. Returns a list of
    violation lines, empty when the world is faithful. A malformed canon raises from load_canon."""
    canon = load_canon()
    zone_names = _names_in(AETHRYN_DIR / "waystones.yaml")
    place_names = _names_in(AETHRYN_DIR / "settlements.yaml")
    place_names |= _names_in(AETHRYN_DIR / "dungeons.yaml")
    return _correspondence_violations(canon, zone_names, place_names)


def _correspondence_violations(
    canon: dict[str, Any], zone_names: set[str], place_names: set[str]
) -> list[str]:
    """Pure drift check: every locked region must be a registered zone hub, and every Seven Crown
    site a registered location. Returns the violation lines (empty when the world matches canon)."""
    violations: list[str] = []
    for region in regions(canon):
        if region["name"] not in zone_names:
            violations.append(f"canon region '{region['name']}' is not a registered waystone zone")
    for crown in seven_crowns(canon):
        if crown["map_name"] not in place_names:
            violations.append(
                f"Seven Crown site '{crown['map_name']}' is not a registered location"
            )
    return violations


def _names_in(path: Path) -> set[str]:
    """The display names of every top-level record in a seed YAML file (skipping a template)."""
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    if not isinstance(data, dict):
        return set()
    return {
        v["name"]
        for k, v in data.items()
        if k != "template" and isinstance(v, dict) and "name" in v
    }
