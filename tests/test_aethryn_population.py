"""Acceptance tests for aggregate Aethryn ecology and population layers."""

from __future__ import annotations

from pathlib import Path

import yaml

from kernel.world.aethryn_compiler import compile_packet
from kernel.world.aethryn_models import PopulationManifest
from kernel.world.aethryn_population import (
    PopulationStateStore,
    simulate_population,
    validate_population_records,
)
from kernel.world.aethryn_runtime import RuntimeCatalog, project_runtime_context
from kernel.world.aethryn_validation import load_packet, validate_packet
from tools.materialize_aethryn import _population_records

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "content/seeds/aethryn/design/packets/veridia_greenhold_living_slice.yaml"


def _records() -> dict[str, list[dict]]:
    packet = load_packet(PACKET)
    return {kind: [dict(row) for row in rows] for kind, rows in packet.records.items()}


def test_rooms_do_not_require_creatures_and_veridia_has_zone_scale_density() -> None:
    packet = load_packet(PACKET)
    report = validate_packet(packet, root=ROOT)
    assert report.verdict == "CLEAN"
    rooms = {str(row["id"]): row for row in packet.records["rooms"]}
    assert "location" not in rooms["veridia_living_cistern_court"]
    manifest = simulate_population(_records(), "veridia_zone", ticks=4, seed=41017)
    assert manifest.states
    assert all(state.current_count >= 0 for state in manifest.states)
    assert any(state.current_count > 0 for state in manifest.states)


def test_crowd_renders_as_one_collective_record_without_persistent_members(tmp_path: Path) -> None:
    staging, _ = compile_packet(PACKET, output_dir=tmp_path / "package", root=ROOT)
    records = yaml.safe_load((staging / "records.yaml").read_text(encoding="utf-8"))
    batch = yaml.safe_load(
        (staging / "room_batches" / "veridia_greenhold_living_slice.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert len(records["crowd_specs"]) == 1
    assert batch["rooms"]["greenhold"]["crowd_refs"] == ["greenhold_market_crowd"]
    assert len(records["npcs"]) == 3


def test_roaming_route_respects_forbidden_rooms_and_is_deterministic() -> None:
    records = _records()
    first = simulate_population(records, "veridia_zone", ticks=2, seed=9)
    second = simulate_population(records, "veridia_zone", ticks=2, seed=9)
    assert first == second
    destination = first.roaming_groups["greenhold_road_patrol_route"][0]
    assert destination not in {"veridia_living_hollow", "veridia_living_cistern_court"}


def test_group_composition_and_population_caps_are_checked() -> None:
    records = _records()
    findings = validate_population_records(records, {str(row["id"]) for row in records["rooms"]})
    assert not findings
    bad = {kind: list(rows) for kind, rows in records.items()}
    bad["population_profiles"][0] = dict(
        bad["population_profiles"][0], population_max=99, carrying_capacity=4
    )
    bad["encounter_groups"][0] = dict(
        bad["encounter_groups"][0], composition={"not_declared": [1, 2]}
    )
    codes = {
        finding.code
        for finding in validate_population_records(
            bad, {str(row["id"]) for row in records["rooms"]}
        )
    }
    assert {"over_capacity", "unknown_group_member"} <= codes


def test_habitat_conflicts_and_legacy_metaphysics_are_rejected() -> None:
    records = _records()
    records["population_profiles"].append(
        {
            "id": "bad_habitat",
            "display_name": "bad habitat",
            "creature_id": "living_field_boar",
            "region": "not_veridia",
            "candidate_rooms": ["veridia_living_wild_loop"],
            "population_min": 1,
            "population_max": 1,
            "allowed_room_types": ["Town Hub"],
            "forbidden_room_types": ["Town Hub"],
        }
    )
    records["creatures"][0] = dict(
        records["creatures"][0], description="This invokes the Unforging."
    )
    codes = {
        finding.code
        for finding in validate_population_records(
            records, {str(row["id"]) for row in records["rooms"]}
        )
    }
    assert {
        "habitat_room_type_conflict",
        "habitat_region_conflict",
        "legacy_bestiary_metaphysics",
    } <= codes


def test_descriptions_survive_materialization_and_reload(tmp_path: Path) -> None:
    staging, _ = compile_packet(PACKET, output_dir=tmp_path / "package", root=ROOT)
    records = yaml.safe_load((staging / "records.yaml").read_text(encoding="utf-8"))
    boar = next(row for row in records["creatures"] if row["id"] == "living_field_boar")
    assert "room_presence_description" in boar
    assert "tusks" in boar["examine_description"]
    assert (
        yaml.safe_load((staging / "records.yaml").read_text(encoding="utf-8"))["creatures"][-1][
            "id"
        ]
        == "living_field_rabbit"
    )


def test_ambient_evidence_projects_without_direct_presence() -> None:
    catalog = RuntimeCatalog(
        records={
            "ambient_presence": (
                {
                    "id": "evidence",
                    "rooms": ["quiet"],
                    "text": "A distant flock calls beyond the ridge.",
                    "evidence_type": "sound",
                    "probability": 1.0,
                    "generation_seed": 7,
                },
            )
        },
        by_id={"evidence": {"id": "evidence"}},
    )
    rendered = project_runtime_context("quiet", 0, catalog)
    assert "distant flock" in rendered
    assert "population" not in rendered.lower()


def test_population_state_persists_depletion_and_recovers_by_declared_rule() -> None:
    records = _records()
    store = PopulationStateStore(records, seed=41017)
    initial = store.tick("veridia_zone", ticks=0)
    depleted = store.deplete("veridia_zone", "greenhold_field_rabbits", amount=3)
    assert (
        next(
            state for state in depleted.states if state.population_id == "greenhold_field_rabbits"
        ).current_count
        < next(
            state for state in initial.states if state.population_id == "greenhold_field_rabbits"
        ).current_count
    )
    recovered = store.tick("veridia_zone", ticks=1)
    assert (
        next(
            state for state in recovered.states if state.population_id == "greenhold_field_rabbits"
        ).current_count
        >= next(
            state for state in depleted.states if state.population_id == "greenhold_field_rabbits"
        ).current_count
    )
    snapshot = store.snapshot()
    store.reset("veridia_zone", scope="zone")
    assert not store.manifests
    store.restore(snapshot)
    assert store.manifests


def test_population_simulation_has_no_model_boundary() -> None:
    # The pure function only consumes mappings and a seed; this is the runtime contract that keeps
    # startup independent of Codex, an LLM, or an external content service.
    result = simulate_population(_records(), "veridia_zone", ticks=3, seed=41017)
    assert isinstance(result, PopulationManifest)
    assert result.digest


def test_materialization_collector_keeps_population_and_creature_records() -> None:
    rows = _population_records(ROOT / "content/seeds/aethryn")
    assert len(rows["creatures"]) >= 3
    assert len(rows["population_profiles"]) == 6
    assert len(rows["crowd_specs"]) == 1
