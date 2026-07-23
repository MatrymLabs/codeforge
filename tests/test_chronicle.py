"""Test twin for parts/chronicle.py -- the ship's memory (append-only hashed ledger).

Acceptance: records append and read back in order, the hash chain links each record to its
predecessor, read_latest/kind-filter/empty-store behave. Refusal (the point of a tamper-evident
log): an edited payload, a reordered chain, a malformed line, a missing field, an unknown kind, or
a non-object payload all fail loud with ChronicleError rather than returning a dishonest memory.
Nearly every test uses tmp_path, so the real (git-tracked) chronicle/ dir is never touched; the one
exception reads the retained ledger with an explicit repo root, on purpose, to pin that main's
Chronicle is not an empty vault.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from parts.chronicle import (
    KINDS,
    ChronicleError,
    ai_evals,
    append,
    incidents,
    provenance,
    read,
    read_latest,
    record_ai_eval,
    record_edge,
    record_incident,
    record_metric,
    render,
    render_ai_evals,
    render_incidents,
    render_provenance,
    render_trend,
    trend,
)

_STAMP = datetime(2026, 7, 14, 12, 0, 0, tzinfo=UTC)


def _ledger(root: Path) -> Path:
    return root / "chronicle" / "ledger.jsonl"


# --- acceptance --------------------------------------------------------------------------------


def test_append_then_read_round_trips(tmp_path: Path) -> None:
    append("evidence", {"dim": "tests", "status": "pass"}, commit="abc1234", root=tmp_path)
    records = read(root=tmp_path)
    assert len(records) == 1
    assert records[0].kind == "evidence"
    assert records[0].payload == {"dim": "tests", "status": "pass"}
    assert records[0].commit == "abc1234"


def test_the_chain_links_each_record_to_its_predecessor(tmp_path: Path) -> None:
    r1 = append("evidence", {"n": 1}, commit="c", root=tmp_path)
    r2 = append("evidence", {"n": 2}, commit="c", root=tmp_path)
    assert r1.prior_hash == ""  # genesis has no predecessor
    assert r2.prior_hash == r1.content_hash  # chained
    assert r1.content_hash != r2.content_hash


def test_read_latest_returns_the_newest(tmp_path: Path) -> None:
    append("evidence", {"seq": "first"}, commit="c", root=tmp_path)
    append("evidence", {"seq": "second"}, commit="c", root=tmp_path)
    latest = read_latest("evidence", root=tmp_path)
    assert latest is not None and latest.payload["seq"] == "second"


def test_empty_store_reads_as_empty_not_an_error(tmp_path: Path) -> None:
    assert read(root=tmp_path) == []
    assert read_latest("evidence", root=tmp_path) is None


def test_a_missing_commit_defaults_rather_than_crashing(tmp_path: Path) -> None:
    rec = append("evidence", {"x": 1}, commit="", root=tmp_path)
    assert rec.commit == "unknown"


def test_render_shows_records_and_reads_empty_state(tmp_path: Path) -> None:
    assert "empty" in render(read(root=tmp_path))
    append("evidence", {"dim": "lint"}, commit="deadbee", root=tmp_path, stamp=_STAMP)
    out = render(read(root=tmp_path))
    assert "THE CHRONICLE" in out and "evidence" in out and "deadbee" in out


# --- refusal / hostile -------------------------------------------------------------------------


def test_unknown_kind_fails_loud_on_append(tmp_path: Path) -> None:
    with pytest.raises(ChronicleError, match="unknown kind"):
        append(
            "retention", {"v": 1}, commit="c", root=tmp_path
        )  # a later-slice kind, not yet valid


def test_non_object_payload_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(ChronicleError, match="must be an object"):
        append("evidence", ["not", "a", "dict"], commit="c", root=tmp_path)  # type: ignore[arg-type]


def test_non_serializable_payload_fails_loud_as_chronicle_error(tmp_path: Path) -> None:
    """A dict is the right shape but a set inside it is not JSON-serializable. The contract is
    fail-loud with ChronicleError, not a raw TypeError the chronicle() verb can't catch."""
    with pytest.raises(ChronicleError, match="not JSON-serializable"):
        append("evidence", {"tags": {1, 2, 3}}, commit="c", root=tmp_path)
    assert read(root=tmp_path) == []  # the bad record never reached disk


