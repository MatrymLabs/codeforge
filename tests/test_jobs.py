"""Test twin for parts/jobs.py -- chargen from seed to sheet."""

from forge import handle_command
from parts.jobs import JOBS, bind_calling
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
