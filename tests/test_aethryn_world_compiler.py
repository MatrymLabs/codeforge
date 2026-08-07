"""Acceptance and refusal tests for the offline Aethryn world compiler."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import yaml

from kernel.world import aethryn_cli
from kernel.world.aethryn_compiler import (
    compile_packet,
    provenance_for,
    publish_package,
    restore_package,
)
from kernel.world.aethryn_state import WorldStateStore, project_cistern_text
from kernel.world.aethryn_validation import load_packet, validate_map_concordance, validate_packet

ROOT = Path(__file__).resolve().parents[1]
PACKET = (
    ROOT
    / "content"
    / "seeds"
    / "aethryn"
    / "design"
    / "packets"
    / "veridia_greenhold_living_slice.yaml"
)
DUSKWOOD_PACKET = (
    ROOT
    / "content"
    / "seeds"
    / "aethryn"
    / "design"
    / "packets"
    / "duskwood_black_hollow_threshold.yaml"
)
BRIGHTWATER_PACKET = (
    ROOT
    / "content"
    / "seeds"
    / "aethryn"
    / "design"
    / "packets"
    / "caeloria_brightwater_river_ledger.yaml"
)


def test_veridia_packet_is_clean_and_has_the_expected_system_counts() -> None:
    packet = load_packet(PACKET)
    report = validate_packet(packet, root=ROOT)
    assert report.verdict == "CLEAN"
    assert dict(packet.required_content_counts)["rooms"] == 9
    assert dict(packet.required_content_counts)["economy_flows"] == 3


def test_duskwood_packet_is_clean_and_preserves_the_existing_hollow() -> None:
    packet = load_packet(DUSKWOOD_PACKET)
    report = validate_packet(packet, root=ROOT)
    assert report.verdict == "CLEAN"
    anchor = next(row for row in packet.records["rooms"] if row["id"] == "the_black_hollow")
    assert anchor["replace"] is True
    assert anchor["exits"]["down"] == "the_black_hollow_delve_1"
    assert dict(packet.required_content_counts)["rooms"] == 7


def test_brightwater_packet_is_clean_and_preserves_authored_river_routes() -> None:
    packet = load_packet(BRIGHTWATER_PACKET)
    report = validate_packet(packet, root=ROOT)
    assert report.verdict == "CLEAN"
    millrace = next(row for row in packet.records["rooms"] if row["id"] == "brightwater_millrace")
    assert millrace["replace"] is True
    assert millrace["exits"] == {
        "south": "brightwater_market",
        "down": "brightwater_sluice",
        "west": "brightwater_lowerweir",
    }
    assert dict(packet.required_content_counts)["economy_flows"] == 3


def test_mutation_contract_validates_consumption_and_state_gates() -> None:
    packet = load_packet(PACKET)
    state_changes = [dict(row) for row in packet.records["state_changes"]]
    state_changes[0]["actions"] = [dict(state_changes[0]["actions"][0], consume_item="yes")]
    pressures = [dict(row) for row in packet.records["quest_pressures"]]
    pressures[0]["state_gate"] = {
        "key": "greenhold.missing_state",
        "active_values": ["low"],
    }
    records = dict(packet.records)
    records["state_changes"] = tuple(state_changes)
    records["quest_pressures"] = tuple(pressures)
    report = validate_packet(replace(packet, records=records), root=ROOT)
    codes = {issue.code for issue in report.issues}
    assert {"invalid_consume_item", "unknown_state_gate_key"} <= codes


def test_state_action_outside_reversible_values_is_actionable() -> None:
    packet = load_packet(BRIGHTWATER_PACKET)
    state_changes = [dict(row) for row in packet.records["state_changes"]]
    state_changes[0]["actions"] = [dict(state_changes[0]["actions"][0], to="unmodeled")]
    records = dict(packet.records)
    records["state_changes"] = tuple(state_changes)
    report = validate_packet(replace(packet, records=records), root=ROOT)
    issue = next(issue for issue in report.issues if issue.code == "action_value_outside_schema")
    assert issue.authority == "state mutation contract"
    assert "reversible_values" in issue.action


def test_locked_region_band_drift_is_actionable() -> None:
    packet = load_packet(PACKET)
    report = validate_packet(replace(packet, threat_range=(1, 31)), root=ROOT)
    issue = next(issue for issue in report.issues if issue.code == "threat_drift")
    assert issue.authority == "canon.yaml"
    assert "keep the packet threat range" in issue.action


def test_unresolved_question_leakage_is_refused() -> None:
    packet = load_packet(PACKET)
    rooms = [dict(row) for row in packet.records["rooms"]]
    rooms[1]["description"] = (
        "This civic edge records whether Netharion survived as objective truth, which is forbidden "
        "because the question remains open in current canon."
    )
    records = dict(packet.records)
    records["rooms"] = tuple(rooms)
    report = validate_packet(replace(packet, records=records), root=ROOT)
    issue = next(issue for issue in report.issues if issue.code == "open_question_leakage")
    assert issue.authority == "canon.yaml"
    assert "rumor" in issue.action


def test_orphan_room_and_dangling_exit_are_refused() -> None:
    packet = load_packet(PACKET)
    rooms = [dict(row) for row in packet.records["rooms"]]
    rooms[1].pop("parent_settlement")
    rooms[1].pop("parent_wilderness", None)
    rooms[1]["exits"] = {"east": "nowhere_room"}
    records = dict(packet.records)
    records["rooms"] = tuple(rooms)
    report = validate_packet(replace(packet, records=records), root=ROOT)
    codes = {issue.code for issue in report.issues}
    assert {"orphan_room", "dangling_exit"} <= codes


def test_compilation_is_deterministic_and_emits_provenance(tmp_path: Path) -> None:
    first, first_manifest = compile_packet(PACKET, output_dir=tmp_path / "first", root=ROOT)
    second, second_manifest = compile_packet(PACKET, output_dir=tmp_path / "second", root=ROOT)
    assert first_manifest.output_digest == second_manifest.output_digest
    first_batch = (first / "room_batches" / "veridia_greenhold_living_slice.yaml").read_bytes()
    second_batch = (second / "room_batches" / "veridia_greenhold_living_slice.yaml").read_bytes()
    assert first_batch == second_batch
    assert (first / "world_ir.yaml").is_file()
    provenance = provenance_for(first, "living_sluice_wheel")
    assert "veridia_greenhold_living_slice" in provenance
    assert "generation_seed" in provenance


def test_publication_keeps_previous_artifact_and_restores_it(tmp_path: Path) -> None:
    staging, _ = compile_packet(PACKET, output_dir=tmp_path / "staging", root=ROOT)
    destination = tmp_path / "published" / "room_batches"
    destination.mkdir(parents=True)
    target = destination / "veridia_greenhold_living_slice.yaml"
    target.write_text("previous package\n", encoding="utf-8")
    published, rollback = publish_package(staging, destination=destination)
    assert published == target
    assert rollback is not None and rollback.read_text(encoding="utf-8") == "previous package\n"
    restored = restore_package(rollback, destination=destination)
    assert restored.read_text(encoding="utf-8") == "previous package\n"


def test_cli_reaches_packet_validation_and_map_concordance() -> None:
    code, text = aethryn_cli.run(["validate-packet", str(PACKET)])
    assert code == 0 and "verdict: CLEAN" in text
    code, text = aethryn_cli.run(["map-concordance-check"])
    assert code == 0 and "CLEAN" in text


def test_map_concordance_covers_all_locked_regions() -> None:
    issues = validate_map_concordance(
        ROOT / "content" / "seeds" / "aethryn" / "design" / "map_concordance.yaml"
    )
    assert issues == []


def test_compiled_batch_is_codeforge_room_batch_data(tmp_path: Path) -> None:
    staging, _ = compile_packet(PACKET, output_dir=tmp_path / "staging", root=ROOT)
    raw = yaml.safe_load(
        (staging / "room_batches" / "veridia_greenhold_living_slice.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert raw["batch"]["status"] == "ready"
    assert raw["batch"]["size"] == 9
    assert raw["rooms"]["veridia_living_hollow"]["exits"] == {"west": "veridia_living_wild_loop"}


def test_duskwood_compilation_emits_sequence_and_generic_state_projection(tmp_path: Path) -> None:
    staging, manifest = compile_packet(DUSKWOOD_PACKET, output_dir=tmp_path / "staging", root=ROOT)
    raw = yaml.safe_load(
        (staging / "room_batches" / "duskwood_black_hollow_threshold.yaml").read_text(
            encoding="utf-8"
        )
    )
    schema = yaml.safe_load((staging / "world_state.yaml").read_text(encoding="utf-8"))
    assert manifest.output_digest
    assert raw["batch"]["sequence"] == 15
    assert schema["duskwood.hollow_lantern"]["room_id"] == "duskwood_hollow_warden_camp"
    assert "{value}" in schema["duskwood.hollow_lantern"]["visible_projection"]


def test_brightwater_compilation_emits_provenance_and_state(tmp_path: Path) -> None:
    staging, manifest = compile_packet(
        BRIGHTWATER_PACKET, output_dir=tmp_path / "brightwater", root=ROOT
    )
    raw = yaml.safe_load(
        (staging / "room_batches" / "caeloria_brightwater_river_ledger.yaml").read_text(
            encoding="utf-8"
        )
    )
    schema = yaml.safe_load((staging / "world_state.yaml").read_text(encoding="utf-8"))
    assert manifest.validation_verdict == "CLEAN"
    assert raw["batch"]["sequence"] == 16
    assert raw["rooms"]["brightwater_sluice"]["name"] == "The Old Sluice"
    assert schema["brightwater.sluice_status"]["room_id"] == "brightwater_sluice"


def test_veridia_state_changes_are_visible_and_survive_restart(tmp_path: Path) -> None:
    staging, _ = compile_packet(PACKET, output_dir=tmp_path / "staging", root=ROOT)
    schema = yaml.safe_load((staging / "world_state.yaml").read_text(encoding="utf-8"))
    state_path = tmp_path / "world-state.json"
    first = WorldStateStore(state_path, schema)
    assert first.get("greenhold.cistern_status") == "low"
    snapshot = first.snapshot()
    first.set("greenhold.cistern_status", "flowing")
    assert "flowing again" in project_cistern_text("The civic court is quiet.", first)
    restarted = WorldStateStore(state_path, schema)
    assert restarted.get("greenhold.cistern_status") == "flowing"
    restarted.restore(snapshot)
    assert restarted.get("greenhold.cistern_status") == "low"


def test_materialize_publishes_by_default_and_supports_stage_only() -> None:
    assert aethryn_cli._parse_materialize([])[2] is True
    assert aethryn_cli._parse_materialize(["--stage-only"])[2] is False


def test_live_room_renderer_projects_persisted_veridia_state(tmp_path: Path, monkeypatch) -> None:
    from kernel.world import world

    schema = {
        "greenhold.cistern_status": {
            "initial_value": "low",
            "reversible_values": ["low", "flowing"],
            "room_id": "veridia_living_cistern_court",
        }
    }
    store = WorldStateStore(tmp_path / "world-state.json", schema)
    monkeypatch.setattr(world, "_AETHRYN_STATE", store)
    monkeypatch.setitem(
        world.WORLD,
        "veridia_living_cistern_court",
        {"name": "Cistern Court", "desc": "A civic court.", "exits": {}},
    )
    dry = world.render_room("veridia_living_cistern_court")
    assert "public channel is dry" in dry
    store.set("greenhold.cistern_status", "flowing")
    flowing = world.render_room("veridia_living_cistern_court")
    assert "public channel runs clear" in flowing


def test_live_room_renderer_projects_persisted_duskwood_state(tmp_path: Path, monkeypatch) -> None:
    from kernel.world import world

    schema = {
        "duskwood.hollow_lantern": {
            "initial_value": "dim",
            "reversible_values": ["dim", "lit"],
            "room_id": "duskwood_hollow_warden_camp",
            "visible_projection": "The warden lantern burns {value} along the return markers.",
        }
    }
    store = WorldStateStore(tmp_path / "world-state.json", schema)
    monkeypatch.setattr(world, "_AETHRYN_STATE", store)
    monkeypatch.setitem(
        world.WORLD,
        "duskwood_hollow_warden_camp",
        {"name": "Warden Lantern Camp", "desc": "A wet camp.", "exits": {}},
    )
    dim = world.render_room("duskwood_hollow_warden_camp")
    assert "burns dim" in dim
    store.set("duskwood.hollow_lantern", "lit")
    lit = world.render_room("duskwood_hollow_warden_camp")
    assert "burns lit" in lit