def test_a_non_utc_stamp_is_converted_before_labelling_it_utc(tmp_path: Path) -> None:
    """recorded_utc must be the real UTC instant: a tz-aware stamp in another zone is converted,
    not just stamped with a 'Z' it hasn't earned."""
    from datetime import timedelta, timezone

    est = timezone(timedelta(hours=-5))
    rec = append(
        "evidence",
        {"x": 1},
        commit="c",
        root=tmp_path,
        stamp=datetime(2026, 1, 1, 5, 0, 0, tzinfo=est),
    )
    assert rec.recorded_utc == "2026-01-01T10:00:00Z"


def test_a_naive_stamp_is_taken_as_utc_unchanged(tmp_path: Path) -> None:
    """A naive stamp (no tzinfo) carries no zone to convert from, so it is taken as UTC as-is
    rather than being shifted by the host's local zone."""
    rec = append(
        "evidence", {"x": 1}, commit="c", root=tmp_path, stamp=datetime(2026, 1, 1, 5, 0, 0)
    )
    assert rec.recorded_utc == "2026-01-01T05:00:00Z"


def test_a_tampered_payload_is_detected_on_read(tmp_path: Path) -> None:
    append("evidence", {"status": "fail"}, commit="c", root=tmp_path)
    p = _ledger(tmp_path)
    # Flip the recorded outcome without recomputing the hash: the classic dishonest edit.
    p.write_text(p.read_text().replace('"fail"', '"pass"'), encoding="utf-8")
    with pytest.raises(ChronicleError, match="tampered"):
        read(root=tmp_path)


def test_a_reordered_chain_is_detected(tmp_path: Path) -> None:
    append("evidence", {"n": 1}, commit="c", root=tmp_path)
    append("evidence", {"n": 2}, commit="c", root=tmp_path)
    p = _ledger(tmp_path)
    first, second = p.read_text().splitlines()
    p.write_text(second + "\n" + first + "\n", encoding="utf-8")  # swap order -> chain breaks
    with pytest.raises(ChronicleError, match="broken chain"):
        read(root=tmp_path)


def test_a_malformed_line_fails_loud(tmp_path: Path) -> None:
    p = _ledger(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not valid json}\n", encoding="utf-8")
    with pytest.raises(ChronicleError, match="unreadable"):
        read(root=tmp_path)


def test_a_record_missing_a_field_fails_loud(tmp_path: Path) -> None:
    p = _ledger(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"kind": "evidence", "payload": {}}\n', encoding="utf-8")  # no hash/commit/etc
    with pytest.raises(ChronicleError, match="malformed record"):
        read(root=tmp_path)


def test_read_with_an_unknown_kind_fails_loud(tmp_path: Path) -> None:
    append("evidence", {"x": 1}, commit="c", root=tmp_path)
    with pytest.raises(ChronicleError, match="unknown kind"):
        read("retention", root=tmp_path)  # a later-slice kind, not yet valid


def test_kinds_are_the_five_shipped_kinds() -> None:
    # A guard so a later slice that widens KINDS updates this test deliberately.
    assert KINDS == ("evidence", "metric", "edge", "incident", "ai-eval")


# --- metric kind + trend series (slice 2) ------------------------------------------------------


def test_record_metric_round_trips(tmp_path: Path) -> None:
    rec = record_metric("engine_tick.median_us", 8.8, commit="aaa111", root=tmp_path)
    assert rec.kind == "metric"
    assert rec.payload == {"name": "engine_tick.median_us", "value": 8.8}
    latest = read_latest("metric", root=tmp_path)
    assert latest is not None and latest.payload["value"] == 8.8


def test_trend_returns_one_names_series_in_order(tmp_path: Path) -> None:
    record_metric("cov.pct", 90.0, commit="a", root=tmp_path, stamp=_STAMP)
    record_metric("engine_tick.median_us", 8.8, commit="a", root=tmp_path, stamp=_STAMP)
    record_metric("engine_tick.median_us", 8.5, commit="b", root=tmp_path, stamp=_STAMP)
    series = trend("engine_tick.median_us", root=tmp_path)
    assert [r.payload["value"] for r in series] == [8.8, 8.5]  # only this metric, in order


