"""Test twin for parts/world/encounter_log.py -- the after-action log (aggression's 'observed' leg).

Pins the two design invariants (this store is bounded, and it never reaches the Chronicle) plus the
wiring: the player's tick actually produces telemetry, and the `encounters` verb renders it.
"""

import copy
import inspect

import pytest

from parts.world import encounter_log, npcs
from parts.world.encounter_log import (
    CAP,
    EncounterError,
    recent,
    render_recent,
    reset,
    tally,
    witness,
)
from parts.world.seed import Npc
from parts.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_log():
    reset()
    npcs_snap = copy.deepcopy(npcs.NPCS)
    SESSIONS.clear()
    yield
    npcs.NPCS.clear()
    npcs.NPCS.update(npcs_snap)
    SESSIONS.clear()
    reset()


def _fighter(location: str = "courtyard") -> Session:
    from parts.world.jobs import bind_calling

    s = Session(player_id="matrym", location=location)
    bind_calling(s, "vanguard")
    SESSIONS["matrym"] = s
    return s


# --- unit behaviour ----------------------------------------------------------


def test_witness_records_and_tallies():
    witness("open_strike", "the Cinder-Wight", "struck first")
    events = recent()
    assert len(events) == 1
    assert events[0].kind == "open_strike"
    assert events[0].who == "the Cinder-Wight"
    assert tally()["open_strike"] == 1


def test_recent_returns_newest_last_within_the_limit():
    for i in range(5):
        witness("defeat", f"foe{i}")
    last_two = recent(limit=2)
    assert [e.who for e in last_two] == ["foe3", "foe4"]


def test_the_ring_is_bounded_and_rolls_under_flood():
    for i in range(CAP + 50):  # more than the ring holds
        witness("open_strike", f"foe{i}")
    events = recent()
    assert len(events) == CAP  # older ones rolled off, never unbounded growth
    assert events[-1].who == f"foe{CAP + 49}"  # the newest survived
    assert tally()["open_strike"] == CAP + 50  # the tally still counts every beat


def test_an_unknown_kind_fails_loud():
    with pytest.raises(EncounterError, match="unknown encounter kind"):
        witness("nonsense", "the foe")


def test_an_empty_who_fails_loud():
    with pytest.raises(EncounterError, match="needs a 'who'"):
        witness("defeat", "   ")


def test_render_is_honest_when_empty_and_populated():
    assert "No encounters logged yet." in render_recent()
    witness("fall", "the Cinder-Wight")
    out = render_recent()
    assert "The Cinder-Wight" in out  # sentence-cased at render
    assert "fall: 1" in out  # the tally line


# --- the security invariant: the tick's log never reaches the Chronicle ------


def test_encounter_log_never_imports_the_chronicle():
    """The whole point: the player tick writes here, so this module must not touch the
    tamper-evident hash-chained ledger. If it ever imports chronicle, the poisoning surface the
    design forbids is back. (Prose may NAME the Chronicle; only an import is banned.)"""
    import_lines = [
        line
        for line in inspect.getsource(encounter_log).splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    assert import_lines  # sanity: we found the import block
    assert not any("chronicle" in line.lower() for line in import_lines)


# --- wiring: the tick produces telemetry, and the verb renders it ------------


def test_the_encounters_verb_renders_through_the_tick():
    from forge import handle_command

    witness("defeat", "the training dummy")
    out = handle_command(_fighter(), "encounters")
    assert "after-action log" in out
    assert "defeat: 1" in out


def test_felling_a_foe_witnesses_a_defeat():
    from parts.world.combat import attack

    s = _fighter()
    for _ in range(10):  # strike until the dummy collapses
        if "collapses" in attack(s, "dummy"):
            break
    assert tally()["defeat"] >= 1
    assert any(e.kind == "defeat" for e in recent())


def test_an_aggressive_open_strike_is_witnessed():
    from parts.world.aggression import menace

    npcs.NPCS["reaver"] = Npc(
        name="the reaver",
        keywords=["reaver"],
        location="courtyard",
        dialogue=["..."],
        next_line=0,
        hp=30,
        hp_now=30,
        xp=10,
        atk=5,
        aggressive=True,
    )
    menace(_fighter("courtyard"))
    assert tally()["open_strike"] == 1
    assert recent()[-1].kind == "open_strike"
