"""Test twin for kernel/world/shrine.py -- pray at a wayshrine for a rest boon.

Acceptance: a room with a shrine restores a share of the pilgrim's pools to `pray`, then the shrine
falls quiet until its cooldown ticks out; a room without a shrine (and a pilgrim already whole) fail
or no-op cleanly. Integration: the wildlands seeds exactly one wayshrine per region, `pray` is
reachable through the engine tick, and a look shows the shrine.
"""

from __future__ import annotations

import pytest

import forge
from kernel.world import shrine
from kernel.world.resources import Resource
from kernel.world.session import SESSIONS, Session
from kernel.world.world import WORLD


@pytest.fixture(autouse=True)
def fresh():
    SESSIONS.clear()
    WORLD["probe_shrine_room"] = {
        "name": "The Wayshrine",
        "desc": "an old standing-stone",
        "exits": {},
        "shrine": "wayshrine",
    }
    yield
    WORLD.pop("probe_shrine_room", None)
    SESSIONS.clear()


def _pilgrim(hp=(10, 100), mp=(5, 50), location="probe_shrine_room") -> Session:
    s = Session(player_id="pilgrim", location=location)
    s.resources = {"hp": Resource("hp", *hp), "mp": Resource("mp", *mp)}
    SESSIONS["pilgrim"] = s
    return s


def test_praying_at_a_wayshrine_restores_a_share_of_your_pools():
    s = _pilgrim()
    out = shrine.pray(s)
    assert "wayshrine" in out.lower()
    # a wayshrine restores maximum // 2 of each pool, clamped to the maximum
    assert s.resources["hp"].current == 10 + 100 // 2
    assert s.resources["mp"].current == 5 + 50 // 2


def test_a_used_shrine_is_spent_then_renews_after_its_cooldown():
    s = _pilgrim()
    shrine.pray(s)
    assert "spent for now" in shrine.pray(s)  # on cooldown for this player
    for _ in range(shrine.SHRINE_COOLDOWN):  # the world beat renews it
        shrine.tick_shrines(s)
    assert "restores" in shrine.pray(s)  # ready again


def test_a_whole_pilgrim_gets_a_gentle_no_op_not_an_error():
    s = _pilgrim(hp=(100, 100), mp=(50, 50))
    out = shrine.pray(s)
    assert "already whole" in out and s.resources["hp"].current == 100


def test_a_room_with_no_shrine_has_nothing_to_pray_at():
    s = _pilgrim(location="probe_shrine_room")
    del WORLD["probe_shrine_room"]["shrine"]
    assert "no shrine here" in shrine.pray(s)


def test_a_shrine_shows_on_look():
    assert "wayshrine" in shrine.shrine_hint("probe_shrine_room").lower()
    del WORLD["probe_shrine_room"]["shrine"]
    assert shrine.shrine_hint("probe_shrine_room") == ""


def test_pray_is_reachable_through_the_engine_tick():
    # A feature is not wired until handle_command proves it reachable (the repo rule).
    s = _pilgrim()
    out = forge.handle_command(s, "pray")
    assert "wayshrine" in out.lower() and s.resources["hp"].current > 10


def test_the_wildlands_seeds_exactly_one_wayshrine_per_region():
    from kernel.world.wildlands import generate_wildlands

    cfg = {
        "id": "probe_wild",
        "name": "The Probe Wilds",
        "region": "Emberreach",
        "biome": "temperate-meadow",
        "attach": "anchor",
        "attach_dir": "east",
        "level_min": 4,
        "level_max": 12,
        "trail_length": 20,
        "branch_every": 3,
        "branch_length": 3,
        "notable_every": 0,
    }
    rooms, _ = generate_wildlands([cfg], {"anchor"})
    shrines = [label for label, r in rooms.items() if r.get("shrine") == "wayshrine"]
    assert len(shrines) == 1, f"a region should seed exactly one wayshrine, got {len(shrines)}"
