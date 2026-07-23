"""Test twin for parts/functions.py -- the Hardware Store functions check."""

from __future__ import annotations

from parts.functions import (
    _DEMOS,
    render_functions,
)


def test_every_live_demo_actually_runs() -> None:
    # Each registered demo must return a (call, output) pair without raising -- if a part
    # stopped working, its demo would blow up here, which is the point.
    for part_id, demo in _DEMOS.items():
        call, out = demo()
        assert isinstance(call, str) and call, part_id
        assert isinstance(out, str) and out, part_id


def test_report_writer_demo_prints_hello_world() -> None:
    call, out = _DEMOS["report-writer"]()
    assert "hello world" in out  # the part wrote it, for real, to a temp file


def test_rank_gate_demo_shows_refuse_and_allow() -> None:
    _call, out = _DEMOS["rank-gate"]()
    assert "refused" in out and "allowed" in out


def test_validated_loader_demo_fails_loud() -> None:
    _call, out = _DEMOS["validated-loader"]()
    assert "fails loud" in out


def test_safe_runner_demo_refuses_a_dangerous_command() -> None:
    _call, out = _DEMOS["safe-runner"]()
    assert "CommandRefused" in out and "never ran" in out


def test_event_ledger_demo_delivers_the_message() -> None:
    _call, out = _DEMOS["event-ledger"]()
    assert "hello world" in out


def test_gate_runner_demo_lists_the_gates() -> None:
    _call, out = _DEMOS["gate-runner"]()
    assert "gates" in out.lower()


def test_demoed_parts_run_live_and_newer_parts_cite_their_twins() -> None:
    # The 7 parts with hand-written demos run live; parts added as the catalog broadened are
    # verified by their real test twins ([tested]), never faked. Nothing is [manual].
    out = render_functions()
    assert "7 demonstrated live" in out
    assert "[tested]" in out  # the newer parts are honestly test-verified
    assert "[manual]" not in out  # every part is demonstrated or test-verified, never hand-waved


def test_render_lists_parts_with_run_or_tested_status() -> None:
    out = render_functions()
    assert "FUNCTIONS CHECK" in out
    assert "[runs]" in out  # at least one live demo
    assert "report-writer" in out and "rank-gate" in out
    assert "parts:" in out  # the summary line


def test_functions_reachable_through_the_engine_tick() -> None:
    from forge import handle_command
    from parts.world.session import Session

    out = handle_command(Session(player_id="fn"), "functions")
    assert "FUNCTIONS CHECK" in out
