#!/usr/bin/env python3
"""CARD: zone_density -- measure per-zone content density across the Aethryn world.

The world spine is proven walkable end to end (test_journey_aethryn), but "walkable" is not "worth
walking": a zone can be on the road yet thin on things to DO. This is the measurement that finds the
thin zones so they can be filled to launch density -- no claim of density without correspondence.

Settlements and dungeons DECLARE their zone (a `zone:` field), so those counts are ground truth.
Quests do not carry a zone field, so a quest is attributed by the ROOMS it hooks: its id and its
`on_enter`/`on_take`/`on_defeat`/`on_give` targets share a distinctive stem (e.g. `aurelian_`) with
the settlement/hub that owns them. Stems that map to more than one zone (e.g. a bare `the`) are
dropped as ambiguous rather than guessed, so an attribution is never silently wrong. It ranks zones
by a simple density score and flags any below the launch floor. Content is read from the seed YAML
(the world is data); no world boot required.

Run: `python3 tools/zone_density.py` (or `make zone-density`). Re-run whenever the world grows.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

_SEED = Path(__file__).resolve().parent.parent / "content" / "seeds" / "aethryn"

# Launch-density floor per zone: below any of these, a zone reads as under-built.
FLOOR = {"settlements": 2, "dungeons": 1, "quests": 1}

# The quest fields whose values name a room; their stems tie a quest to a zone.
_ROOM_REF = re.compile(r"(?:on_enter|on_take|on_defeat|on_give|^\s*id):\s*([a-z][a-z0-9_]+)", re.M)


def _load(name: str) -> dict:
    return yaml.safe_load((_SEED / name).read_text(encoding="utf-8")) or {}


def _by_zone(rows: dict, zone_name: str) -> list[str]:
    """The ids of settlement/dungeon rows whose `zone` field matches this zone's display name."""
    return [k for k, v in rows.items() if isinstance(v, dict) and v.get("zone") == zone_name]


def _stem(label: str) -> str:
    """The distinctive leading token of a label or name (`aurelian_city` -> `aurelian`)."""
    return re.split(r"[ _]", label.strip().lower(), maxsplit=1)[0]


def _stem_index(zones: dict, settlements: dict, dungeons: dict) -> dict[str, str]:
    """Map each UNAMBIGUOUS name-stem to its owning zone; a stem seen in >1 zone is dropped."""
    seen: dict[str, set] = defaultdict(set)
    for z in zones.values():
        for hub in z.get("rooms", []):
            seen[_stem(hub)].add(z["name"])
        seen[_stem(z["name"])].add(z["name"])
    for rows in (settlements, dungeons):
        for key, v in rows.items():
            if isinstance(v, dict) and "zone" in v:
                seen[_stem(key)].add(v["zone"])
                seen[_stem(v.get("name", key))].add(v["zone"])
    return {stem: next(iter(zs)) for stem, zs in seen.items() if len(zs) == 1}


def _quest_zones(filename: str, text: str, stem2zone: dict[str, str]) -> set[str]:
    """The zones a quest attributes to, via the stems of the rooms it hooks (plus its filename)."""
    stems = {_stem(filename)} | {_stem(m) for m in _ROOM_REF.findall(text)}
    return {stem2zone[s] for s in stems if s in stem2zone}


def audit() -> list[dict]:
    zones = _load("zones.yaml")
    settlements = _load("settlements.yaml")
    dungeons = _load("dungeons.yaml")
    stem2zone = _stem_index(zones, settlements, dungeons)
    quest_zones = {
        p.name: _quest_zones(p.name, p.read_text(encoding="utf-8"), stem2zone)
        for p in sorted((_SEED / "quests").glob("*.yaml"))
    }

    rows: list[dict] = []
    for _zid, z in zones.items():
        name = z["name"]
        hubs = list(z.get("rooms", []))
        setts = _by_zone(settlements, name)
        dungs = _by_zone(dungeons, name)
        quests = [f for f, zs in quest_zones.items() if name in zs]
        score = (
            len(hubs) + 2 * len(setts) + 3 * len(dungs) + 2 * len(quests)
        )  # dungeons/quests weigh more
        counts = {"settlements": setts, "dungeons": dungs, "quests": quests}
        thin = [k for k, floor in FLOOR.items() if len(counts[k]) < floor]
        rows.append(
            {
                "zone": name,
                "band": f"{z.get('level_min')}-{z.get('level_max')}",
                "hubs": len(hubs),
                "settlements": len(setts),
                "dungeons": len(dungs),
                "quests": len(quests),
                "score": score,
                "thin_on": thin,
            }
        )
    return sorted(rows, key=lambda r: r["score"])


def main() -> int:
    rows = audit()
    print("=== Aethryn zone-density audit (per-zone content that declares its zone) ===\n")
    print(
        f"{'zone':<20} {'band':>8} {'hubs':>5} {'sett':>5} {'dun':>4} {'qst':>4} {'score':>6}  thin"
    )
    thin_zones = []
    for r in rows:
        flag = ("THIN: " + ",".join(r["thin_on"])) if r["thin_on"] else ""
        if r["thin_on"]:
            thin_zones.append(r["zone"])
        print(
            f"{r['zone']:<20} {r['band']:>8} {r['hubs']:>5} {r['settlements']:>6} "
            f"{r['dungeons']:>5} {r['quests']:>6} {r['score']:>6}  {flag}"
        )
    print(
        f"\n{len(thin_zones)}/{len(rows)} zones below the launch floor "
        f"(floor: {FLOOR['settlements']} sett, {FLOOR['dungeons']} dun, {FLOOR['quests']} quest)."
    )
    if thin_zones:
        print("Thinnest first:", ", ".join(thin_zones))
    return 0


if __name__ == "__main__":
    sys.exit(main())
