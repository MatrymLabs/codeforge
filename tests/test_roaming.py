"""Test twin for kernel/world/roaming.py -- ambient NPCs that drift on the world beat.

Acceptance: a `wander` NPC in the player's room leaves through an exit; a wanderer next door ambles
in; the room index reflects the move; the drift is reachable through the engine tick. Refusal /
bounds: a non-wanderer never moves, the roam chance can keep a wanderer put, and a roomless session
is a clean no-op. Every move is deterministic under a seeded RNG.
"""

from __future__ import annotations

import copy

import pytest

from forge import handle_command
from kernel.world import npcs, roaming
from kernel.world.jobs import bind_calling
from kernel.world.npcs import NPCS, npcs_in
from kernel.world.roaming import roam
from kernel.world.seed import Npc
from kernel.world.session import SESSIONS, Session
from kernel.world.world import WORLD


@pytest.fixture(autouse=True)
def fresh_world():
    snap = copy.deepcopy(npcs.NPCS)
    SESSIONS.clear()
    yield
    npcs.NPCS.clear()
    npcs.NPCS.update(snap)
    npcs.reindex_npcs()
    SESSIONS.clear()


class _AlwaysMove:
    """A roam RNG that always triggers a move and picks the first option -- deterministic."""

    def randrange(self, n: int) -> int:
        return 0  # the 0 that clears the chance gate

    def choice(self, seq: list[str]) -> str:
        return seq[0]


class _NeverMove:
    def randrange(self, n: int) -> int:
        return 1  # never the 0 -> nothing moves

    def choice(self, seq: list[str]) -> str:
        return seq[0]


def _wanderer(label: str, location: str, wander: bool = True) -> str:
    npc: Npc = {
        "name": f"a {label}",
        "keywords": [label],
        "location": location,
        "dialogue": ["..."],
        "next_line": 0,
        "hp": 5,
        "hp_now": 5,
        "xp": 1,
        "atk": 0,
        "aggressive": False,
    }
    if wander:
        npc["wander"] = True
    npcs.NPCS[label] = npc
    npcs.reindex_npcs()
    return label


def _player_at(location: str) -> Session:
    s = Session(player_id="matrym", location=location)
    SESSIONS["matrym"] = s
    bind_calling(s, "vanguard")
    return s


def test_a_wanderer_leaves_the_players_room(monkeypatch):
    monkeypatch.setattr(roaming, "_ROAM_RNG", _AlwaysMove())
    s = _player_at("forge")
    _wanderer("stroller", "forge")
    first_exit = sorted(WORLD["forge"]["exits"])[0]  # noqa: FURB192
    dest = WORLD["forge"]["exits"][first_exit]
    out = roam(s)
    assert f"wanders {first_exit}" in out
    assert NPCS["stroller"]["location"] == dest
    assert "stroller" not in npcs_in("forge")
    assert "stroller" in npcs_in(dest)


def test_a_wanderer_ambles_in_from_next_door(monkeypatch):
    monkeypatch.setattr(roaming, "_ROAM_RNG", _AlwaysMove())
    s = _player_at("forge")
    adjacent = next(iter(WORLD["forge"]["exits"].values()))
    _wanderer("visitor", adjacent)
    out = roam(s)
    assert "wanders in" in out
    assert NPCS["visitor"]["location"] == "forge"
    assert "visitor" in npcs_in("forge")


def test_a_non_wanderer_stays_put(monkeypatch):
    monkeypatch.setattr(roaming, "_ROAM_RNG", _AlwaysMove())
    s = _player_at("forge")
    _wanderer("statue", "forge", wander=False)
    roam(s)
    assert NPCS["statue"]["location"] == "forge"  # no wander flag, no drift


def test_the_roam_chance_can_keep_a_wanderer_put(monkeypatch):
    monkeypatch.setattr(roaming, "_ROAM_RNG", _NeverMove())
    s = _player_at("forge")
    _wanderer("stroller", "forge")
    assert roam(s) == ""  # the chance gate held
    assert NPCS["stroller"]["location"] == "forge"


def test_a_roomless_session_is_a_clean_noop(monkeypatch):
    monkeypatch.setattr(roaming, "_ROAM_RNG", _AlwaysMove())
    s = Session(player_id="ghost", location="nowhere-real")
    assert roam(s) == ""  # an unknown room: nothing to roam, no crash


def test_roaming_is_reachable_through_the_engine_tick(monkeypatch):
    monkeypatch.setattr(roaming, "_ROAM_RNG", _AlwaysMove())
    s = _player_at("forge")
    _wanderer("drifter", "forge")
    out = handle_command(s, "look")  # any command runs the beat, which runs roam
    assert "wanders" in out
    assert NPCS["drifter"]["location"] != "forge"  # it drifted on the beat
