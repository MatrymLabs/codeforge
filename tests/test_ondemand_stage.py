"""CARD: test_ondemand_stage -- twin for ondemand_stage (acceptance + hostile refusal cases)."""

from __future__ import annotations

import pytest

from kernel.shelf.ondemand_stage import Stage, StageError, progress, stage_at


def _crop() -> list[Stage]:
    # Classic crop growth timeline.
    return [
        Stage("seed", 0),
        Stage("sprout", 10),
        Stage("ripe", 30),
        Stage("withered", 60),
    ]


# --- acceptance --------------------------------------------------------------


def test_before_first_threshold_is_stage_zero() -> None:
    # start at beat 100, observed at 105 -> elapsed 5 -> still seed.
    assert stage_at(_crop(), 100, 105).name == "seed"


def test_at_start_is_stage_zero() -> None:
    assert stage_at(_crop(), 100, 100).name == "seed"


def test_exactly_at_threshold_advances() -> None:
    # elapsed exactly 10 -> sprout begins.
    assert stage_at(_crop(), 0, 10).name == "sprout"


def test_between_thresholds_is_the_lower() -> None:
    # elapsed 29 -> sprout (ripe not yet at 30).
    assert stage_at(_crop(), 0, 29).name == "sprout"


def test_past_last_threshold_is_last_stage() -> None:
    assert stage_at(_crop(), 0, 9999).name == "withered"


def test_exactly_at_last_threshold_is_last_stage() -> None:
    assert stage_at(_crop(), 0, 60).name == "withered"


def test_progress_reports_next_and_countdown() -> None:
    # elapsed 5: current seed, next sprout at 10, 5 beats to go.
    current, upcoming, countdown = progress(_crop(), 0, 5)
    assert current.name == "seed"
    assert upcoming is not None and upcoming.name == "sprout"
    assert countdown == 5


def test_progress_countdown_at_boundary() -> None:
    # elapsed 10: just entered sprout, next is ripe at 30, 20 beats out.
    current, upcoming, countdown = progress(_crop(), 0, 10)
    assert current.name == "sprout"
    assert upcoming is not None and upcoming.name == "ripe"
    assert countdown == 20


def test_progress_last_stage_next_is_none() -> None:
    current, upcoming, countdown = progress(_crop(), 0, 100)
    assert current.name == "withered"
    assert upcoming is None
    assert countdown == 0


def test_single_stage_timeline() -> None:
    only = [Stage("static", 0)]
    assert stage_at(only, 0, 500).name == "static"
    assert progress(only, 0, 500) == (Stage("static", 0), None, 0)


# --- refusal -----------------------------------------------------------------


def test_empty_stages_fails_loud() -> None:
    with pytest.raises(StageError):
        stage_at([], 0, 0)


def test_first_at_beat_not_zero_fails_loud() -> None:
    with pytest.raises(StageError):
        stage_at([Stage("seed", 5), Stage("ripe", 30)], 0, 10)


def test_non_increasing_at_beats_fails_loud() -> None:
    with pytest.raises(StageError):
        stage_at([Stage("seed", 0), Stage("ripe", 10), Stage("bad", 10)], 0, 5)


def test_decreasing_at_beats_fails_loud() -> None:
    with pytest.raises(StageError):
        stage_at([Stage("seed", 0), Stage("ripe", 30), Stage("bad", 20)], 0, 5)


def test_now_before_start_fails_loud() -> None:
    with pytest.raises(StageError):
        stage_at(_crop(), 100, 50)


def test_non_snake_case_name_fails_loud() -> None:
    with pytest.raises(StageError):
        stage_at([Stage("seed", 0), Stage("Ripe", 30)], 0, 5)


def test_symbol_name_fails_loud() -> None:
    with pytest.raises(StageError):
        stage_at([Stage("seed", 0), Stage("ri-pe", 30)], 0, 5)
