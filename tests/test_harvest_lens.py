"""Test twin for parts/harvest_lens.py -- detect reusable-pattern candidates in source."""

import pytest

from forge import handle_command
from parts.harvest_lens import (
    Candidate,
    HarvestError,
    draft_card,
    render_candidates,
    scan_source,
    stocked_signals,
)
from parts.world.session import Session

_SRC = '''
class RetryPolicy:
    """Retry with backoff."""


class TaskQueue:
    """A queue of tasks."""


def plain_helper():
    return 1
'''


def test_scan_finds_pattern_candidates():
    signals = {c.signal for c in scan_source(_SRC)}
    assert "retry" in signals  # name + docstring
    assert "queue" in signals  # name + docstring
    assert "backoff" in signals  # docstring of RetryPolicy


def test_stocked_signals_are_not_reflagged():
    signals = {c.signal for c in scan_source(_SRC, stocked=frozenset({"retry", "backoff"}))}
    assert "retry" not in signals
    assert "queue" in signals  # still surfaced


def test_plain_code_yields_no_candidates():
    assert scan_source("def add(a, b):\n    return a + b\n") == []


def test_bad_source_fails_loud():
    with pytest.raises(HarvestError):
        scan_source("def oops(:\n")


def test_stocked_signals_reads_catalog_text():
    stocked = stocked_signals("tags: [retry, backoff]\npurpose: a retry policy")
    assert "retry" in stocked
    assert "queue" not in stocked


def test_draft_card_stub():
    card = draft_card(Candidate("TaskQueue", "queue", "queue / task queue", 3))
    assert card["id"] == "queue-candidate"
    assert "candidate" in card["status"]


def test_render_reports_empty_and_findings():
    assert "store is current" in render_candidates([])
    out = render_candidates([Candidate("Pool", "pool", "resource pool", 5)])
    assert "Pool" in out
    assert "resource pool" in out


def test_harvest_verb_scans_the_repo_and_is_tick_reachable():
    out = handle_command(Session(player_id="matrym", location="courtyard"), "harvest")
    assert "Harvest Lens" in out
