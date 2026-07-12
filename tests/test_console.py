"""Test twin for parts/console.py -- the FailsafeRunner.

The safety properties are the point: only allowlisted commands run, timeouts kill
hung ones, output is capped, and nothing is ever shell-parsed. Fakes are injected
so tests stay fast and hermetic; the real allowlist is exercised only via the
always-available `version` entry."""

import sys

import pytest

from forge import handle_command
from parts.console import CommandRefused, console_menu, run, run_view
from parts.session import SESSIONS, Session


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
