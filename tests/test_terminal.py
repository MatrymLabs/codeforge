"""Test twin for parts/terminal.py -- the in-game computer terminal."""

from __future__ import annotations

from parts.terminal import _NAMES, _run, terminal


def test_boot_screen_lists_every_wired_program() -> None:
    out = terminal("")
    assert "Programs" in out and "diagnostic console" in out
    for name in _NAMES:
        assert name in out, f"{name} missing from the terminal menu"


def test_sticky_note_shows_the_basic_commands_to_get_in() -> None:
    out = terminal("")
    assert "STICKY NOTE" in out
    assert "workshop -> north" in out  # how to reach the console in the world
    assert "terminal <name>" in out  # how to run a program
    assert "terminal help" in out  # how to see the note again


def test_help_shows_the_boot_screen_with_the_note() -> None:
    assert "STICKY NOTE" in terminal("help")


def test_every_wired_program_actually_runs() -> None:
    # The terminal only wires existing renderers; each must produce real output, no crash.
    for name in _NAMES:
        body = _run(name)
        assert isinstance(body, str) and body.strip(), name
        assert not body.startswith("no such program"), name


def test_running_a_program_frames_it_like_a_terminal() -> None:
    out = terminal("functions")
    assert "FORGE TERMINAL $ terminal functions" in out
    assert "FUNCTIONS CHECK" in out  # the actual program output, framed
    assert "> _" in out  # the terminal prompt


def test_inspect_and_career_and_pm_are_reachable_from_the_terminal() -> None:
    assert "FRAME-UP INSPECTION" in terminal("inspect")
    assert "CAREER EVIDENCE SIGN" in terminal("career")
    assert terminal("pm").strip() != ""


def test_unknown_program_is_reported_not_run() -> None:
    out = terminal("rm -rf")
    assert "no such program" in out.lower()


def test_terminal_is_reachable_through_the_engine_tick() -> None:
    from forge import handle_command
    from parts.session import Session

    out = handle_command(Session(player_id="term"), "terminal")
    assert "Programs" in out and "diagnostic console" in out
