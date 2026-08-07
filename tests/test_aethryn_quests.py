# ruff: noqa: E501

"""Focused proof for the structured Aethryn quest extension."""

import json
from pathlib import Path

from kernel.world.aethryn_compiler import compile_packet
from kernel.world.aethryn_quests import (
    ConsequenceStore,
    ContributionLedger,
    deterministic_contract_preview,
    party_credit,
    simulate_public_event,
    simulate_quest,
    validate_quest_records,
    validate_quest_spec,
)
from kernel.world.aethryn_validation import load_packet, validate_packet

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "content/seeds/aethryn/design/packets/veridia_greenhold_living_slice.yaml"


def _packet():
    return load_packet(PACKET)


def test_veridia_packet_has_structured_quest_web_and_validates():
    packet = _packet()
    report = validate_packet(packet, root=ROOT)
    assert report.verdict == "CLEAN"
    assert len(packet.records["quests"]) == 10
    assert len(packet.records["quest_arcs"]) == 1
    assert len(packet.records["public_events"]) == 1


def test_legacy_quest_shape_is_adapted_without_changing_id_or_progress_states():
    legacy = {
        "id": "legacy_bridge",
        "name": "Legacy Bridge",
        "start": "offered",
        "reward_xp": 12,
        "steps": [{"state": "offered", "event": "enter", "to": "done", "on_enter": "greenhold"}],
        "terminal": ["done"],
        "labels": {"offered": "The bridge waits.", "done": "The bridge stands."},
    }
    assert validate_quest_spec(legacy).verdict == "CLEAN"
    row = validate_quest_records({"quests": [legacy]})
    assert row.verdict == "CLEAN"


def test_graph_validator_rejects_unreachable_states_and_nonrepeatable_cycles():
    bad = {
        "id": "broken_graph",
        "display_name": "Broken Graph",
        "canon_status": "GENERATED_LOCAL",
        "quest_type": "repair",
        "pressure_id": "pressure",
        "start_state": "a",
        "terminal_states": ["done"],
        "states": ["a", "loop", "orphan", "done"],
        "transitions": [
            {"from": "a", "event": "enter", "to": "loop"},
            {"from": "loop", "event": "talk", "to": "loop"},
            {"from": "orphan", "event": "enter", "to": "done"},
        ],
        "prose": {
            "title": "Broken",
            "summary": "A pressure.",
            "journal": "Do work.",
            "success": "Done.",
        },
    }
    codes = {finding.code for finding in validate_quest_spec(bad).findings}
    assert {"unreachable_state", "dead_state", "invalid_cycle"} <= codes


def test_identical_contract_inputs_are_identical_and_have_generated_provenance():
    template = {
        "id": "field_watch",
        "target_pool": ["boar", "vermin"],
        "objective_pool": ["inspect", "drive_off"],
        "pressure_types": ["ecology"],
        "narrative_variants": ["A field needs a watch."],
        "cooldown": 4,
    }
    first = deterministic_contract_preview(template, 77)
    second = deterministic_contract_preview(template, 77)
    assert first == second
    assert first["canon_status"] == "GENERATED_LOCAL"
    assert first["provenance"]["seed"] == 77


def test_contract_history_avoids_recent_target_when_an_alternative_exists():
    template = {
        "id": "watch",
        "target_pool": ["boar", "vermin"],
        "objective_pool": ["inspect"],
        "pressure_types": ["ecology"],
    }
    assert deterministic_contract_preview(template, 2, history=["boar"])["target_id"] == "vermin"


def test_crowd_and_public_contributions_are_aggregate_not_persistent_npcs():
    ledger = ContributionLedger()
    ledger.add("alia", 2, kind="repair")
    ledger.add("bram", 0)
    ledger.add("cira", 1, kind="evidence")
    assert ledger.totals() == {"alia": 2, "cira": 1}
    assert party_credit(("alia", "bram", "cira"), required=1, contributions=ledger.totals()) == (
        "alia",
        "cira",
    )
    state = simulate_public_event({"id": "water_day", "success_threshold": 3}, ledger.totals())
    assert state.state == "success"
    assert len(ledger.snapshot()) == 2


def test_consequence_scope_round_trips_and_can_be_reset():
    store = ConsequenceStore()
    store.apply(
        {
            "effect_type": "change_world_state",
            "target": "cistern",
            "scope": "settlement",
            "value": "flowing",
            "persistence": "world",
        }
    )
    restored = ConsequenceStore()
    restored.restore(store.snapshot())
    assert restored.get("cistern", scope="settlement") == store.get("cistern", scope="settlement")
    restored.reset("settlement")
    assert restored.get("cistern", scope="settlement") is None


def test_consequence_store_rejects_explicit_immutable_canon_target():
    store = ConsequenceStore()
    try:
        store.apply({"target": "veridia", "scope": "regional", "immutable": True})
    except ValueError as exc:
        assert "immutable" in str(exc)
    else:
        raise AssertionError("immutable canon target was accepted")


def test_quest_preview_is_deterministic_and_reaches_terminal_state():
    row = next(row for row in _packet().records["quests"] if row["id"] == "greenhold_water_repair")
    preview = simulate_quest(row)
    assert preview["states"] == ["offered", "diagnose", "ready", "resolved"]
    assert preview["complete"] is True


def test_compiled_package_contains_quest_records_and_provenance(tmp_path):
    staging, manifest = compile_packet(PACKET, output_dir=tmp_path / "package", root=ROOT)
    assert manifest.records["quests"] == 10
    records = json.loads(
        json.dumps(__import__("yaml").safe_load((staging / "records.yaml").read_text()))
    )
    assert records["quests"][0]["provenance"]["packet_id"] == "veridia_greenhold_living_slice"
    assert records["quest_world_effects"][0]["generator_version"] == "1.0.0"
    manifest = __import__("yaml").safe_load((staging / "quest_manifest.yaml").read_text())
    assert len(manifest["quest_ids"]) == 10


def test_existing_runtime_quest_ids_remain_present():
    from kernel.world.quest import all_ids

    ids = set(all_ids())
    assert ids
    assert "the_endless_journey" in ids or "coilward_contract" in ids


def test_builder_commands_reach_the_quest_extension():
    from kernel.world.aethryn_cli import run

    code, text = run(["quest-check", "veridia_greenhold_living_slice.yaml"])
    assert code == 0 and "CLEAN" in text
    code, text = run(
        ["quest-graph", "greenhold_water_repair", "veridia_greenhold_living_slice.yaml"]
    )
    assert code == 0 and "transitions" in text
    code, text = run(
        [
            "simulate-public-event",
            "greenhold_water_day_event",
            "veridia_greenhold_living_slice.yaml",
        ]
    )
    assert code == 0 and "success" in text
