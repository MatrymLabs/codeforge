"""CARD: aethryn_delivery -- versioned packages, semantic diffs, cache, and hotfix contracts."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from kernel.world.aethryn_models import content_digest

PACKAGE_SCHEMA_VERSION = "aethryn-package/1"
HOTFIX_SCHEMA_VERSION = "aethryn-hotfix/1"
CACHE_SCHEMA_VERSION = "aethryn-cache/1"
_GENERATED_METADATA_FIELDS = frozenset(
    {"generation_seed", "generator_name", "generator_version", "provenance", "content_digest"}
)


class DeliveryError(ValueError):
    """A package delivery operation would produce an ambiguous or unsafe artifact."""


@dataclass(frozen=True, slots=True)
class RecordChange:
    """One semantic record change between two compiled packages."""

    kind: str
    stable_id: str
    change: str
    fields: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "stable_id": self.stable_id,
            "change": self.change,
            "fields": list(self.fields),
        }


@dataclass(frozen=True, slots=True)
class ArtifactDiff:
    """A semantic comparison with migration and rollback implications made explicit."""

    first_digest: str
    second_digest: str
    first_package_schema: str
    second_package_schema: str
    changes: tuple[RecordChange, ...]
    categories: tuple[str, ...]
    migration_required: bool
    migration_reasons: tuple[str, ...]

    @property
    def verdict(self) -> str:
        return "WATCHLIST" if self.migration_required else "CLEAN"

    @property
    def changed_ids(self) -> tuple[str, ...]:
        return tuple(f"{change.kind}:{change.stable_id}" for change in self.changes)

    def to_payload(self) -> dict[str, Any]:
        return {
            "first_digest": self.first_digest,
            "second_digest": self.second_digest,
            "first_package_schema": self.first_package_schema,
            "second_package_schema": self.second_package_schema,
            "verdict": self.verdict,
            "migration_required": self.migration_required,
            "migration_reasons": list(self.migration_reasons),
            "categories": list(self.categories),
            "changes": [change.to_payload() for change in self.changes],
        }


def _package_root(path: Path) -> Path:
    if path.is_dir():
        return path
    raise DeliveryError(f"package path is not a directory: {path}")


def _read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise DeliveryError(f"package file is missing: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _package_payload(path: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    root = _package_root(path)
    manifest = _read_yaml(root / "manifest.yaml")
    records = _read_yaml(root / "records.yaml")
    if not isinstance(manifest, dict):
        raise DeliveryError(f"manifest must be a mapping: {root / 'manifest.yaml'}")
    if not isinstance(records, dict):
        raise DeliveryError(f"records must be a mapping: {root / 'records.yaml'}")
    normalized: dict[str, list[dict[str, Any]]] = {}
    for kind, rows in records.items():
        if not isinstance(rows, list):
            raise DeliveryError(f"records.{kind} must be a list: {root / 'records.yaml'}")
        normalized[str(kind)] = [
            dict(row) for row in rows if isinstance(row, Mapping) and _stable_id(row)
        ]
    return manifest, normalized


def package_output_digest(path: Path) -> str:
    """Recompute the digest covered by a compiled package manifest."""
    root = _package_root(path)
    manifest, records = _package_payload(root)
    batch_files = sorted((root / "room_batches").glob("*.yaml"))
    if len(batch_files) != 1:
        raise DeliveryError(f"package must contain exactly one room batch: {root}")
    return content_digest(
        {
            "batch": _read_yaml(batch_files[0]),
            "records": records,
            "world_ir": _read_yaml(root / "world_ir.yaml"),
            "world_state": _read_yaml(root / "world_state.yaml"),
            "prose_similarity": _read_yaml(root / "room_prose_similarity.yaml"),
        }
    )


def validate_package(path: Path) -> None:
    """Refuse hotfix inputs that are not clean or whose contents disagree with their manifest."""
    manifest, _ = _package_payload(path)
    if str(manifest.get("validation_verdict", "")) != "CLEAN":
        raise DeliveryError(f"package validation is not CLEAN: {path}")
    declared = str(manifest.get("output_digest", ""))
    actual = package_output_digest(path)
    if declared != actual:
        raise DeliveryError(
            f"package digest mismatch at {path}; rebuild the package before delivery"
        )


def _stable_id(row: Mapping[str, Any]) -> str:
    return str(row.get("id", row.get("stable_id", "")))


def _record_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        stable_id = _stable_id(row)
        if stable_id in output:
            raise DeliveryError(f"duplicate record id in package: {stable_id}")
        output[stable_id] = row
    return output


def _changed_fields(first: Mapping[str, Any], second: Mapping[str, Any]) -> tuple[str, ...]:
    fields = {
        str(key)
        for key in set(first) | set(second)
        if str(key) not in _GENERATED_METADATA_FIELDS
        if content_digest(first.get(key)) != content_digest(second.get(key))
    }
    return tuple(sorted(fields))


def _categories(kind: str, fields: tuple[str, ...]) -> set[str]:
    categories = {kind}
    field_set = set(fields)
    if kind == "rooms":
        if "exits" in field_set:
            categories.add("exits_changed")
        if field_set & {"parent_region", "parent_zone", "parent_settlement", "parent_wilderness"}:
            categories.add("rooms_moved")
    if kind in {"items", "materials", "recipes", "equipment_sets", "loot_profiles"}:
        categories.add("item_balance")
    if kind in {"merchant_stock_profiles", "economy_flows"}:
        categories.add("merchant_economy")
    if kind in {"npcs", "creatures", "population_profiles", "crowd_specs", "spawn_pools"}:
        categories.add("population")
    if kind in {"quests", "quest_arcs", "quest_pressures", "quest_world_effects"}:
        categories.add("quests")
    if kind in {"state_changes", "public_events"}:
        categories.add("world_state")
    return categories


def _migration_reasons(
    changes: tuple[RecordChange, ...], first_schema: str, second_schema: str
) -> tuple[str, ...]:
    reasons: set[str] = set()
    if first_schema != second_schema:
        reasons.add("package schema changed")
    if any(change.change == "removed" for change in changes):
        reasons.add("records were removed; saved references require review")
    if "rooms_moved" in _all_categories(changes):
        reasons.add("room hierarchy changed; player locations require compatibility handling")
    if "exits_changed" in _all_categories(changes):
        reasons.add("room topology changed; active navigation requires review")
    if any(change.kind in {"state_changes", "public_events"} for change in changes):
        reasons.add("persistent world state changed; state migration must be reviewed")
    return tuple(sorted(reasons))


def _all_categories(changes: tuple[RecordChange, ...]) -> set[str]:
    output: set[str] = set()
    for change in changes:
        output.update(_categories(change.kind, change.fields))
    return output


def semantic_diff(first: Path, second: Path) -> ArtifactDiff:
    """Compare package records by kind and stable id instead of by YAML line position."""
    first_manifest, first_records = _package_payload(first)
    second_manifest, second_records = _package_payload(second)
    changes: list[RecordChange] = []
    for kind in sorted(set(first_records) | set(second_records)):
        left = _record_map(first_records.get(kind, []))
        right = _record_map(second_records.get(kind, []))
        for stable_id in sorted(set(left) | set(right)):
            if stable_id not in left:
                changes.append(RecordChange(kind, stable_id, "added"))
            elif stable_id not in right:
                changes.append(RecordChange(kind, stable_id, "removed"))
            else:
                fields = _changed_fields(left[stable_id], right[stable_id])
                if fields:
                    changes.append(RecordChange(kind, stable_id, "changed", fields))
    ordered_changes = tuple(changes)
    first_schema = str(first_manifest.get("package_schema_version", PACKAGE_SCHEMA_VERSION))
    second_schema = str(second_manifest.get("package_schema_version", PACKAGE_SCHEMA_VERSION))
    categories = tuple(sorted(_all_categories(ordered_changes)))
    reasons = _migration_reasons(ordered_changes, first_schema, second_schema)
    return ArtifactDiff(
        first_digest=str(first_manifest.get("output_digest", content_digest(first_manifest))),
        second_digest=str(second_manifest.get("output_digest", content_digest(second_manifest))),
        first_package_schema=first_schema,
        second_package_schema=second_schema,
        changes=ordered_changes,
        categories=categories,
        migration_required=bool(reasons),
        migration_reasons=reasons,
    )


def format_semantic_diff(diff: ArtifactDiff) -> str:
    """Render a stable human-readable diff suitable for a builder or CI log."""
    lines = [
        f"semantic diff: {diff.verdict}",
        f"first_digest: {diff.first_digest}",
        f"second_digest: {diff.second_digest}",
        f"changes: {len(diff.changes)}",
        f"categories: {', '.join(diff.categories) or '(none)'}",
        f"migration_required: {'yes' if diff.migration_required else 'no'}",
    ]
    if diff.migration_reasons:
        lines.append("migration_reasons:")
        lines.extend(f"- {reason}" for reason in diff.migration_reasons)
    if diff.changes:
        lines.append("records:")
        for change in diff.changes:
            fields = f" [{', '.join(change.fields)}]" if change.fields else ""
            lines.append(f"- {change.change}: {change.kind}:{change.stable_id}{fields}")
    return "\n".join(lines)


def cache_key(*, packet_payload: Any, source_digest: str, compiler_version: str) -> str:
    """Build a deterministic cache key from every declared compilation input."""
    normalized_packet = (
        asdict(cast(Any, packet_payload)) if is_dataclass(packet_payload) else packet_payload
    )
    return content_digest(
        {
            "cache_schema_version": CACHE_SCHEMA_VERSION,
            "packet": normalized_packet,
            "source_digest": source_digest,
            "compiler_version": compiler_version,
        }
    )


def cache_entry(cache_dir: Path, key: str) -> Path:
    return cache_dir / key


def restore_cached_package(cache_dir: Path, key: str, staging: Path) -> bool:
    """Restore a complete validated package when its deterministic key is present."""
    source = cache_entry(cache_dir, key) / "package"
    if not source.is_dir() or not (source / "manifest.yaml").is_file():
        return False
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(source, staging)
    return True


def store_cached_package(cache_dir: Path, key: str, staging: Path) -> None:
    """Store an immutable package copy after the compiler has completed validation."""
    destination = cache_entry(cache_dir, key)
    if destination.exists():
        return
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copytree(staging, destination / "package")
    (destination / "cache.yaml").write_text(
        yaml.safe_dump(
            {"cache_schema_version": CACHE_SCHEMA_VERSION, "key": key},
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def inspect_cache(cache_dir: Path) -> tuple[dict[str, Any], ...]:
    """Return stable cache metadata without reading or mutating source content."""
    if not cache_dir.is_dir():
        return ()
    entries: list[dict[str, Any]] = []
    for entry in sorted(cache_dir.iterdir(), key=lambda path: path.name):
        metadata = entry / "cache.yaml"
        if metadata.is_file():
            payload = _read_yaml(metadata)
            if isinstance(payload, dict):
                entries.append(payload)
    return tuple(entries)


def create_hotfix(base: Path, candidate: Path, output: Path) -> ArtifactDiff:
    """Create a bounded hotfix manifest and changed-record payload from two packages."""
    if output.is_file() or (output.is_dir() and any(output.iterdir())):
        raise DeliveryError(f"hotfix output must be empty: {output}")
    validate_package(base)
    validate_package(candidate)
    diff = semantic_diff(base, candidate)
    if not diff.changes:
        raise DeliveryError("hotfix contains no changed records")
    base_manifest, _ = _package_payload(base)
    candidate_manifest, candidate_records = _package_payload(candidate)
    if diff.first_package_schema != diff.second_package_schema:
        raise DeliveryError(
            "hotfix package schema mismatch; migrate the candidate package before packaging"
        )
    changed_by_kind: dict[str, set[str]] = {}
    for change in diff.changes:
        if change.change != "removed":
            changed_by_kind.setdefault(change.kind, set()).add(change.stable_id)
    changed_records = {
        kind: [row for row in rows if _stable_id(row) in changed_by_kind.get(kind, set())]
        for kind, rows in candidate_records.items()
        if kind in changed_by_kind
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "changed_records.yaml").write_text(
        yaml.safe_dump(changed_records, sort_keys=False), encoding="utf-8"
    )
    manifest = {
        "hotfix_schema_version": HOTFIX_SCHEMA_VERSION,
        "base_build_digest": str(base_manifest.get("output_digest", "")),
        "candidate_build_digest": diff.second_digest,
        "base_package_schema_version": diff.first_package_schema,
        "changed_records": list(diff.changed_ids),
        "categories": list(diff.categories),
        "migration_required": diff.migration_required,
        "migration_reasons": list(diff.migration_reasons),
        "rollback_manifest": {
            "restore_base_build_digest": str(base_manifest.get("output_digest", "")),
            "restore_source": "base package supplied to the hotfix command",
        },
        "validation_verdict": "CLEAN",
    }
    (output / "hotfix.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return diff
