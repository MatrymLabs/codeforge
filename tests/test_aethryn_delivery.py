"""Test twin for the versioned Aethryn package delivery boundary."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from kernel.world import aethryn_compiler
from kernel.world.aethryn_compiler import compile_packet
from kernel.world.aethryn_delivery import (
    PACKAGE_SCHEMA_VERSION,
    create_hotfix,
    inspect_cache,
    package_output_digest,
    semantic_diff,
)

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "content/seeds/aethryn/design/packets/veridia_greenhold_living_slice.yaml"


def test_manifest_declares_package_and_content_compatibility(tmp_path: Path) -> None:
    staging, manifest = compile_packet(PACKET, output_dir=tmp_path / "package", root=ROOT)

    assert manifest.package_schema_version == PACKAGE_SCHEMA_VERSION
    assert manifest.compiler_version == "aethryn-compiler/1.1"
    assert manifest.content_schema_versions["rooms"] == "aethryn-content/1"
    raw = yaml.safe_load((staging / "manifest.yaml").read_text(encoding="utf-8"))
    assert raw["migration_plan"]["migration_required"] is False


def test_semantic_diff_reports_record_changes_and_migration_implications(tmp_path: Path) -> None:
    first, _ = compile_packet(PACKET, output_dir=tmp_path / "first", root=ROOT)
    second = tmp_path / "second"
    second.mkdir()
    for source in ("manifest.yaml", "world_ir.yaml"):
        (second / source).write_bytes((first / source).read_bytes())
    records = yaml.safe_load((first / "records.yaml").read_text(encoding="utf-8"))
    room = next(row for row in records["rooms"] if row["id"] == "greenhold")
    room["short_description"] = "A revised civic gate stands beneath the orchard wall."
    (second / "records.yaml").write_text(yaml.safe_dump(records, sort_keys=False), encoding="utf-8")

    diff = semantic_diff(first, second)

    assert diff.changes
    assert "rooms" in diff.categories
    assert diff.first_digest == diff.second_digest
    assert diff.migration_required is False


def test_semantic_diff_flags_exit_changes_as_a_review_category(tmp_path: Path) -> None:
    first, _ = compile_packet(PACKET, output_dir=tmp_path / "first", root=ROOT)
    second = tmp_path / "second"
    second.mkdir()
    for source in ("manifest.yaml", "world_ir.yaml"):
        (second / source).write_bytes((first / source).read_bytes())
    records = yaml.safe_load((first / "records.yaml").read_text(encoding="utf-8"))
    room = next(row for row in records["rooms"] if row["id"] == "greenhold")
    room["exits"] = {"north": "changed_destination"}
    (second / "records.yaml").write_text(yaml.safe_dump(records, sort_keys=False), encoding="utf-8")

    diff = semantic_diff(first, second)

    assert "exits_changed" in diff.categories
    assert any(change.stable_id == "greenhold" for change in diff.changes)


def test_cache_reuses_a_validated_package_without_regeneration(tmp_path: Path, monkeypatch) -> None:
    cache = tmp_path / "cache"
    first, first_manifest = compile_packet(
        PACKET,
        output_dir=tmp_path / "first",
        root=ROOT,
        cache_dir=cache,
    )

    def refuse_regeneration(*_args, **_kwargs):
        raise AssertionError("cache hit should not regenerate package records")

    monkeypatch.setattr(aethryn_compiler, "_enriched_records", refuse_regeneration)
    second, second_manifest = compile_packet(
        PACKET,
        output_dir=tmp_path / "second",
        root=ROOT,
        cache_dir=cache,
    )

    assert first_manifest.output_digest == second_manifest.output_digest
    assert (first / "world_ir.yaml").read_bytes() == (second / "world_ir.yaml").read_bytes()
    assert len(inspect_cache(cache)) == 1


def test_hotfix_contains_changed_records_and_rollback_identity(tmp_path: Path) -> None:
    base, _ = compile_packet(PACKET, output_dir=tmp_path / "base", root=ROOT)
    candidate = tmp_path / "candidate"
    shutil.copytree(base, candidate)
    records = yaml.safe_load((base / "records.yaml").read_text(encoding="utf-8"))
    room = next(row for row in records["rooms"] if row["id"] == "greenhold")
    room["short_description"] = "A revised civic gate stands beneath the orchard wall."
    (candidate / "records.yaml").write_text(
        yaml.safe_dump(records, sort_keys=False), encoding="utf-8"
    )
    manifest = yaml.safe_load((candidate / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["output_digest"] = package_output_digest(candidate)
    (candidate / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )

    output = tmp_path / "hotfix"
    diff = create_hotfix(base, candidate, output)
    manifest = yaml.safe_load((output / "hotfix.yaml").read_text(encoding="utf-8"))
    changed = yaml.safe_load((output / "changed_records.yaml").read_text(encoding="utf-8"))

    assert diff.changes
    assert manifest["hotfix_schema_version"] == "aethryn-hotfix/1"
    assert manifest["base_build_digest"]
    assert "rooms:greenhold" in manifest["changed_records"]
    assert [row["id"] for row in changed["rooms"]] == ["greenhold"]
