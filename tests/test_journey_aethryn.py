"""End-to-end JOURNEY gate over the REAL aethryn content: the Forgeward Road walked to the endgame.

`test_journey_spine` proves the MECHANISM (travel firing the on_enter beat advances the spine) with
a controlled world. This proves the SHIPPED aethryn campaign actually connects end to end: its real
zones (seeds/aethryn/zones.yaml) lay a complete main road, every zone on that road is a real
waystone (seeds/aethryn/waystones.yaml) so the road is walkable by fast-travel, and carrying a fresh
hero hub-to-hub over the real travel() reaches the real endgame (the Voidscar) and its reward.

This is the content regression guard behind "the game plays from the valley to the endgame": the
live spine is forged from exactly these zones (kernel/world/world.py: register_spine(_story_zones),
_story_zones = load_zones(zones.yaml)), so reading them here walks the same road the server lays.

Acceptance: every leg advances in order and the endgame terminal + XP reward fire at the Voidscar.
Invariant: every spine hub is a waystone (add a zone, you must add its waystone, or the road cannot
be walked). Tick-level + deterministic; the live-TCP full walk is scripts/e2e_smoke.py.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from kernel.world import quest as questmod
from kernel.world.jobs import bind_calling
from kernel.world.session import Session
from kernel.world.spine import forge_spine
from kernel.world.travel import travel

_AETHRYN = Path(__file__).resolve().parent.parent / "content" / "blueprints" / "aethryn"


def _real_zones() -> list[dict[str, Any]]:
    """The flagship's declared story zones (the set the live server forges the spine from)."""
    raw = yaml.safe_load((_AETHRYN / "zones.yaml").read_text(encoding="utf-8"))
    return [{**z, "name": z.get("name", zid)} for zid, z in raw.items()]


def _real_waystones() -> dict[str, dict[str, Any]]:
    """The flagship's waystone network manifest (hub room-id -> {name, level})."""
    raw = yaml.safe_load((_AETHRYN / "waystones.yaml").read_text(encoding="utf-8"))
    return {room: {"name": cfg["name"], "level": int(cfg["level"])} for room, cfg in raw.items()}


def _ordered_hubs(zones: list[dict[str, Any]]) -> list[str]:
    """Each zone's hub room (rooms[0]) in the spine's own order: level_min then level_max."""
    ordered = sorted(
        (z for z in zones if z.get("rooms")),
        key=lambda z: (int(z.get("level_min") or 1), int(z.get("level_max") or 1)),
    )
    return [str(z["rooms"][0]) for z in ordered]


@pytest.fixture
def aethryn_road():
    """Fold the REAL Forgeward Road into the engine, isolated from the loaded seed's quests."""
    zones = _real_zones()
    stones = _real_waystones()
    spec = forge_spine(zones)
    assert spec is not None, "the flagship must lay a road"

    q_snap = dict(questmod._QUESTS)
    routes_snap = copy.deepcopy(questmod._EVENT_ROUTES)
    runs_snap = copy.deepcopy(questmod._RUNS)
    questmod.register_specs([spec])
    try:
        yield zones, stones, spec
    finally:
        questmod._QUESTS.clear()
        questmod._QUESTS.update(q_snap)
        questmod._EVENT_ROUTES.clear()
        questmod._EVENT_ROUTES.update(routes_snap)
        questmod._RUNS.clear()
        questmod._RUNS.update(runs_snap)


def test_every_forgeward_hub_is_a_waystone(aethryn_road):
    """Invariant: the road must be walkable by fast-travel end to end. A zone on the spine with no
    waystone is an unreachable leg -- the exact orphaned-inch this whole effort is chasing."""
    zones, stones, spec = aethryn_road
    hubs = _ordered_hubs(zones)
    orphaned = [h for h in hubs if h not in stones]
    assert not orphaned, f"spine hubs with no waystone (road unwalkable by fast-travel): {orphaned}"
    assert len(spec["steps"]) >= 10, (
        "the flagship road must be a real multi-zone journey, not a stub"
    )


def test_the_real_forgeward_road_walks_to_the_voidscar(aethryn_road):
    """Carry a fresh hero across every real waystone in order and prove the campaign advances one
    leg per arrival, all the way to the shipped endgame (the Voidscar) and its reward."""
    zones, stones, spec = aethryn_road
    hubs = _ordered_hubs(zones)

    hero = Session(player_id="aethryn_pathfinder", location=hubs[0])
    bind_calling(hero, "vanguard")  # real stats, so the endgame XP reward actually lands
    hero.coins = 100_000_000  # a full purse: the fare sink is not what this gate measures
    start_xp = hero.xp
    start_level = hero.level

    legs_advanced = 0
    out = ""
    for hub in hubs[1:]:  # from the second hub onward: each arrival is a spine beat
        out = travel(hero, hub, stones)
        assert f"carried to the {stones[hub]['name']} waystone" in out  # the hop happened
        if "road runs on" in out or "walked the Forgeward Road" in out:
            legs_advanced += 1  # arriving ticked the road forward

    # Every leg advanced, in order, with no gap in the chain.
    assert legs_advanced == len(spec["steps"])
    # The shipped endgame fired at the final hub, with its whole-world reward.
    assert "walked the Forgeward Road" in out
    assert "Aethryn is yours to roam" in out
    assert hero.level == start_level + 1
    assert hero.xp > start_xp
