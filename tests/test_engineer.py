"""Test twin for parts/engineer.py -- the Engineer's combat kit, all deterministic.

Proves the four combat pillars the vertical slice requires: a skill (Field Repair) that heals
and spends MP, a cooldown that recovers over ticks, a status (Analyzed via Diagnostic Scan)
that lengthens with the inherent and expires, and a counter (Emergency Repair) that fires once
below a threshold and respects its cooldown. Plus the engine-tick reachability of the verbs.
"""

from __future__ import annotations

import copy

import pytest

from forge import handle_command
from parts import engineer, npcs
from parts.engineer import (
    analyzed_duration,
    deploy_barrier,
    diagnostic_scan,
    emergency_repair,
    field_repair,
    field_repair_heal,
    tick,
)
from parts.jobs import bind_calling
from parts.resources import Resource
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_world():
    npcs_snap = copy.deepcopy(npcs.NPCS)
    SESSIONS.clear()
    yield
    npcs.NPCS = npcs_snap
    SESSIONS.clear()


def _engineer(location: str = "courtyard") -> Session:
    s = Session(player_id="matrym", location=location)
    SESSIONS["matrym"] = s
    bind_calling(s, "engineer")
    return s


def _hurt(session: Session, current: int) -> None:
    hp = session.resources["hp"]
    session.resources["hp"] = Resource("hp", current, hp.maximum)


# --- Field Repair: the skill + MP cost + cooldown -------------------------------
def test_field_repair_heals_and_spends_mp() -> None:
    s = _engineer()
    _hurt(s, 5)  # 5 / 31
    before_mp = s.resources["mp"].current
    out = field_repair(s)
    assert s.resources["hp"].current == 5 + field_repair_heal(s)  # heal = 6 + 13//2 + 1 = 13
    assert s.resources["mp"].current == before_mp - engineer.FIELD_REPAIR_MP
    assert "Field Repair" in out


def test_field_repair_enters_and_reports_a_cooldown() -> None:
    s = _engineer()
    _hurt(s, 5)
    field_repair(s)
    assert s.cooldowns["field_repair"] == engineer.FIELD_REPAIR_COOLDOWN
    assert "still recovering" in field_repair(s)  # a second immediate use is refused


def test_the_cooldown_expires_after_enough_ticks() -> None:
    s = _engineer()
    _hurt(s, 5)
    field_repair(s)
    for _ in range(engineer.FIELD_REPAIR_COOLDOWN):
        tick(s)
    assert "field_repair" not in s.cooldowns  # ready again
    _hurt(s, 5)
    assert "Field Repair" in field_repair(s)


def test_field_repair_refused_without_enough_mp() -> None:
    s = _engineer()
    s.resources["mp"] = Resource("mp", 1, 13)  # below the cost
    assert "Not enough MP" in field_repair(s)


def test_only_an_engineer_can_field_repair() -> None:
    s = Session(player_id="matrym")
    bind_calling(s, "vanguard")
    assert "Only an Engineer" in field_repair(s)


# --- Diagnostic Scan: the status + the inherent passive -------------------------
def test_diagnostic_scan_applies_analyzed_lengthened_by_the_inherent() -> None:
    s = _engineer()
    out = diagnostic_scan(s, "dummy")
    # Systems Thinking (inherent) adds +1 to the base duration.
    assert s.statuses["analyzed"] == engineer.ANALYZED_BASE_DURATION + 1
    assert "Analyzed applied" in out


def test_analyzed_expires_after_its_ticks() -> None:
    s = _engineer()
    diagnostic_scan(s, "dummy")
    for _ in range(analyzed_duration(s)):
        tick(s)
    assert "analyzed" not in s.statuses


def test_the_inherent_lengthens_analyzed() -> None:
    s = _engineer()
    assert (
        analyzed_duration(s)
        == engineer.ANALYZED_BASE_DURATION + engineer.SYSTEMS_THINKING_ANALYZED_BONUS
    )


