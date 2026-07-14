"""Test twin for parts/chronicle.py -- the ship's memory (append-only hashed ledger).

Acceptance: records append and read back in order, the hash chain links each record to its
predecessor, read_latest/kind-filter/empty-store behave. Refusal (the point of a tamper-evident
log): an edited payload, a reordered chain, a malformed line, a missing field, an unknown kind, or
a non-object payload all fail loud with ChronicleError rather than returning a dishonest memory.
Every test uses tmp_path, so the real (git-tracked) chronicle/ dir is never touched.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from parts.chronicle import KINDS, ChronicleError, append, read, read_latest, render

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
        append("metric", {"v": 1}, commit="c", root=tmp_path)  # a later-slice kind, not yet valid


def test_non_object_payload_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(ChronicleError, match="must be an object"):
        append("evidence", ["not", "a", "dict"], commit="c", root=tmp_path)  # type: ignore[arg-type]


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
        read("incident", root=tmp_path)


def test_slice_one_ships_only_the_evidence_kind() -> None:
    # A guard so a later slice that widens KINDS updates this test deliberately.
    assert KINDS == ("evidence",)


# --- integration: arc_ledger.emit retains its evidence verdict in the Chronicle ----------------


def test_emit_retains_its_evidence_verdict_in_the_chronicle(tmp_path: Path) -> None:
    from parts.arc_ledger import emit

    emit("abc123", root=tmp_path, runner=lambda check: True)  # injected runner: no subprocess
    latest = read_latest("evidence", root=tmp_path)
    assert latest is not None
    assert latest.payload["status"] == "ready"
    assert latest.commit == "abc123"
    assert "test_evidence" in latest.payload["source"]


# --- the verb: reachable through the engine tick -----------------------------------------------


def test_chronicle_verb_reachable_through_the_engine_tick() -> None:
    from forge import handle_command
    from parts.session import Session

    out = handle_command(Session(player_id="matrym", location="courtyard"), "chronicle")
    assert "hronicle" in out.lower()  # empty or populated, the panel always names itself
