"""Test twin for parts/jobs.py -- chargen from seed to sheet."""

import pytest

from forge import handle_command
from parts.jobs import JOBS, bind_calling, calling_index
from parts.session import Session


def test_jobs_load_from_seed_with_labels():
    assert set(JOBS) == {"vanguard", "scholar", "artificer", "engineer"}
    assert JOBS["scholar"]["name"] == "Scholar"
    assert JOBS["scholar"]["stats"]["magic"] == 14


def test_assign_job_births_stats_and_resources():
    s = Session(player_id="matrym")
    message = bind_calling(s, "scholar")
    assert "way of the Scholar" in message
    assert s.job == "scholar"
    assert s.stats is not None
    assert s.stats.get("magic").base == 14
    assert s.resources["hp"].maximum == 20 + 8  # BASE_HP + stamina
    assert s.resources["mp"].maximum == 5 + 14  # BASE_MP + magic
    assert s.resources["hp"].is_full


def test_calling_index_aligns_names_even_with_a_long_label(monkeypatch: pytest.MonkeyPatch):
    """Hostile case: a seed names an 11-char calling next to short ones. The description column
    must still line up -- the old fixed :<10 width let a long label shove its name out of column."""
    fake = {
        "vanguard": {"name": "Vanguard", "description": "short label"},
        "emberwright": {"name": "Emberwright", "description": "long label (11 chars)"},
    }
    monkeypatch.setattr("parts.jobs.JOBS", fake)
    rows = [ln for ln in calling_index().splitlines() if " -- " in ln]
    name_columns = {ln.index(job["name"]) for ln, job in zip(rows, fake.values(), strict=True)}
    assert len(name_columns) == 1  # every calling's name starts at the same column


def test_unknown_calling_is_refused():
    s = Session(player_id="matrym")
    assert "no calling named" in bind_calling(s, "necromancer")
    assert s.job == ""
    assert s.stats is None


def test_score_before_choosing_points_to_jobs():
    s = Session(player_id="matrym")
    assert "no calling yet" in handle_command(s, "score")


def test_full_chargen_through_the_engine_tick():
    s = Session(player_id="matrym")
    assert "Callings" in handle_command(s, "jobs")
    handle_command(s, "job artificer")
    sheet = handle_command(s, "score")
    assert "Job: Artificer (Lv 1)" in sheet  # the rich JRPG score sheet
    assert "PLvl 1" in sheet  # player level separate from job level


def test_set_secondary_equips_a_subjob_and_opens_its_record():
    from parts.jobs import set_secondary

    s = Session(player_id="matrym")
    bind_calling(s, "engineer")
    out = set_secondary(s, "scholar")
    assert s.secondary_job == "scholar"
    assert "scholar" in s.job_progress  # its own record, tracked separately
    assert "Scholar" in out


def test_secondary_refusals():
    from parts.jobs import set_secondary

    fresh = Session(player_id="matrym")
    assert "primary calling first" in set_secondary(fresh, "scholar")  # no primary yet
    s = Session(player_id="matrym")
    bind_calling(s, "engineer")
    assert "no calling named" in set_secondary(s, "necromancer")
    assert "already your primary" in set_secondary(s, "engineer")


def test_the_sheet_shows_the_equipped_secondary():
    from parts.character_view import sheet_from_session
    from parts.jobs import set_secondary

    s = Session(player_id="matrym")
    bind_calling(s, "engineer")
    set_secondary(s, "scholar")
    sheet = sheet_from_session(s)
    assert sheet is not None and sheet.secondary_job == "Scholar (Lv 1)"


def test_subjob_reaches_through_the_tick():
    s = Session(player_id="matrym")
    handle_command(s, "job engineer")
    assert "secondary" in handle_command(s, "subjob scholar").lower()
