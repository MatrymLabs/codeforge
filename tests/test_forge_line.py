"""Test twin for parts/forge_line.py -- the manufacturing conveyor, offline + deterministic.

The Writer is a seam: a FakeWriter captures the filed content so no real report/ dir is created and
the whole line runs offline. Acceptance (token-bucket runs green through all eight stations) AND
refusal (an unknown id fails SEARCH and NAs the rest; a mixed-case/whitespaced id is a miss, never
silently normalized) AND the honest soft path (a part without a manifest WATCHes, never fails).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parts.forge_line import render_line, run_line
from parts.verdicts import FAIL, NA, PASS, WATCH

_STATIONS = [
    "SEARCH",
    "BLUEPRINT",
    "ASSEMBLE",
    "TEST",
    "DIAGNOSE",
    "DOCUMENT",
    "CATALOG+FILE",
    "PACKAGE",
]


class FakeWriter:
    """Captures (category, text) instead of writing; returns a synthetic path. Proves offline."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, category: str, text: str) -> Path:
        self.calls.append((category, text))
        return Path(f"/tmp/fake-{len(self.calls)}.md")


def _boom(*_a: object, **_k: object) -> object:
    raise AssertionError("the line must not reach a subprocess station")


def test_the_line_runs_token_bucket_green_through_all_eight_stations() -> None:
    fake = FakeWriter()
    run = run_line("token-bucket", writer=fake, stamp="2026-07-22")
    assert run.verdict == PASS
    assert [s.station for s in run.stations] == _STATIONS  # exactly 8, in loop order
    assert all(s.verdict in (PASS, WATCH) for s in run.stations)
    assert len(fake.calls) == 2  # DOCUMENT + PACKAGE are the only disk writes


def test_the_line_never_shells_a_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    # cast.validate_cast / install_check spawn subprocesses; the line must never touch them.
    import parts.cast as cast

    monkeypatch.setattr(cast, "validate_cast", _boom)
    monkeypatch.setattr(cast, "install_check", _boom)
    run = run_line("token-bucket", writer=FakeWriter(), stamp="2026-07-22")
    assert run.verdict == PASS  # ran clean without ever reaching a subprocess station


def test_an_unknown_part_fails_search_and_nas_the_rest() -> None:
    fake = FakeWriter()
    run = run_line("no-such-part", writer=fake, stamp="2026-07-22")
    assert run.verdict == FAIL
    assert run.stations[0].station == "SEARCH" and run.stations[0].verdict == FAIL
    assert all(s.verdict == NA for s in run.stations[1:-1])  # the six content stations skip cleanly
    assert run.stations[-1].verdict == FAIL  # PACKAGE reflects the failure
    assert len(fake.calls) == 1  # only PACKAGE writes; DOCUMENT was skipped, never crashed


@pytest.mark.parametrize("bad", ["Token-Bucket", " token-bucket ", "token_bucket"])
def test_the_line_does_not_lower_or_trim_a_data_label(bad: str) -> None:
    # exact-id only: a mixed-case / whitespaced / underscored id is a SEARCH miss, not fixed up
    run = run_line(bad, writer=FakeWriter(), stamp="2026-07-22")
    assert run.stations[0].verdict == FAIL


def test_a_part_without_a_manifest_watches_at_document_never_fails() -> None:
    # `deadline` is catalogued + filed but has no docs/hardware manifest -> DOCUMENT watch
    run = run_line("deadline", writer=FakeWriter(), stamp="2026-07-22")
    doc = next(s for s in run.stations if s.station == "DOCUMENT")
    assert doc.verdict == WATCH and "no part manifest" in doc.detail
    assert run.verdict == WATCH  # a soft gap holds the line off a clean pass, never fails it


def test_render_line_is_pure_and_one_line_per_station() -> None:
    run = run_line("token-bucket", writer=FakeWriter(), stamp="2026-07-22")
    text = render_line(run)
    assert render_line(run) == text  # pure: repeated render is identical, no disk write
    body = [line for line in text.splitlines() if line.startswith("[")]
    assert len(body) == len(run.stations) == 8
