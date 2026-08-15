"""CARD: campaign -- one executable content contract for a whole seed campaign.

Aethryn's breadth is deliberately generated: the map declares zones and dungeon mouths, wildlands
grow their enemies, settlements grow their people, and the quest engine grows contracts. That is
useful only if the whole campaign is checked as one product. This module loads a small seed-side
contract and validates the assembled result in one pass, from the level-one on-ramp through the
level-300 endgame.

The contract is not a second world database. It declares the campaign cap, representative level
checkpoints, and minimum per-zone guarantees; the report derives its counts from the live assembled
world. A missing dungeon, quest, enemy, or settlement therefore fails boot/CI instead of becoming a
silent thin zone.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from kernel.world.seed import BlueprintError, Npc

_MINIMUM_KEYS = ("zones", "dungeons", "settlements", "combatants", "npcs", "quests")


def load_campaign(path: Path) -> dict[str, Any] | None:
    """Load and validate an optional campaign contract.

    Seeds without ``campaign.yaml`` remain unchanged. A campaign contract is intentionally small:
    it describes the level cap/checkpoints and the minimum content each declared zone must carry.
    """
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise BlueprintError("campaign.yaml must be a mapping.")
    for key in ("id", "name", "level_cap", "checkpoints", "minimums"):
        if key not in raw:
            raise BlueprintError(f"campaign.yaml is missing required key {key!r}.")
    if not isinstance(raw["id"], str) or not raw["id"].strip():
        raise BlueprintError("campaign.yaml: 'id' must be a non-empty string.")
    if not isinstance(raw["name"], str) or not raw["name"].strip():
        raise BlueprintError("campaign.yaml: 'name' must be a non-empty string.")
    cap = raw["level_cap"]
    if isinstance(cap, bool) or not isinstance(cap, int) or not 1 <= cap <= 300:
        raise BlueprintError(f"campaign.yaml: 'level_cap' must be an int 1..300, got {cap!r}.")

    checkpoints = raw["checkpoints"]
    if not isinstance(checkpoints, list) or not checkpoints:
        raise BlueprintError("campaign.yaml: 'checkpoints' must be a non-empty list.")
    if any(isinstance(level, bool) or not isinstance(level, int) for level in checkpoints):
        raise BlueprintError("campaign.yaml: checkpoints must contain only integers.")
    if checkpoints != sorted(set(checkpoints)) or checkpoints[0] != 1 or checkpoints[-1] != cap:
        raise BlueprintError(
            "campaign.yaml: checkpoints must be sorted, unique, and span from 1 to level_cap."
        )
    if any(level < 1 or level > cap for level in checkpoints):
        raise BlueprintError("campaign.yaml: every checkpoint must fall within 1..level_cap.")

    minimums = raw["minimums"]
    if not isinstance(minimums, dict):
        raise BlueprintError("campaign.yaml: 'minimums' must be a mapping.")
    missing = [key for key in _MINIMUM_KEYS if key not in minimums]
    if missing:
        raise BlueprintError(f"campaign.yaml: minimums missing {', '.join(missing)}.")
    for key in _MINIMUM_KEYS:
        value = minimums[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise BlueprintError(f"campaign.yaml: minimums.{key} must be a positive integer.")
    return raw


def _covered(level: int, zones: list[dict[str, Any]]) -> bool:
    return any(int(z.get("level_min", 0)) <= level <= int(z.get("level_max", 0)) for z in zones)


def report(
    contract: dict[str, Any],
    zones: list[dict[str, Any]],
    dungeons: list[dict[str, Any]],
    settlements: list[dict[str, Any]],
    npcs: dict[str, Npc],
    quest_ids: list[str],
) -> dict[str, Any]:
    """Return a machine-readable campaign census from assembled world components."""
    minimums = contract["minimums"]
    zone_rows: list[dict[str, Any]] = []
    for zone in zones:
        label = str(zone.get("label", zone.get("name", "")))
        name = str(zone.get("name", label))
        rooms = set(zone.get("rooms", []))
        zone_dungeons = [d for d in dungeons if d.get("zone") == name]
        zone_settlements = [s for s in settlements if s.get("zone") == name]
        zone_npcs = [npc for npc in npcs.values() if npc.get("location") in rooms]
        zone_combatants = [npc for npc in zone_npcs if npc.get("hp", 0) > 0]
        story_ids = {f"story_{s['room']}" for s in zone_settlements if s.get("room")}
        zone_quest_ids = [
            quest_id
            for quest_id in quest_ids
            if quest_id in story_ids
            or quest_id.startswith(f"cull_{label}_")
            or quest_id.startswith(f"forage_{label}_")
        ]
        zone_rows.append(
            {
                "label": label,
                "name": name,
                "level_min": zone.get("level_min"),
                "level_max": zone.get("level_max"),
                "rooms": len(rooms),
                "dungeons": len(zone_dungeons),
                "settlements": len(zone_settlements),
                "npcs": len(zone_npcs),
                "combatants": len(zone_combatants),
                "quests": len(zone_quest_ids),
            }
        )

    cap = int(contract["level_cap"])
    covered_levels = [level for level in range(1, cap + 1) if _covered(level, zones)]
    return {
        "campaign": contract["id"],
        "name": contract["name"],
        "level_cap": cap,
        "zones": len(zones),
        "dungeons": len(dungeons),
        "settlements": len(settlements),
        "npcs": len(npcs),
        "combatants": sum(1 for npc in npcs.values() if npc.get("hp", 0) > 0),
        "quests": len(quest_ids),
        "level_band_gaps": [
            level for level in range(1, cap + 1) if level not in set(covered_levels)
        ],
        "checkpoints": {str(level): _covered(level, zones) for level in contract["checkpoints"]},
        "zone_rows": zone_rows,
        "minimums": minimums,
    }


def validate(
    path: Path,
    zones: list[dict[str, Any]],
    dungeons: list[dict[str, Any]],
    settlements: list[dict[str, Any]],
    npcs: dict[str, Npc],
    quest_ids: list[str],
) -> dict[str, Any] | None:
    """Validate a seed's assembled campaign and return its census.

    This is the single gate for the campaign-wide promise. It is intentionally called after all
    procedural generators and quest registrations have run, so it measures what players receive.
    """
    contract = load_campaign(path)
    if contract is None:
        return None
    result = report(contract, zones, dungeons, settlements, npcs, quest_ids)
    minimums = result["minimums"]
    failures: list[str] = []
    if result["zones"] < minimums["zones"]:
        failures.append(f"zones {result['zones']} < {minimums['zones']}")
    for key in ("dungeons", "settlements", "combatants", "npcs", "quests"):
        if result[key] < minimums[key]:
            failures.append(f"{key} {result[key]} < {minimums[key]}")
    if result["level_band_gaps"]:
        failures.append(f"level coverage gaps {result['level_band_gaps'][:8]}")
    missing_checkpoints = [level for level, covered in result["checkpoints"].items() if not covered]
    if missing_checkpoints:
        failures.append(f"checkpoint coverage missing {missing_checkpoints}")
    for row in result["zone_rows"]:
        for key in ("dungeons", "settlements", "combatants", "npcs", "quests"):
            if row[key] < minimums[key]:
                failures.append(f"{row['name']}: {key} {row[key]} < {minimums[key]}")
    if failures:
        raise BlueprintError("campaign content contract failed: " + "; ".join(failures))
    return result
