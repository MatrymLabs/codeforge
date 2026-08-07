"""Acceptance tests for deterministic Aethryn room prose and presentation payloads."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import yaml

from kernel.world.aethryn_compiler import compile_packet
from kernel.world.aethryn_room_prose import build_packet_presentations, validate_presentations
from kernel.world.aethryn_validation import load_packet, validate_packet
from kernel.world.room_batches import apply_room_batches
from kernel.world.seed import load_rooms

ROOT = Path(__file__).resolve().parents[1]
PACKET_ROOT = ROOT / "content" / "seeds" / "aethryn" / "design" / "packets"
PACKETS = tuple(sorted(PACKET_ROOT.glob("*.yaml")))


def test_every_compiled_room_has_complete_prose_and_provenance(tmp_path: Path) -> None:
    required = {
        "name",
        "presentation_version",
        "area_name",
        "room_type",
        "primary_purpose",
        "short_description",
        "long_description",
        "points_of_interest",
        "conditions",
        "exits",
        "parent_region",
        "parent_zone",
        "canon_status",
        "source_design_ids",
        "generation_seed",
        "generator_name",
        "generator_version",
        "provenance",
        "content_digest",
    }
    for packet_path in PACKETS:
        staging, _ = compile_packet(
            packet_path,
            output_dir=tmp_path / packet_path.stem,
            root=ROOT,
        )
        raw = yaml.safe_load(
            (staging / "room_batches" / packet_path.name).read_text(encoding="utf-8")
        )
        assert raw["batch"]["presentation_spec"] == "aethryn-room-v1"
        for room_id, room in raw["rooms"].items():
            assert required <= set(room), room_id
            assert room["prose_status"] == "GENERATED_LOCAL"
            assert room["provenance"]["packet_id"] == raw["batch"]["id"]
            assert room["points_of_interest"] is not None


def test_room_prose_is_deterministic_and_changes_with_relevant_design_input() -> None:
    packet = load_packet(PACKET_ROOT / "veridia_greenhold_living_slice.yaml")
    records = {kind: tuple(rows) for kind, rows in packet.records.items()}
    first = build_packet_presentations(packet, records)
    second = build_packet_presentations(packet, records)
    assert first == second

    changed = replace(
        packet,
        geography_profile={**packet.geography_profile, "terrain": "raised river terraces"},
    )
    changed_presentations = build_packet_presentations(changed, records)
    assert (
        changed_presentations["veridia_living_road_threshold"]["long_description"]
        != first["veridia_living_road_threshold"]["long_description"]
    )


def test_interactive_records_are_structured_points_of_interest() -> None:
    packet = load_packet(PACKET_ROOT / "veridia_greenhold_living_slice.yaml")
    records = {kind: tuple(rows) for kind, rows in packet.records.items()}
    presentations = build_packet_presentations(packet, records)
    assert not validate_presentations(packet, presentations, records)
    cistern_points = presentations["veridia_living_cistern_court"]["points_of_interest"]
    assert {point["id"] for point in cistern_points} == {"living_drainage_ledger"}
    assert "examine" in cistern_points[0]["actions"]


def test_canon_and_temporary_state_leakage_in_prose_is_rejected() -> None:
    packet = load_packet(PACKET_ROOT / "veridia_greenhold_living_slice.yaml")
    rooms = [dict(row) for row in packet.records["rooms"]]
    rooms[0]["description"] = "The Forge is current here, and the cistern is currently flowing."
    changed = replace(packet, records={**packet.records, "rooms": tuple(rooms)})
    report = validate_packet(changed, root=ROOT)
    codes = {issue.code for issue in report.issues}
    assert "placeholder_or_legacy_prose" in codes
    assert "temporary_state_in_static_prose" in codes


def test_prose_that_denies_a_declared_exit_is_rejected() -> None:
    packet = load_packet(PACKET_ROOT / "veridia_greenhold_living_slice.yaml")
    records = {kind: tuple(rows) for kind, rows in packet.records.items()}
    presentations = build_packet_presentations(packet, records)
    changed = dict(presentations["veridia_living_road_threshold"])
    changed["long_description"] = (
        "The maintained road has a milestone, wet ditches, cart ruts, and a public notice board. "
        "There is no way east from this threshold, despite the route map and nearby hedges."
    )
    presentations["veridia_living_road_threshold"] = changed
    findings = validate_presentations(packet, presentations, records)
    assert any(finding.code == "prose_exit_contradiction" for finding in findings)


def test_compiled_room_batch_survives_materialization_and_reload(tmp_path: Path) -> None:
    packet_path = PACKET_ROOT / "veridia_greenhold_living_slice.yaml"
    staging, _ = compile_packet(packet_path, output_dir=tmp_path / "staging", root=ROOT)
    world = load_rooms(ROOT / "content" / "seeds" / "aethryn-authored-scale-1" / "rooms.yaml")
    batch_data = yaml.safe_load(
        (staging / "room_batches" / packet_path.name).read_text(encoding="utf-8")
    )
    for record in batch_data["rooms"].values():
        for destination in record["exits"].values():
            world.setdefault(
                destination,
                {
                    "name": destination,
                    "desc": "An established route anchor remains available for this reload test.",
                    "exits": {},
                },
            )
    apply_room_batches(
        world,
        directory=staging / "room_batches",
    )
    room = world["veridia_living_farmstead"]
    assert room["presentation_version"] == "aethryn-room-v1"
    assert room["short_description"]
    assert room["long_description"]
    assert room["provenance"]["packet_id"] == "veridia_greenhold_living_slice"


def test_city_wilderness_and_dungeon_rooms_use_short_and_verbose_templates() -> None:
    script = """
from kernel.world import world
for room_id in ("greenhold", "veridia_living_wild_loop", "the_black_hollow"):
    normal = world.render_room(room_id)
    verbose = world.render_room(room_id, verbose=True)
    assert "DESCRIPTION" in normal
    assert "EXITS" in normal
    assert "DESCRIPTION" in verbose
    assert len(verbose) >= len(normal)
    assert world.WORLD[room_id]["presentation_version"] == "aethryn-room-v1"
print("ROOM_TEMPLATES_OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env={**os.environ, "FORGE_SEED": "aethryn", "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "ROOM_TEMPLATES_OK" in result.stdout


def test_text_client_look_and_look_verbose_select_the_contract_fields() -> None:
    script = """
from forge import handle_command
from kernel.world.session import SESSIONS, Session
session = Session(player_id="room-prose-look", location="veridia_living_farmstead", named=True)
SESSIONS[session.player_id] = session
normal = handle_command(session, "look")
verbose = handle_command(session, "look verbose")
assert "A small barley holding" in normal
assert "The Veridia setting" not in normal
assert "The Veridia setting" in verbose
assert "POINTS OF INTEREST" in normal
print("LOOK_FIELDS_OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env={**os.environ, "FORGE_SEED": "aethryn", "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "LOOK_FIELDS_OK" in result.stdout
