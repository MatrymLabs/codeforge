"""Test twin for scripts/export_research.py -- bridging the R&D candidate register into a
Research.Findings manifest the Master Client's research panel reads.

Acceptance: a candidate maps onto the finding shape (id/title/question/verdict/source/evidence/
summary), folded scalars collapse to one line, findings sort by id, and the CLI writes a JSON list.
Refusal/honesty: a candidate with no id is dropped; a field the candidate lacks is absent from the
finding (never invented); a malformed register fails loud.
"""

from __future__ import annotations

import json
from typing import cast

import pytest

import scripts.export_research as export

_REGISTER = {
    "candidates": [
        {
            "candidate_id": "CAND-01-fts5",
            "technology": "SQLite FTS5 full-text search",
            "problem_it_may_solve": "Search rooms, items,\nlore, NPCs, and commands.",
            "status": "LAB_PROVEN",
            "source": "CAPABILITY_CROSSWALK GAP-06",
            "required_experiment": "EXP-05-search",
            "expected_benefit": "sub-linear ranked search; no new dependency",
        },
        {
            "candidate_id": "CAND-09-otel",
            "technology": "OpenTelemetry",
            "status": "MONITOR",
        },
        {"technology": "no id here", "status": "REJECTED"},  # no candidate_id -> dropped
    ]
}


def test_a_candidate_maps_onto_the_finding_shape() -> None:
    findings = export.export_findings(_REGISTER)
    fts = next(f for f in findings if f["id"] == "CAND-01-fts5")
    assert fts["title"] == "SQLite FTS5 full-text search"
    assert fts["verdict"] == "LAB_PROVEN" and fts["source"] == "CAPABILITY_CROSSWALK GAP-06"
    assert fts["evidence"] == "EXP-05-search"
    assert (
        fts["question"] == "Search rooms, items, lore, NPCs, and commands."
    )  # folded scalar collapsed to one line


def test_an_absent_field_is_left_out_never_invented() -> None:
    findings = export.export_findings(_REGISTER)
    otel = next(f for f in findings if f["id"] == "CAND-09-otel")
    assert otel["verdict"] == "MONITOR" and otel["title"] == "OpenTelemetry"
    assert (
        "source" not in otel and "evidence" not in otel
    )  # the candidate had none: absent, not blank


def test_a_candidate_without_an_id_is_dropped() -> None:
    ids = [f["id"] for f in export.export_findings(_REGISTER)]
    assert ids == [
        "CAND-01-fts5",
        "CAND-09-otel",
    ]  # the id-less candidate is gone, and sorted by id


def test_a_malformed_register_fails_loud() -> None:
    with pytest.raises(ValueError, match="candidates"):
        export.export_findings({"not": "a register"})
    with pytest.raises(ValueError, match="candidates"):
        export.export_findings(["not", "a", "mapping"])


def test_the_cli_writes_a_json_list_of_findings(tmp_path) -> None:
    import yaml  # noqa: PLC0415

    rd_home = tmp_path / "rd"
    register_path = rd_home / "04-verdicts" / "CANDIDATE_REGISTER.yaml"
    register_path.parent.mkdir(parents=True)
    register_path.write_text(yaml.safe_dump(_REGISTER), encoding="utf-8")
    out = tmp_path / "research.json"
    assert export.main(["--rd-home", str(rd_home), "--out", str(out)]) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert [f["id"] for f in written] == ["CAND-01-fts5", "CAND-09-otel"]  # a valid finding list


def test_the_projector_and_client_parser_accept_the_export() -> None:
    # the whole point: the export is exactly what research_findings emits and the client parses
    from kernel.seedlab.workspace_gmcp import research_findings  # noqa: PLC0415

    payload = research_findings(export.export_findings(_REGISTER), seed="codeforge")
    assert payload["finding_count"] == 2
    groups = cast("list[dict[str, object]]", payload["verdicts"])
    assert {g["verdict"] for g in groups} == {"LAB_PROVEN", "MONITOR"}  # grouped by real status
