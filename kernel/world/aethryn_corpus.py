"""CARD: aethryn_corpus -- normalize the complete legacy Aethryn source corpus.

The packet compiler started with three deliberately small design packets.  The live seed still
has a larger, older source surface: canonical topology, seed rooms, authored room batches,
procedural region specs, material culture, quests, and runtime prototypes.  This module makes that
surface a first-class compiler input.  It does not replace the runtime loaders; it proves that all
of their source records can be represented in one WorldIR and that declared cross-system links
resolve before publication.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from kernel.world.aethryn_diagnostics import Diagnostic, DiagnosticReport, diagnostic
from kernel.world.aethryn_ir import WorldIR, build_world_ir
from kernel.world.aethryn_models import GenerationPacket, content_digest
from kernel.world.aethryn_references import resolve_references
from kernel.world.aethryn_schema import SchemaRegistry, default_schema_registry
from kernel.world.aethryn_validation import VALID_STATUSES

_ROOT = Path(__file__).resolve().parents[2]
_SEED_ROOT = _ROOT / "content" / "seeds" / "aethryn"

# These are deliberate adapter seams for records produced by the runtime generators rather than
# YAML source.  They are kept explicit so a typo in a source exit still fails reference resolution;
# this is not a wildcard or a "accept any generated id" escape hatch.
_RUNTIME_GENERATED_ROOM_REFERENCES = frozenset(
    {
        "greenhold_inn",
        "greenhold_store",
        "ravenwatch_inn",
        "ravenwatch_store",
        "ravenwatch_market",
        "skyward_spires_0_0",
        "skyward_spires_caves_r0",
        "duskwood_vale_underworks_r0",
        "the_black_hollow_delve_1",
    }
)


@dataclass(frozen=True, slots=True)
class WorldCorpus:
    """All source records visible to the Aethryn full-world compiler boundary."""

    records: Mapping[str, tuple[Mapping[str, Any], ...]]
    source_paths: tuple[str, ...]
    external_ids: Mapping[str, frozenset[str]]
    source_digest: str

    @property
    def counts(self) -> dict[str, int]:
        return {type_id: len(rows) for type_id, rows in sorted(self.records.items())}

    def packet(self) -> GenerationPacket:
        """Adapt the corpus to the existing packet pipeline without losing its source digest."""
        return GenerationPacket(
            packet_id="aethryn_full_world",
            target_type="full_world",
            parent_region="aethryn",
            parent_zone="aethryn",
            canon_status="CANON_WORKING",
            world_purpose="Compile every current Aethryn source into one normalized WorldIR.",
            gameplay_purpose="Provide a deterministic, reference-closed world package boundary.",
            narrative_purpose="Preserve authored and canonical source provenance.",
            inherited_constraints=(
                "preserve stable runtime ids",
                "never silently overwrite sources",
            ),
            threat_range=(1, 300),
            geography_profile={"source": "world_graph.yaml"},
            climate_profile={"source": "fields.yaml"},
            architecture_profile={"source": "rooms.yaml"},
            cultural_profile={"source": "settlements.yaml"},
            economy_profile={"source": "material_culture.yaml"},
            ecology_profile={"source": "wildlands.yaml"},
            required_connections=("topology", "runtime_rooms", "content_references"),
            required_content_counts=self.counts,
            state_scope="full_world",
            forbidden_content=("silent duplicate replacement",),
            generation_seed=0,
            expected_output_paths=("world_ir.yaml", "corpus_manifest.yaml"),
            generator_name="aethryn_full_world_corpus",
            generator_version="1.0",
            source_design_ids=tuple(self.source_paths),
            records=self.records,
            source_paths=self.source_paths,
        )


@dataclass(frozen=True, slots=True)
class WorldCorpusAudit:
    """WorldIR plus all normalization and reference diagnostics."""

    corpus: WorldCorpus
    ir: WorldIR | None
    report: DiagnosticReport

    @property
    def verdict(self) -> str:
        return self.report.verdict


def _slug(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def _status(row: Mapping[str, Any], default: str = "AUTHORED_LOCAL") -> str:
    value = str(row.get("canon_status", default))
    return value if value in VALID_STATUSES else default


def _read(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return value if isinstance(value, dict) else {}


def _region_maps(seed_root: Path) -> tuple[set[str], dict[str, str], dict[str, str]]:
    canon = _read(seed_root / "canon.yaml")
    region_ids = {
        _slug(row.get("id"))
        for row in canon.get("regions", [])
        if isinstance(row, Mapping) and row.get("id")
    }
    graph = _read(seed_root / "world_graph.yaml")
    region_ids.update(_slug(key) for key in graph.get("regions", {}))
    zones = _read(seed_root / "zones.yaml")
    room_region: dict[str, str] = {}
    room_zone: dict[str, str] = {}
    for zone_id, raw in zones.items():
        if not isinstance(raw, Mapping):
            continue
        region = _slug(raw.get("region", zone_id.removesuffix("_zone")))
        region_ids.add(region)
        zone = _slug(zone_id)
        for room_id in raw.get("rooms", ()):
            room = _slug(room_id)
            room_region[room] = region
            room_zone[room] = zone
    return region_ids, room_region, room_zone


def _parent_values(
    row: Mapping[str, Any],
    stable_id: str,
    *,
    region_ids: set[str],
    room_region: Mapping[str, str],
    room_zone: Mapping[str, str],
    source_path: Path,
) -> tuple[str, str]:
    region = _slug(row.get("parent_region") or row.get("region"))
    zone = _slug(row.get("parent_zone") or row.get("zone"))
    if zone.endswith("_zone"):
        region = region or zone.removesuffix("_zone")
    if not region and stable_id in room_region:
        region = room_region[stable_id]
    if not zone and stable_id in room_zone:
        zone = room_zone[stable_id]
    if not region:
        stem = _slug(source_path.stem)
        candidates = sorted(region_ids, key=len, reverse=True)
        region = next((candidate for candidate in candidates if candidate in stem), "")
    if zone and not zone.endswith("_zone"):
        zone = f"{zone}_zone"
    if not zone and region:
        zone = f"{region}_zone"
    return region, zone


def _record(
    stable_id: str,
    raw: Mapping[str, Any],
    *,
    region_ids: set[str],
    room_region: Mapping[str, str],
    room_zone: Mapping[str, str],
    source_path: Path,
) -> dict[str, Any]:
    row = dict(raw)
    row["id"] = stable_id
    row.setdefault("display_name", row.get("name", stable_id))
    row.setdefault("canon_status", _status(row))
    for field_name in ("region", "zone", "parent_region", "parent_zone", "attach"):
        if field_name in row and isinstance(row[field_name], str):
            row[field_name] = _slug(row[field_name])
    if isinstance(row.get("zone"), str) and row["zone"] and not row["zone"].endswith("_zone"):
        row["zone"] = f"{row['zone']}_zone"
    region, zone = _parent_values(
        row,
        stable_id,
        region_ids=region_ids,
        room_region=room_region,
        room_zone=room_zone,
        source_path=source_path,
    )
    if region:
        row["parent_region"] = region
    if zone:
        row["parent_zone"] = zone
    row["source_path"] = str(source_path.relative_to(_ROOT))
    return row


def load_world_corpus(root: Path | None = None) -> tuple[WorldCorpus, DiagnosticReport]:
    """Load the complete current Aethryn source surface into stable record collections."""
    repo_root = (root or _ROOT).resolve()
    seed_root = repo_root / "content" / "seeds" / "aethryn"
    region_ids, room_region, room_zone = _region_maps(seed_root)
    records: dict[str, dict[str, dict[str, Any]]] = {}
    priorities: dict[tuple[str, str], int] = {}
    source_paths: set[str] = set()
    findings: list[Diagnostic] = []

    def add(
        type_id: str, stable_id: str, raw: Mapping[str, Any], path: Path, priority: int
    ) -> None:
        if not stable_id:
            return
        source_paths.add(str(path.relative_to(repo_root)))
        row = _record(
            stable_id,
            raw,
            region_ids=region_ids,
            room_region=room_region,
            room_zone=room_zone,
            source_path=path,
        )
        bucket = records.setdefault(type_id, {})
        key = (type_id, stable_id)
        previous = bucket.get(stable_id)
        if previous is None:
            bucket[stable_id] = row
            priorities[key] = priority
            return
        comparable_previous = {
            key: value for key, value in previous.items() if key != "source_path"
        }
        comparable_row = {key: value for key, value in row.items() if key != "source_path"}
        if comparable_previous == comparable_row:
            return
        explicit_overlay = bool(row.get("replace"))
        if explicit_overlay and priority >= priorities[key]:
            bucket[stable_id] = row
            priorities[key] = priority
            findings.append(
                diagnostic(
                    "explicit_source_overlay",
                    f"{type_id}:{stable_id} is explicitly replaced by a later source",
                    subsystem="corpus_loading",
                    source_path=str(path.relative_to(repo_root)),
                    record_id=stable_id,
                    violated_rule="overlays must declare replace: true",
                    authority_source="Aethryn source precedence",
                    suggested_correction="retain the explicit replace marker and provenance",
                    severity="info",
                )
            )
            return
        findings.append(
            diagnostic(
                "conflicting_source_record",
                f"{type_id}:{stable_id} appears with conflicting payloads",
                subsystem="corpus_loading",
                source_path=str(path.relative_to(repo_root)),
                record_id=stable_id,
                violated_rule="one stable id cannot have competing unapproved sources",
                authority_source="Aethryn source precedence",
                suggested_correction="merge the record or mark the intentional replacement",
            )
        )

    def add_map(path: Path, type_id: str, *, priority: int = 10) -> None:
        for stable_id, raw in _read(path).items():
            if isinstance(raw, Mapping):
                add(type_id, _slug(stable_id), raw, path, priority)

    # Canonical topology and the legacy runtime source maps.
    canon = _read(seed_root / "canon.yaml")
    for raw in canon.get("regions", ()):
        if isinstance(raw, Mapping):
            add("regions", _slug(raw.get("id")), raw, seed_root / "canon.yaml", 30)
    graph = _read(seed_root / "world_graph.yaml")
    for stable_id, raw in graph.get("regions", {}).items():
        if isinstance(raw, Mapping):
            region_id = _slug(stable_id)
            canonical = dict(records.get("regions", {}).get(region_id, {}))
            canonical.pop("source_path", None)
            canonical.update(raw)
            # Canonical region facts and graph adjacency are complementary fields of one region
            # contract, not competing records.  Merge them before the normal duplicate gate.
            records.setdefault("regions", {})[region_id] = _record(
                region_id,
                canonical,
                region_ids=region_ids,
                room_region=room_region,
                room_zone=room_zone,
                source_path=seed_root / "world_graph.yaml",
            )
            priorities[("regions", region_id)] = 35
    for stable_id in graph.get("seas", ()):
        add(
            "seas",
            _slug(stable_id),
            {"display_name": stable_id},
            seed_root / "world_graph.yaml",
            30,
        )

    for filename, type_id in (
        ("zones.yaml", "zones"),
        ("rooms.yaml", "rooms"),
        ("settlements.yaml", "settlements"),
        ("fields.yaml", "wilderness"),
        ("wildlands.yaml", "wilderness"),
        ("underground.yaml", "underground"),
        ("dungeons.yaml", "dungeons"),
        ("npcs.yaml", "npcs"),
        ("items.yaml", "items"),
        ("recipes.yaml", "recipes"),
        ("abilities.yaml", "abilities"),
        ("jobs.yaml", "jobs"),
        ("professions.yaml", "professions"),
        ("sets.yaml", "sets"),
    ):
        add_map(seed_root / filename, type_id)

    # Authored room batches are a source layer, not a second silent runtime authority.
    batch_root = seed_root / "room_batches"
    for path in sorted(batch_root.glob("*.yaml")):
        raw = _read(path)
        rooms = raw.get("rooms", {})
        if isinstance(rooms, Mapping):
            for stable_id, row in rooms.items():
                if isinstance(row, Mapping):
                    add("rooms", _slug(stable_id), row, path, 20 if row.get("replace") else 15)

    # Material culture is a typed multi-document source, not an opaque YAML blob.
    culture = _read(seed_root / "material_culture.yaml")
    for section, type_id in (
        ("materials", "materials"),
        ("families", "item_families"),
        ("qualities", "quality_profiles"),
        ("prototypes", "items"),
        ("recipes", "recipes"),
        ("stations", "crafting_stations"),
        ("merchant_stock", "merchant_stock_profiles"),
        ("loot_profiles", "loot_profiles"),
        ("sets", "equipment_sets"),
    ):
        rows = culture.get(section, {})
        if isinstance(rows, Mapping):
            for stable_id, row in rows.items():
                if isinstance(row, Mapping):
                    add(type_id, _slug(stable_id), row, seed_root / "material_culture.yaml", 25)

    # Quest YAML files use one document per stable quest id.
    quest_root = seed_root / "quests"
    for path in sorted(quest_root.glob("*.yaml")):
        raw = _read(path)
        if raw:
            add("quests_legacy", _slug(raw.get("id", path.stem)), raw, path, 15)

    frozen = {
        type_id: tuple(bucket[key] for key in sorted(bucket))
        for type_id, bucket in sorted(records.items())
    }
    runtime_room_ids: set[str] = {"nowhere", "forge"} | set(_RUNTIME_GENERATED_ROOM_REFERENCES)
    external_ids = {
        "rooms": frozenset(runtime_room_ids),
        "regions": frozenset(region_ids | {"aethryn"}),
        "zones": frozenset(row["id"] for row in frozen.get("zones", ()) if isinstance(row, Mapping))
        | frozenset({"the_shattered_isles_zone", "xil_nath_jungle_zone"}),
        "seas": frozenset(row["id"] for row in frozen.get("seas", ())),
    }
    return WorldCorpus(
        records=frozen,
        source_paths=tuple(sorted(source_paths)),
        external_ids=external_ids,
        source_digest=content_digest({"records": frozen, "sources": sorted(source_paths)}),
    ), DiagnosticReport(tuple(findings))


def audit_world_corpus(root: Path | None = None) -> WorldCorpusAudit:
    """Compile and reference-check the complete source corpus."""
    loaded = load_world_corpus(root)
    # ``load_world_corpus`` returns source diagnostics as its second tuple element so callers can
    # distinguish an intentional overlay from an unapproved duplicate.
    corpus, source_report = loaded
    registry: SchemaRegistry = default_schema_registry()
    ir, normalization = build_world_ir(
        corpus.packet(), registry, external_ids=dict(corpus.external_ids)
    )
    references = resolve_references(ir, registry)
    return WorldCorpusAudit(corpus, ir, source_report.merge(normalization, references))


def format_corpus_audit(audit: WorldCorpusAudit) -> str:
    """Produce stable CLI evidence without hiding the record counts or source digest."""
    lines = [
        f"world corpus: {audit.verdict}",
        f"source_digest: {audit.corpus.source_digest}",
        f"source_files: {len(audit.corpus.source_paths)}",
        "records:",
    ]
    lines.extend(f"  {key}: {value}" for key, value in audit.corpus.counts.items())
    for finding in audit.report.diagnostics:
        lines.append(f"{finding.severity}: {finding.code}: {finding.message}")
    return "\n".join(lines)