def test_render_trend_shows_the_net_direction(tmp_path: Path) -> None:
    record_metric("m", 10, commit="a", root=tmp_path, stamp=_STAMP)
    record_metric("m", 7, commit="b", root=tmp_path, stamp=_STAMP)
    out = render_trend("m", trend("m", root=tmp_path))
    assert "TREND - m" in out and "down 3" in out
    assert render_trend("absent", trend("absent", root=tmp_path)).startswith("No metric named")


def test_metric_refuses_a_non_numeric_value(tmp_path: Path) -> None:
    with pytest.raises(ChronicleError, match="must be a number"):
        record_metric("m", "fast", commit="a", root=tmp_path)  # type: ignore[arg-type]
    with pytest.raises(ChronicleError, match="must be a number"):
        record_metric("m", True, commit="a", root=tmp_path)  # bool is not a metric value


def test_metric_refuses_an_empty_name(tmp_path: Path) -> None:
    with pytest.raises(ChronicleError, match="non-empty string 'name'"):
        record_metric("   ", 1.0, commit="a", root=tmp_path)


def test_chronicle_trend_verb() -> None:
    from parts.chronicle import chronicle as verb

    assert verb("trend") == "usage: chronicle trend <metric-name>"
    # Reads the real (empty in tests) ledger; an unrecorded metric renders honestly, never crashes.
    assert verb("trend nonexistent_metric_xyz").startswith("No metric named")


# --- edge kind + provenance (slice 3) ----------------------------------------------------------


def test_record_edge_and_provenance_round_trip(tmp_path: Path) -> None:
    rec = record_edge("part:tb", "wasDerivedFrom", "blueprint:tb", commit="a", root=tmp_path)
    assert rec.kind == "edge"
    assert rec.payload == {"from": "part:tb", "relation": "wasDerivedFrom", "to": "blueprint:tb"}


def test_provenance_finds_a_node_as_either_endpoint(tmp_path: Path) -> None:
    record_edge("evidence:x", "wasGeneratedBy", "run:x", commit="x", root=tmp_path)
    record_edge("release:x", "wasInformedBy", "evidence:x", commit="x", root=tmp_path)
    around = provenance("evidence:x", root=tmp_path)
    assert len(around) == 2  # once as `from`, once as `to`
    assert provenance("unrelated", root=tmp_path) == []


def test_render_provenance_shows_edges_and_empty_state(tmp_path: Path) -> None:
    assert render_provenance("n", provenance("n", root=tmp_path)).startswith("No provenance")
    record_edge("n", "wasDerivedFrom", "src", commit="a", root=tmp_path)
    out = render_provenance("n", provenance("n", root=tmp_path))
    assert "PROVENANCE - n" in out and "n -wasDerivedFrom-> src" in out


def test_render_provenance_shows_a_self_loop_once(tmp_path: Path) -> None:
    """A self-loop edge (from == to) is one edge; it must render on one line, not double-count
    into both outgoing and incoming so the body contradicts the header's edge count."""
    record_edge("n", "wasDerivedFrom", "n", commit="c", root=tmp_path)
    out = render_provenance("n", provenance("n", root=tmp_path))
    assert "(1 edge(s))" in out
    assert out.count("-wasDerivedFrom->") == 1


def test_edge_refuses_an_unknown_relation(tmp_path: Path) -> None:
    with pytest.raises(ChronicleError, match="unknown edge relation"):
        record_edge("a", "causes", "b", commit="c", root=tmp_path)  # not a PROV-O relation


def test_edge_refuses_an_empty_endpoint(tmp_path: Path) -> None:
    with pytest.raises(ChronicleError, match="non-empty string 'to'"):
        record_edge("a", "wasDerivedFrom", "  ", commit="c", root=tmp_path)


def test_chronicle_provenance_verb() -> None:
    from parts.chronicle import chronicle as verb

    assert verb("provenance") == "usage: chronicle provenance <node>"
    assert verb("provenance nonexistent_node_xyz").startswith("No provenance")


