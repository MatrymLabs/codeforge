"""Test twin for parts/arc_ledger.py -- file/read runtime ARC verdicts, and the evidence driver.

Acceptance: a filed verdict round-trips and the newest wins; the driver files release+evidence from
real check outcomes. Refusal: an absent dir reads as None (-> MISSING), and a bad status / unknown
dimension / empty source / malformed artifact fails loud rather than rendering a false verdict.
"""

from datetime import UTC, datetime

import pytest

from parts.arc_ledger import VerdictError, emit, read_latest, record_verdict


def test_record_then_read_round_trips(tmp_path):
    record_verdict("release", "ready", "release_gate: 4/4 passed", commit="abc123", root=tmp_path)
    verdict = read_latest("release", root=tmp_path)
    assert verdict is not None
    assert verdict.status == "ready" and verdict.commit == "abc123"
    assert "release_gate" in verdict.source


def test_read_latest_of_an_absent_dir_is_none(tmp_path):
    # No filed verdict -> None -> the dimension is MISSING (the honesty default).
    assert read_latest("release", root=tmp_path) is None


def test_the_newest_verdict_wins(tmp_path):
    old = datetime(2026, 7, 10, tzinfo=UTC)
    new = datetime(2026, 7, 12, tzinfo=UTC)
    record_verdict("release", "blocked", "old", commit="a", root=tmp_path, stamp=old)
    record_verdict("release", "ready", "new", commit="b", root=tmp_path, stamp=new)
    assert read_latest("release", root=tmp_path).status == "ready"


# --- refusal: hostile artifacts fail loud -------------------------------------


def test_record_refuses_a_bad_status(tmp_path):
    with pytest.raises(VerdictError):
        record_verdict("release", "green", "x", commit="a", root=tmp_path)


def test_record_refuses_an_unknown_dimension(tmp_path):
    with pytest.raises(VerdictError):
        record_verdict("architecture", "ready", "x", commit="a", root=tmp_path)


def test_record_refuses_an_empty_source(tmp_path):
    with pytest.raises(VerdictError):
        record_verdict("release", "ready", "   ", commit="a", root=tmp_path)


def test_a_malformed_artifact_fails_loud(tmp_path):
    directory = tmp_path / "arc-evidence"
    directory.mkdir()
    (directory / "2026-07-12-release.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(VerdictError):
        read_latest("release", root=tmp_path)


def test_a_partial_artifact_fails_loud(tmp_path):
    directory = tmp_path / "arc-evidence"
    directory.mkdir()
    (directory / "2026-07-12-release.json").write_text('{"dimension": "release"}', encoding="utf-8")
    with pytest.raises(VerdictError):
        read_latest("release", root=tmp_path)


# --- the driver: emit() files release+evidence from injected, real outcomes ----


def test_emit_files_release_and_evidence_when_checks_pass(tmp_path):
    filed = emit("abc123", root=tmp_path, runner=lambda check: True)
    names = {p.name.split("-", 3)[-1] for p in filed}
    assert names == {"release.json", "evidence.json"}
    assert read_latest("release", root=tmp_path).status == "ready"
    assert read_latest("evidence", root=tmp_path).status == "ready"


def test_emit_records_a_failing_check_as_blocked(tmp_path):
    # security fails -> release blocked; evidence (tests+coverage) still ready.
    emit("abc123", root=tmp_path, runner=lambda check: check != "security")
    assert read_latest("release", root=tmp_path).status == "blocked"
    assert read_latest("evidence", root=tmp_path).status == "ready"


def test_emit_does_not_file_change_or_patch(tmp_path):
    # No persistent store yet: change/patch are never filed, so they stay MISSING by absence.
    emit("abc123", root=tmp_path, runner=lambda check: True)
    assert read_latest("change", root=tmp_path) is None
    assert read_latest("patch", root=tmp_path) is None


def test_a_well_formed_artifact_with_a_bad_status_fails_loud(tmp_path):
    directory = tmp_path / "arc-evidence"
    directory.mkdir()
    (directory / "2026-07-12-release.json").write_text(
        '{"dimension":"release","status":"green","source":"x","commit":"a","recorded_utc":"t"}',
        encoding="utf-8",
    )
    with pytest.raises(VerdictError):
        read_latest("release", root=tmp_path)


def test_a_well_formed_artifact_without_a_source_fails_loud(tmp_path):
    directory = tmp_path / "arc-evidence"
    directory.mkdir()
    (directory / "2026-07-12-release.json").write_text(
        '{"dimension":"release","status":"ready","source":"  ","commit":"a","recorded_utc":"t"}',
        encoding="utf-8",
    )
    with pytest.raises(VerdictError):
        read_latest("release", root=tmp_path)


def test_console_runner_maps_an_allowlisted_result_to_a_bool(monkeypatch):
    # The default runner is the safe console runner; here we prove the mapping without a subprocess.
    from types import SimpleNamespace

    import parts.arc_ledger as mod

    monkeypatch.setattr(
        "parts.console.run", lambda check, allowlist=None: SimpleNamespace(ok=(check == "lint"))
    )
    assert mod._console_runner("lint") is True
    assert mod._console_runner("security") is False


def test_main_usage_is_refused_without_the_emit_verb(capsys):
    from parts.arc_ledger import main

    assert main([]) == 2
    assert main(["wibble"]) == 2
    assert "usage:" in capsys.readouterr().out


def test_main_emit_files_and_reports(monkeypatch, capsys, tmp_path):
    import parts.arc_ledger as mod

    monkeypatch.setattr(mod, "emit", lambda commit: [tmp_path / "2026-07-13-release.json"])
    assert mod.main(["emit", "abc123"]) == 0
    out = capsys.readouterr().out
    assert "filed 2026-07-13-release.json" in out
    assert "no persistent store yet" in out
