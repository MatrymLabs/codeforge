"""Test twin for parts/frameup.py -- the `inspect` frame-up of the whole machine."""

from __future__ import annotations

from parts.frameup import (
    GREEN,
    RED,
    YELLOW,
    SystemFrame,
    frame_up,
    inspect,
    overall,
    render_frameup,
)


def test_the_real_repo_frames_up_with_every_system() -> None:
    frames = frame_up()
    systems = {f.system for f in frames}
    assert "classification registry" in systems
    assert "quality gate (QA board)" in systems
    assert "veritasgate (truth)" in systems
    assert "career board" in systems
    assert "pioneer mode" in systems


def test_overall_is_worst_of_the_gating_systems() -> None:
    green = SystemFrame("a", GREEN, "")
    red = SystemFrame("b", RED, "")
    yellow = SystemFrame("c", YELLOW, "")
    assert overall([green, green]) == GREEN
    assert overall([green, yellow]) == YELLOW
    assert overall([green, yellow, red]) == RED  # red beats yellow


def test_info_rows_never_drag_the_overall_down() -> None:
    # A yellow INFO row (gating=False) must not turn a green machine yellow.
    frames = [SystemFrame("gate", GREEN, ""), SystemFrame("info", YELLOW, "", gating=False)]
    assert overall(frames) == GREEN


def test_the_real_repo_reads_green() -> None:
    # The shipped repo is healthy; the frame-up should say so (and this pins it staying so).
    assert overall(frame_up()) == GREEN


def test_render_shows_the_header_and_overall() -> None:
    out = render_frameup()
    assert "THE FORGE - FRAME-UP INSPECTION" in out
    assert "OVERALL:" in out
    assert "nothing stored, nothing faked" in out


def test_inspect_command_renders_the_frameup() -> None:
    assert "FRAME-UP INSPECTION" in inspect("")
    assert "FRAME-UP INSPECTION" in inspect("forge")  # `inspect the forge`
    assert "FRAME-UP INSPECTION" in inspect("the forge")


def test_inspect_subviews_reuse_each_system_renderer() -> None:
    assert "truth check" in inspect("truth")  # VeritasGate renderer
    assert inspect("qa").strip() != ""  # the QA board renderer
    assert inspect("pm").strip() != ""  # pm status renderer
    assert "Unknown inspect view" in inspect("nonsense")


def test_inspect_save_banks_the_frameup_via_the_reportwriter() -> None:
    out = inspect("save")
    assert "banked to reports/frameup/" in out
    assert "FRAME-UP INSPECTION" in out


def test_inspect_is_reachable_through_the_engine_tick() -> None:
    from forge import handle_command
    from parts.world.session import Session

    out = handle_command(Session(player_id="insp"), "inspect")
    assert "FRAME-UP INSPECTION" in out