# --- incident kind: FRACAS register (slice 4) --------------------------------------------------


def test_record_incident_round_trips(tmp_path: Path) -> None:
    rec = record_incident("gateway dropped a login", "high", commit="a", root=tmp_path)
    assert rec.kind == "incident"
    assert rec.payload["what"] == "gateway dropped a login"
    assert rec.payload["severity"] == "high"
    assert rec.payload["status"] == "open" and rec.payload["corrective_action"] == ""


def test_incidents_filter_by_status(tmp_path: Path) -> None:
    record_incident("a", "high", commit="c", root=tmp_path)
    record_incident(
        "b", "low", status="closed", corrective_action="fixed", commit="c", root=tmp_path
    )
    assert len(incidents(root=tmp_path)) == 2
    assert len(incidents("open", root=tmp_path)) == 1
    assert incidents("closed", root=tmp_path)[0].payload["corrective_action"] == "fixed"


def test_render_incidents_puts_open_and_severe_first(tmp_path: Path) -> None:
    record_incident("minor", "low", status="closed", commit="c", root=tmp_path)
    record_incident("urgent", "critical", commit="c", root=tmp_path)
    out = render_incidents(incidents(root=tmp_path))
    assert out.index("urgent") < out.index("minor")  # open+critical before closed+low
    assert render_incidents(incidents(root=tmp_path, status="none")) == "No incidents recorded."


def test_incident_refuses_a_bad_severity(tmp_path: Path) -> None:
    with pytest.raises(ChronicleError, match="severity must be one of"):
        record_incident("x", "urgent", commit="c", root=tmp_path)


def test_incident_refuses_an_empty_what(tmp_path: Path) -> None:
    with pytest.raises(ChronicleError, match="needs a non-empty 'what'"):
        record_incident("   ", "high", commit="c", root=tmp_path)


def test_incident_refuses_a_bad_status(tmp_path: Path) -> None:
    with pytest.raises(ChronicleError, match="status must be one of"):
        record_incident("x", "high", status="pending", commit="c", root=tmp_path)


def test_chronicle_incidents_verb() -> None:
    from parts.chronicle import chronicle as verb

    # Reads the real (empty in tests) ledger; renders honestly, never crashes.
    assert verb("incidents") == "No incidents recorded."


# --- ai-eval kind: scored AI/Advisor evaluation (slice 5) --------------------------------------


def test_record_ai_eval_round_trips(tmp_path: Path) -> None:
    rec = record_ai_eval(
        "arch.q1", 0.75, model="claude-opus-4-8", passed=True, commit="a", root=tmp_path
    )
    assert rec.kind == "ai-eval"
    assert rec.payload == {
        "subject": "arch.q1",
        "score": 0.75,
        "model": "claude-opus-4-8",
        "passed": True,
    }


def test_ai_evals_filter_by_subject(tmp_path: Path) -> None:
    record_ai_eval("q1", 1.0, model="m", passed=True, commit="a", root=tmp_path)
    record_ai_eval("q2", 0.2, model="m", passed=False, commit="a", root=tmp_path)
    assert len(ai_evals(root=tmp_path)) == 2
    assert [r.payload["subject"] for r in ai_evals("q1", root=tmp_path)] == ["q1"]


def test_render_ai_evals_flags_a_regression(tmp_path: Path) -> None:
    record_ai_eval("q", 1.0, model="m", passed=True, commit="a", root=tmp_path, stamp=_STAMP)
    record_ai_eval("q", 0.5, model="m", passed=True, commit="b", root=tmp_path, stamp=_STAMP)
    out = render_ai_evals(ai_evals(root=tmp_path))
    assert "q: 0.5" in out and "REGRESSION (was 1)" in out
    assert render_ai_evals([]) == "No AI evaluations recorded."


def test_ai_eval_refuses_a_score_out_of_range(tmp_path: Path) -> None:
    with pytest.raises(ChronicleError, match=r"in \[0.0, 1.0\]"):
        record_ai_eval("q", 1.5, model="m", passed=True, commit="a", root=tmp_path)


