"""Test twin for kernel/domains/journey.py -- generate a GameSpec from a compact journey intent.

Acceptance (end to end, on the real Linker + engine): a one-line journey (a region + an ordered list
of waypoints) generates a GameSpec that LINKS through game_linker and OPERATES-AND-RESUMES through
game_session -- so a whole playable, durable, recoverable region comes from a short description. The
generation is deterministic (same waypoints -> byte-identical linked content).

Refusal (fail loud): no waypoints, a duplicate label, or a non-snake_case label is a JourneyError --
caught early, before the Linker would reject it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.domains.game_linker import LINKED, link_and_validate, link_region
from kernel.domains.game_session import RESUMED, operate_and_recover
from kernel.domains.journey import JourneyError, journey_region

_WAYPOINTS = ["greenhold", "riverside", "summit"]


# --- acceptance: a generated journey links, operates, and resumes --------------------------------


def test_a_generated_journey_links(tmp_path: Path) -> None:
    spec = journey_region("veridia", _WAYPOINTS)
    linked, verdict = link_and_validate(spec, tmp_path)
    assert verdict.verdict == LINKED and verdict.quest is True
    assert linked.rooms_linked == 4  # trailhead + 3 waypoints


def test_a_generated_journey_operates_and_resumes(tmp_path: Path) -> None:
    # The whole point: a short intent -> a region a live player can travel and recover.
    report = operate_and_recover(journey_region("veridia", _WAYPOINTS), tmp_path)
    assert report.verdict == RESUMED and report.terminal == "arrived"


def test_a_single_waypoint_journey_resumes(tmp_path: Path) -> None:
    report = operate_and_recover(journey_region("short", ["the_end"]), tmp_path)
    assert report.verdict == RESUMED and report.terminal == "arrived"


def test_generation_is_deterministic(tmp_path: Path) -> None:
    a = link_region(journey_region("veridia", _WAYPOINTS), tmp_path / "a")
    b = link_region(journey_region("veridia", _WAYPOINTS), tmp_path / "b")
    assert a.checksums == b.checksums  # same intent -> byte-identical linked content


# --- refusal: fail loud, before the Linker would ------------------------------------------------


def test_no_waypoints_is_refused() -> None:
    with pytest.raises(JourneyError):
        journey_region("empty", [])


def test_no_region_is_refused() -> None:
    with pytest.raises(JourneyError):
        journey_region("  ", ["a"])


def test_a_bad_label_is_refused() -> None:
    with pytest.raises(JourneyError):
        journey_region("r", ["Bad Waypoint"])


def test_a_duplicate_label_is_refused() -> None:
    with pytest.raises(JourneyError):
        journey_region("r", ["camp", "camp"])  # two identical waypoints


def test_a_waypoint_colliding_with_the_start_is_refused() -> None:
    with pytest.raises(JourneyError):
        journey_region("r", ["trailhead"])  # collides with the default start label
