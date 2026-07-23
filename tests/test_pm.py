"""Test twin for parts/pm.py -- the project control panel.

The dashboard is DERIVED, not stored: it composes the registry and the QualityGate.
Acceptance (metrics count the real registry, status recommends a real next action)
and reachability through the tick are pinned.
"""

from collections.abc import Iterator

import pytest

from forge import handle_command
from parts.pm import ProjectMetrics, _recommended_next, pm_metrics, pm_status, project_metrics
from parts.world.session import SESSIONS, Session

# --- failure/edge branches (the "board is red/green" logic), injected deterministically ---


def test_recommended_next_prioritizes_failures() -> None:
    assert "Fix 2 failing" in _recommended_next(ProjectMetrics(total=5, qa_fail=2, qa_watch=3))


def test_recommended_next_then_docs_then_planned() -> None:
    assert "Link docs on 3" in _recommended_next(ProjectMetrics(total=3, docs_missing=3))
    assert "Build the next of 2" in _recommended_next(ProjectMetrics(total=2, qa_pass=0, planned=2))


def test_recommended_next_all_pass() -> None:
    assert "All filed objects pass" in _recommended_next(ProjectMetrics(total=4, qa_pass=4))


def test_pm_status_is_red_when_objects_fail() -> None:
    out = pm_status(metrics=ProjectMetrics(total=10, qa_fail=2, qa_watch=8))
    assert "RED" in out and "Fix 2 failing" in out


def test_pm_status_is_green_when_all_pass() -> None:
    out = pm_status(metrics=ProjectMetrics(total=10, qa_pass=10))
    assert "GREEN" in out
    assert "100%" in out  # ready_pct
    assert "Objects filed:" in pm_metrics(metrics=ProjectMetrics(total=10, qa_pass=10))


def test_metrics_are_computed_from_the_real_registry() -> None:
    m = project_metrics()
    # every object gets exactly one QA verdict, so the tally reconciles with the total
    assert m.qa_pass + m.qa_watch + m.qa_fail == m.total
    assert m.built + m.planned == m.total
    assert m.total >= 20  # rooms + commands + items are filed
    assert "CMD" in m.by_type and "RM" in m.by_type


def test_status_reports_a_color_and_a_next_action() -> None:
    out = pm_status()
    assert "CodeForge Project Status" in out
    assert any(c in out for c in ("GREEN", "YELLOW", "RED"))
    assert "Recommended next:" in out


def test_metrics_render_lists_types() -> None:
    out = pm_metrics()
    assert "Objects filed:" in out
    assert "QA readiness:" in out


# --- reachable through the engine tick ---------------------------------------


@pytest.fixture(autouse=True)
def fresh() -> Iterator[None]:
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def test_pm_status_through_the_tick() -> None:
    session = Session(player_id="pm")
    SESSIONS["pm"] = session
    out = handle_command(session, "pm status")
    assert "CodeForge Project Status" in out
    assert "Recommended next:" in out


def test_pm_metrics_through_the_tick() -> None:
    session = Session(player_id="pm")
    SESSIONS["pm"] = session
    assert "Objects filed:" in handle_command(session, "pm metrics")