# --- Emergency Repair: the counter ----------------------------------------------
def test_emergency_repair_fires_once_below_the_threshold() -> None:
    s = _engineer()
    _hurt(s, 5)  # 5/31 is well below 30%
    out = emergency_repair(s)
    assert out is not None and "Emergency Repair" in out
    assert s.resources["hp"].current == 5 + field_repair_heal(s)
    assert "emergency_repair" in s.cooldowns


def test_emergency_repair_does_not_fire_twice_before_recovering() -> None:
    s = _engineer()
    _hurt(s, 3)
    assert emergency_repair(s) is not None
    _hurt(s, 3)  # still hurt...
    assert emergency_repair(s) is None  # ...but on cooldown, so it does not re-trigger


def test_emergency_repair_stays_quiet_above_the_threshold() -> None:
    s = _engineer()  # full HP
    assert emergency_repair(s) is None


# --- refusals -------------------------------------------------------------------
def test_only_an_engineer_can_scan() -> None:
    s = Session(player_id="matrym", location="courtyard")
    bind_calling(s, "vanguard")
    assert "Only an Engineer" in diagnostic_scan(s, "dummy")


def test_scanning_nothing_is_refused() -> None:
    s = _engineer()
    assert "no one like that here" in diagnostic_scan(s, "phantom")


def test_a_peaceful_target_cannot_be_scanned() -> None:
    s = _engineer(location="library")
    assert "inert" in diagnostic_scan(s, "librarian")  # a 0-HP NPC is not a combat target


def test_emergency_repair_is_engineer_only() -> None:
    s = Session(player_id="matrym")
    bind_calling(s, "vanguard")
    _hurt(s, 1)
    assert emergency_repair(s) is None


# --- the tick -------------------------------------------------------------------
def test_tick_counts_down_and_drops_expired_effects() -> None:
    s = _engineer()
    s.cooldowns["x"] = 2
    s.statuses["y"] = 1
    tick(s)
    assert s.cooldowns["x"] == 1 and "y" not in s.statuses  # y hit zero and was dropped


# --- engine-tick reachability ---------------------------------------------------
def test_repair_and_scan_are_reachable_through_the_tick() -> None:
    s = Session(player_id="matrym", location="courtyard")
    handle_command(s, "job engineer")
    assert "Field Repair" in handle_command(s, "repair")
    assert "Analyzed applied" in handle_command(s, "scan dummy")


# --- Power Cells + Deploy Barrier -----------------------------------------------
def test_the_engineer_starts_with_power_cells() -> None:
    s = _engineer()
    assert s.resources["power"].maximum == 6 and s.resources["power"].current == 6


def test_deploy_barrier_spends_power_and_raises_a_barrier() -> None:
    s = _engineer()
    out = deploy_barrier(s)
    assert s.resources["power"].current == 6 - engineer.DEPLOY_BARRIER_COST
    assert s.statuses["barrier"] == engineer.BARRIER_DURATION
    assert "deploy a barrier" in out


def test_deploy_barrier_refused_without_enough_power() -> None:
    s = _engineer()
    s.resources["power"] = Resource("power", 1, 6)  # below the cost
    assert "Not enough Power Cells" in deploy_barrier(s)


def test_power_regenerates_on_the_tick_capped_at_max() -> None:
    s = _engineer()
    s.resources["power"] = Resource("power", 2, 6)
    tick(s)
    assert s.resources["power"].current == 3  # +power_regen
    s.resources["power"] = Resource("power", 6, 6)
    tick(s)
    assert s.resources["power"].current == 6  # capped, never over max


def test_only_an_engineer_can_deploy() -> None:
    s = Session(player_id="matrym")
    bind_calling(s, "vanguard")
    assert "Only an Engineer" in deploy_barrier(s)


def test_a_job_without_power_cells_has_no_power_resource() -> None:
    s = Session(player_id="matrym")
    bind_calling(s, "vanguard")
    assert "power" not in s.resources


def test_deploy_reaches_through_the_tick() -> None:
    s = Session(player_id="matrym", location="courtyard")
    handle_command(s, "job engineer")
    assert "deploy a barrier" in handle_command(s, "deploy")
