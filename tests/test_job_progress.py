"""Test twin for parts/job_progress.py -- per-job progression survives a restart.

Acceptance: taking a job opens a record; multiple jobs' records persist and restore
independently (changing jobs never erases a prior job's level). The round-trip goes through
a real character save/restore, so the foreign key is exercised the way the Postgres CI runs it.
"""

from __future__ import annotations

import copy

import pytest

from parts import npcs
from parts.characters import load_character, restore_character, save_character
from parts.job_progress import JobProgress, load_job_progress
from parts.jobs import bind_calling
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_world():
    npcs_snap = copy.deepcopy(npcs.NPCS)
    SESSIONS.clear()
    yield
    npcs.NPCS = npcs_snap
    SESSIONS.clear()


def test_taking_a_job_opens_a_progress_record() -> None:
    s = Session(player_id="matrym")
    bind_calling(s, "engineer")
    assert s.job_progress["engineer"] == JobProgress("engineer", job_level=1, jp=0, tp=0)


def test_a_prior_job_record_is_preserved_when_you_take_it_up_again() -> None:
    s = Session(player_id="matrym")
    bind_calling(s, "engineer")
    s.job_progress["engineer"] = JobProgress("engineer", job_level=7, jp=200, tp=400)
    bind_calling(s, "engineer")  # take it up again
    assert s.job_progress["engineer"].job_level == 7  # not reset to 1


def test_load_is_empty_for_an_unknown_character() -> None:
    assert load_job_progress("nobody_here") == {}


def test_multiple_job_records_survive_a_character_roundtrip() -> None:
    s = Session(player_id="matrym", location="courtyard", named=True)
    SESSIONS["matrym"] = s
    bind_calling(s, "engineer")
    s.job_progress["engineer"] = JobProgress("engineer", job_level=4, jp=90, tp=250)
    s.job_progress["scholar"] = JobProgress("scholar", job_level=2, jp=30, tp=60)
    save_character(s)

    fresh = Session(player_id="matrym")
    record = load_character("matrym")
    assert record is not None
    restore_character(fresh, record)
    assert fresh.job_progress["engineer"] == JobProgress("engineer", 4, 90, 250)
    assert fresh.job_progress["scholar"] == JobProgress("scholar", 2, 30, 60)


def test_an_unnamed_seat_persists_no_job_progress() -> None:
    s = Session(player_id="drifter")
    bind_calling(s, "engineer")  # a runtime record exists...
    save_character(s)  # ...but an unnamed seat is never saved
    assert load_job_progress("drifter") == {}


def test_the_secondary_job_survives_a_character_roundtrip():
    from parts.jobs import set_secondary

    s = Session(player_id="matrym", location="courtyard", named=True)
    SESSIONS["matrym"] = s
    bind_calling(s, "engineer")
    set_secondary(s, "scholar")
    save_character(s)
    fresh = Session(player_id="matrym")
    record = load_character("matrym")
    assert record is not None
    restore_character(fresh, record)
    assert fresh.secondary_job == "scholar"
    assert "scholar" in fresh.job_progress  # its separate record persisted too
