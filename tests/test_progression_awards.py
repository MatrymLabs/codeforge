"""Test twin for parts/progression_awards.py -- the leveling engine, exercised directly.

These call the grants (award_xp/jp/tp) straight, with no combat in the loop: they pin the
curve-climbing math, the monotonic clamp, active-job isolation, and named-character
persistence. Combat's own twin (test_combat.py) proves the same grants fire through a
real `attack()`; this twin proves the engine in isolation.
"""

import pytest

from parts.events import bind_echo, unbind_echo
from parts.jobs import bind_calling
from parts.progression_awards import award_jp, award_tp, award_xp
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_sessions():
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def _fighter(job: str = "vanguard", location: str = "courtyard") -> Session:
    s = Session(player_id="matrym", location=location)
    SESSIONS["matrym"] = s
    bind_calling(s, job)
    return s


def test_level_up_crosses_the_locked_curve_and_grows_resources():
    s = _fighter()  # vanguard: sta 12, mag 4; level 2 needs 75 XP
    hp_before = s.resources["hp"].maximum
    message = award_xp(s, 80)
    assert "LEVEL UP" in message
    assert s.level == 2
    assert s.resources["hp"].maximum == hp_before + 4 + 12 // 4  # mk1 formula
    assert s.resources["hp"].is_full


def test_the_room_witnesses_the_level_up():
    s = _fighter()
    b = Session(player_id="bystander", location="courtyard")
    SESSIONS["bystander"] = b
    heard: list[str] = []
    bind_echo("bystander", heard.append)
    award_xp(s, 80)
    assert "Matrym has reached level 2!" in heard
    unbind_echo("bystander")


def test_awards_never_drain_progress_on_a_negative_amount():
    """Defense in depth: an award is a gain, never a loss - a negative amount (should be impossible
    after the loader refuses negative NPC xp) is clamped to zero, not subtracted from the player."""
    s = _fighter("engineer")
    s.xp = 100
    award_jp(s, 50)
    award_tp(s, 40)
    jp_before = s.job_progress["engineer"].jp
    tp_before = s.job_progress["engineer"].tp
    award_xp(s, -1000)
    award_jp(s, -1000)
    award_tp(s, -1000)
    assert s.xp == 100  # not drained
    assert s.job_progress["engineer"].jp == jp_before
    assert s.job_progress["engineer"].tp == tp_before


def test_jp_accrues_to_the_active_job_and_levels_it():
    s = _fighter("engineer")
    # cumulative JP to reach job level 2 is 60 (20 for lvl 1 + 40 for lvl 2).
    out = award_jp(s, 60)
    assert s.job_progress["engineer"].jp == 60
    assert s.job_progress["engineer"].job_level == 2  # crossed the threshold
    assert "advances to job level 2" in out


def test_a_small_jp_gain_accrues_without_leveling():
    s = _fighter("engineer")
    award_jp(s, 10)
    assert s.job_progress["engineer"].jp == 10
    assert s.job_progress["engineer"].job_level == 1  # below the level-2 threshold


def test_a_seat_with_no_active_job_earns_no_jp():
    s = Session(player_id="matrym")  # no calling taken
    assert award_jp(s, 50) == ""


def test_earned_jp_persists_for_a_named_character():
    from parts.characters import load_character, restore_character

    s = Session(player_id="matrym", location="courtyard", named=True)
    SESSIONS["matrym"] = s
    bind_calling(s, "engineer")
    award_jp(s, 45)  # a named seat persists on award
    fresh = Session(player_id="matrym")
    record = load_character("matrym")
    assert record is not None
    restore_character(fresh, record)
    assert fresh.job_progress["engineer"].jp == 45


def test_jp_only_touches_the_active_job():
    s = _fighter("engineer")
    from parts.job_progress import JobProgress

    s.job_progress["scholar"] = JobProgress("scholar", job_level=5, jp=200)
    award_jp(s, 30)
    assert s.job_progress["scholar"] == JobProgress("scholar", job_level=5, jp=200)  # untouched


def test_tp_accrues_to_the_active_job():
    s = _fighter("engineer")
    award_tp(s, 120)
    assert s.job_progress["engineer"].tp == 120


def test_no_active_job_earns_no_tp():
    assert award_tp(Session(player_id="matrym"), 50) == ""


def test_earned_tp_persists_for_a_named_character():
    from parts.characters import load_character, restore_character

    s = Session(player_id="matrym", location="courtyard", named=True)
    SESSIONS["matrym"] = s
    bind_calling(s, "engineer")
    award_tp(s, 75)
    fresh = Session(player_id="matrym")
    record = load_character("matrym")
    assert record is not None
    restore_character(fresh, record)
    assert fresh.job_progress["engineer"].tp == 75