def test_ai_eval_refuses_an_empty_subject_and_non_bool_passed(tmp_path: Path) -> None:
    with pytest.raises(ChronicleError, match="non-empty 'subject'"):
        record_ai_eval("  ", 0.5, model="m", passed=True, commit="a", root=tmp_path)
    with pytest.raises(ChronicleError, match="'passed' must be a bool"):
        record_ai_eval("q", 0.5, model="m", passed="yes", commit="a", root=tmp_path)  # type: ignore[arg-type]


def test_chronicle_evals_verb() -> None:
    from parts.chronicle import chronicle as verb

    assert verb("evals") == "No AI evaluations recorded."


# --- integration: arc_ledger.emit retains its evidence verdict in the Chronicle ----------------


def test_emit_opens_a_fracas_incident_on_a_blocked_release(tmp_path: Path) -> None:
    from parts.arc_ledger import emit

    emit("badsha", root=tmp_path, runner=lambda check: check != "security")  # security fails
    opened = incidents("open", root=tmp_path)
    assert len(opened) == 1
    assert opened[0].payload["severity"] == "high"
    assert "release blocked" in opened[0].payload["what"]


def test_a_ready_release_files_no_incident(tmp_path: Path) -> None:
    from parts.arc_ledger import emit

    emit("goodsha", root=tmp_path, runner=lambda check: True)
    assert incidents(root=tmp_path) == []  # no failure -> no FRACAS noise


def test_emit_retains_its_evidence_verdict_in_the_chronicle(tmp_path: Path) -> None:
    from parts.arc_ledger import emit

    emit("abc123", root=tmp_path, runner=lambda check: True)  # injected runner: no subprocess
    latest = read_latest("evidence", root=tmp_path)
    assert latest is not None
    assert latest.payload["status"] == "ready"
    assert latest.commit == "abc123"
    assert "test_evidence" in latest.payload["source"]


def test_emit_records_the_gate_runs_provenance_edges(tmp_path: Path) -> None:
    from parts.arc_ledger import emit

    emit("sha9", root=tmp_path, runner=lambda check: True)
    around = provenance("evidence:sha9", root=tmp_path)
    relations = {e.payload["relation"] for e in around}
    assert relations == {"wasGeneratedBy", "wasInformedBy"}  # generated by the run, informs release


# --- the verb: reachable through the engine tick -----------------------------------------------


def test_chronicle_verb_reachable_through_the_engine_tick() -> None:
    from forge import handle_command
    from parts.world.session import Session

    out = handle_command(Session(player_id="matrym", location="courtyard"), "chronicle")
    assert "hronicle" in out.lower()  # empty or populated, the panel always names itself


def test_the_retained_chronicle_is_not_an_empty_vault():
    """The ship's memory carries real, hash-chained evidence on main -- not a README-only vault.

    Discharges the 2026-07-17 convergence review's residual "orphaned last inch": the Chronicle core
    + producers existed, but nothing ran + retained a ledger. `make daily` now records the ARC gate
    verdict, so the store accumulates on the human ritual. conftest quarantines the Chronicle for
    every test (even an explicit repo root), so this reads the committed ledger FILE directly to
    check main's real state, not the empty tmp store."""
    import json
    from pathlib import Path

    ledger = Path(__file__).resolve().parent.parent / "chronicle" / "ledger.jsonl"
    assert ledger.is_file(), "no retained Chronicle ledger on main -- run `make arc-verdicts`"
    records = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    assert len(records) >= 1, "the retained Chronicle is empty -- run `make arc-verdicts`"
    assert any(
        r["kind"] == "evidence" for r in records
    )  # at least one retained, cited gate verdict


def test_make_daily_records_to_the_chronicle():
    """The wired last inch: `make daily` runs arc-verdicts, which appends the gate verdict to the
    retained Chronicle. So the store keeps accumulating on the HUMAN ritual cadence (not a robot
    auto-committing from CI, which the keel deferred). Pins the wiring vs a silent regression."""
    from pathlib import Path

    makefile = (Path(__file__).resolve().parent.parent / "Makefile").read_text(encoding="utf-8")
    daily = next(line for line in makefile.splitlines() if line.startswith("daily:"))
    assert "arc-verdicts" in daily
