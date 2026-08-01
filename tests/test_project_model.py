"""Test twin for parts/seedlab/project_model.py -- the engineering Seed's first act.

Acceptance: a well-formed spec source yields a model with every named facet and its provenance,
and renders inspectably. Refusal (fail loud, never model a lie): a missing identity, a non-list
facet, a bad relationship triple, and a source_id-less provenance all raise SeedLabError.
"""

from __future__ import annotations

import pytest

from parts.seedlab.project_model import (
    ProjectSource,
    Provenance,
    SeedLabError,
    SpecSource,
    extract_model,
    render_model,
)

_SPEC = {
    "identity": "TaskLedger, a tiny CLI task tracker",
    "entities": ["Task", "Ledger"],
    "relationships": [["Ledger", "holds", "Task"]],
    "states": ["open", "done"],
    "actions": ["add", "complete", "list"],
    "inputs": ["a task title"],
    "outputs": ["the task list"],
}


def _source(spec: dict | None = None, prov: Provenance | None = None) -> SpecSource:
    return SpecSource(
        spec if spec is not None else dict(_SPEC),
        prov or Provenance("taskledger", owner="josh", license="MIT", visibility="private"),
    )


# --- acceptance --------------------------------------------------------------------------------
def test_a_spec_source_is_a_project_source():
    assert isinstance(_source(), ProjectSource)  # the connector protocol is satisfied


def test_extract_builds_the_full_model():
    m = extract_model(_source())
    assert m.identity == "TaskLedger, a tiny CLI task tracker"
    assert m.entities == ["Task", "Ledger"]
    assert m.states == ["open", "done"] and m.actions == ["add", "complete", "list"]
    assert m.inputs == ["a task title"] and m.outputs == ["the task list"]
    rel = m.relationships[0]
    assert (rel.subject, rel.verb, rel.object) == ("Ledger", "holds", "Task")


def test_provenance_rides_the_model():
    m = extract_model(_source())
    assert m.provenance.source_id == "taskledger" and m.provenance.license == "MIT"


def test_render_shows_the_facets_and_provenance():
    out = render_model(extract_model(_source()))
    assert "Project Model: TaskLedger" in out
    assert "owner: josh, license: MIT, private" in out
    assert "Ledger holds Task" in out
    assert "add, complete, list" in out


def test_missing_facets_default_to_empty_not_error():
    m = extract_model(_source({"identity": "bare"}))  # only identity: the rest are optional
    assert m.identity == "bare" and m.entities == [] and m.actions == []


# --- refusal: a malformed source fails loud ----------------------------------------------------
def test_a_spec_without_an_identity_is_refused():
    with pytest.raises(SeedLabError, match="identity"):
        extract_model(_source({"entities": ["X"]}))


def test_a_non_list_facet_is_refused():
    with pytest.raises(SeedLabError, match="entities"):
        extract_model(_source({"identity": "x", "entities": "not-a-list"}))


def test_a_bad_relationship_triple_is_refused():
    with pytest.raises(SeedLabError, match="relationship"):
        extract_model(_source({"identity": "x", "relationships": [["only", "two"]]}))


def test_an_empty_entity_string_is_refused():
    with pytest.raises(SeedLabError, match="entities"):
        extract_model(_source({"identity": "x", "entities": ["ok", "  "]}))


def test_provenance_needs_a_source_id():
    with pytest.raises(SeedLabError, match="source_id"):
        Provenance("")


def test_provenance_rejects_a_bad_visibility():
    with pytest.raises(SeedLabError, match="visibility"):
        Provenance("s", visibility="secret")


def test_a_non_mapping_spec_is_refused():
    class _Bad:
        def provenance(self) -> Provenance:
            return Provenance("s")

        def spec(self) -> dict:
            return ["not", "a", "dict"]  # type: ignore[return-value]

    with pytest.raises(SeedLabError, match="mapping"):
        extract_model(_Bad())
