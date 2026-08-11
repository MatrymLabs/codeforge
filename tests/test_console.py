"""Test twin for kernel/shelf/console.py -- the FailsafeRunner.

The safety properties are the point: only allowlisted commands run, timeouts kill
hung ones, output is capped, and nothing is ever shell-parsed. Fakes are injected
so tests stay fast and hermetic; the real allowlist is exercised only via the
always-available `version` entry."""

import sys

import pytest

from forge import handle_command
from kernel.shelf import console
from kernel.shelf.console import CommandRefused, console_menu, run, run_view
from kernel.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_sessions():
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def _player() -> Session:
    session = Session(player_id="builder")
    SESSIONS["builder"] = session
    return session


def test_allowlisted_version_runs_read_only():
    result = run("version")
    assert result.ok
    assert "Python" in result.output


def test_unlisted_command_is_refused_and_never_runs():
    # Neither a shell string nor an arbitrary program is a valid key -> refused.
    with pytest.raises(CommandRefused):
        run("rm -rf /")
    with pytest.raises(CommandRefused):
        run("version; whoami")  # no shell parsing: this is just an unknown key


def test_timeout_kills_a_hung_command():
    slow = {"sleep": [sys.executable, "-c", "import time; time.sleep(5)"]}
    result = run("sleep", allowlist=slow, timeout=0.5)
    assert result.timed_out
    assert not result.ok


def test_output_is_capped():
    loud = {"loud": [sys.executable, "-c", "print('x' * 10000)"]}
    result = run("loud", allowlist=loud, cap=100)
    assert len(result.output) <= 100 + 40  # cap plus the short truncation notice
    assert "truncated" in result.output


def test_missing_executable_is_reported_not_raised():
    ghost = {"ghost": ["definitely-not-a-real-binary-xyz"]}
    result = run("ghost", allowlist=ghost)
    assert not result.ok
    assert "not found" in result.output


def test_console_menu_lists_the_allowlist():
    menu = console_menu()
    assert "allowlisted" in menu.lower()
    assert "version" in menu and "lint" in menu


def test_console_commands_reachable_through_the_tick():
    session = _player()
    assert "allowlisted" in handle_command(session, "console").lower()
    assert "Python" in handle_command(session, "run version")
    assert "not an allowlisted" in handle_command(session, "run bogus")


def test_run_view_refuses_unknown_without_running():
    assert "not an allowlisted" in run_view("bogus")


# --- the console's own honesty: an allowlist that outlives its targets -------------------------
# `run compile` reported a GREEN CHECKMARK for nine days while printing "Can't list 'parts'".
# compileall exits 0 when it cannot find its targets, so a command that compiled nothing announced
# success. These pin that a stale allowlist can never do that again.


def test_repo_root_is_the_repository_not_a_package_directory():
    """It was parent.parent, correct as parts/console.py and wrong the moment it moved."""
    assert (console.REPO_ROOT / "pyproject.toml").is_file()
    assert (console.REPO_ROOT / "forge.py").is_file()
    assert console.REPO_ROOT.name != "kernel"


def test_every_declared_target_actually_exists_today():
    """The regression guard. A restructure that moves a directory reddens here, loudly."""
    assert console.stale_commands() == {}, (
        f"the allowlist points at paths that no longer exist: {console.stale_commands()}"
    )


def test_a_command_whose_target_vanished_is_refused_and_never_runs(monkeypatch):
    monkeypatch.setitem(console.TARGETS, "compile", ("parts", "forge.py"))  # the retired directory
    with pytest.raises(console.CommandRefused) as caught:
        console.run("compile")
    assert "parts" in str(caught.value)
    assert "never ran" in str(caught.value)


def test_a_stale_command_is_reported_rather_than_reported_green(monkeypatch):
    monkeypatch.setitem(console.TARGETS, "types", ("parts",))
    assert console.stale_commands() == {"types": ("parts",)}
    view = console.run_view("types")
    assert "✓" not in view  # the whole defect: a checkmark over a measurement never taken
    assert "stale" in view


def test_missing_targets_is_empty_for_a_command_that_declares_none():
    assert console.missing_targets("version") == ()
    assert console.missing_targets("status") == ()
