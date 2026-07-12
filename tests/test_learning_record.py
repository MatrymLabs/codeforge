"""Test twin for parts/learning_record.py -- capture engineering improvements as evidence."""

import json

import pytest

from forge import handle_command
from parts.learning_record import (
    LearningRecordError,
    from_dict,
    learnings,
    load_all,
    load_record,
    to_markdown,
)
from parts.session import Session

_GOOD = {
    "record_id": "sample-lesson",
    "title": "A Sample Lesson",
    "date": "2026-07-12",
    "what_changed": "we did a thing",
    "why": "because it was better",
    "evidence": ["tests green", "coverage up"],
    "tradeoffs": "some churn",
    "future_reuse": "a candidate part",
    "concepts": ["identity vs classification"],
}


def test_valid_record_parses():
    rec = from_dict(_GOOD)
    assert rec.record_id == "sample-lesson"
    assert rec.evidence == ("tests green", "coverage up")
    assert rec.concepts == ("identity vs classification",)


def test_markdown_projection_has_every_section():
    md = to_markdown(from_dict(_GOOD))
    for heading in ("What changed", "Why", "Evidence", "Tradeoffs", "Future reuse", "Concepts"):
        assert heading in md


@pytest.mark.parametrize(
    "mutation, needle",
    [
        ({"record_id": "Bad Id"}, "kebab"),
        ({"title": ""}, "title"),
        ({"date": "   "}, "date"),
        ({"what_changed": ""}, "what_changed"),
        ({"evidence": []}, "evidence"),
        ({"evidence": ["ok", ""]}, "evidence"),
        ({"concepts": "not a list"}, "concepts"),
    ],
)
def test_bad_records_fail_loud(mutation, needle):
    raw = {**_GOOD, **mutation}
    with pytest.raises(LearningRecordError) as err:
        from_dict(raw)
    assert needle in str(err.value)


def test_non_mapping_fails_loud():
    with pytest.raises(LearningRecordError) as err:
        from_dict(["not", "a", "mapping"])
    assert "expected a mapping" in str(err.value)


def test_unreadable_file_fails_loud(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text("{ not json")
    with pytest.raises(LearningRecordError):
        load_record(bad)


def test_empty_directory_reports_nothing_filed(tmp_path):
    assert "No learning records filed yet" in learnings(root=tmp_path)


def test_load_all_reads_a_tmp_dir(tmp_path):
    (tmp_path / "data" / "learning_records").mkdir(parents=True)
    (tmp_path / "data" / "learning_records" / "x.json").write_text(json.dumps(_GOOD))
    ids = [r.record_id for r in load_all(root=tmp_path)]
    assert ids == ["sample-lesson"]


def test_the_shipped_record_is_valid():
    # The repo's own first record must always pass the gate.
    assert "catalog-v3-identity-vs-filing-aid" in [r.record_id for r in load_all()]


def test_learnings_list_and_show_via_the_tick():
    session = Session(player_id="matrym", location="courtyard")
    assert "LEARNING RECORDS" in handle_command(session, "learnings")
    assert "What changed" in handle_command(
        session, "learnings show catalog-v3-identity-vs-filing-aid"
    )


def test_learnings_show_unknown_id():
    assert "No learning record" in learnings("show nope")
