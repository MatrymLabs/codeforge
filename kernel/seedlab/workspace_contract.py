"""SeedLab workspace contract: one versioned JSON shape for client panels.

This is the structured client-facing layer over the existing SeedLab projections. It packages the
current Project Hub contract, a normalized project-state snapshot, and the live workspace packages
that the Master Client can render.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from kernel.blueprint import Blueprint
from kernel.hardware import Part, load_catalog
from kernel.hardware_lifecycle import HardwareRecord
from kernel.hardware_migration import RollbackRecord
from kernel.hardware_promotion import PromotionPacketStore
from kernel.seed_package import BuildManifest
from kernel.seedlab.approval import ApprovalError, ApprovalRecord
from kernel.seedlab.artifact_registry import configured_artifact_store
from kernel.seedlab.artifact_store import (
    ArtifactRecord,
    ArtifactStore,
    artifact_labels,
    build_report_artifacts,
)
from kernel.seedlab.connector_registry import ConnectorRegistry, configured_connector_registry
from kernel.seedlab.creator_draft import CreatorDraft, CreatorDraftError
from kernel.seedlab.deployment import DeploymentError, DeploymentRun
from kernel.seedlab.kernel import SeedKernel
from kernel.seedlab.manifest_evidence import ManifestRunEvidence
from kernel.seedlab.manifest_registry import configured_manifest_evidence_store
from kernel.seedlab.model_store import ModelStore, configured_model_store, model_labels
from kernel.seedlab.project_hub import ProjectHub, ProjectState
from kernel.seedlab.project_model import ProjectModel
from kernel.seedlab.provenance_registry import configured_provenance_store
from kernel.seedlab.registry import seed_store
from kernel.seedlab.source_connector import SourceRecord, source_connector_label, source_label
from kernel.seedlab.task import TaskRecord, configured_task_store
from kernel.seedlab.tool_runner import RunLog, ToolRunResult, configured_run_log, run_labels
from kernel.seedlab.workspace_gmcp import workspace_packages

WORKSPACE_CONTRACT_VERSION = "seedlab.workspace/1"

_LIFECYCLE_KEYS = (
    "catalog",
    "drafts",
    "content",
    "tests",
    "approvals",
    "activations",
    "health",
    "rollbacks",
    "promotions",
)


@dataclass(frozen=True)
class WorkspacePackageRecord:
    """One package in the structured workspace contract."""

    package: str
    payload: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {"package": self.package, "payload": self.payload}


@dataclass(frozen=True)
class WorkspaceContract:
    """Versioned workspace contract for the Master Client."""

    contract_version: str
    seed: dict[str, object]
    project: dict[str, object]
    project_state: dict[str, object]
    packages: tuple[WorkspacePackageRecord, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "seed": self.seed,
            "project": self.project,
            "project_state": self.project_state,
            "packages": [package.to_dict() for package in self.packages],
        }


def _default_home(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root)
    return Path(os.environ.get("SEEDLAB_HOME", ".seedlab"))


def _seed_kernel(root: Path | None = None) -> SeedKernel:
    home = _default_home(root)
    backend = os.environ.get("CODEFORGE_SEED_REGISTRY", "file").strip() or "file"
    return SeedKernel(seed_store(backend, home))


def _project_state(
    seed_id: str,
    *,
    source: SourceRecord | None = None,
    model_store: ModelStore,
    run_log: RunLog,
    artifact_store: ArtifactStore,
) -> ProjectState:
    source_labels: tuple[str, ...] = ()
    connector_labels: tuple[str, ...] = ()
    if source is not None:
        source_labels = (source_label(source),)
        connector_labels = (source_connector_label(source),)
    return ProjectState(
        seed_id,
        sources=source_labels,
        connectors=connector_labels,
        models=model_labels(model_store, seed_id),
        builds=run_labels(run_log, seed_id, "build"),
        tests=run_labels(run_log, seed_id, "test"),
        targets=artifact_labels(artifact_store, seed_id),
    )


def build_workspace_contract(
    seed_id: str,
    *,
    root: Path | None = None,
    source: SourceRecord | None = None,
    source_files: Sequence[str] | None = None,
    model: ProjectModel | None = None,
    runs: Sequence[ToolRunResult] | None = None,
    artifacts: Sequence[ArtifactRecord] | None = None,
    blueprints: Sequence[Blueprint] | None = None,
    manifest: BuildManifest | None = None,
    manifest_evidence: Sequence[ManifestRunEvidence] | None = None,
    hardware_records: Sequence[HardwareRecord] | None = None,
    modules: Sequence[Mapping[str, object]] | None = None,
    findings: Sequence[Mapping[str, object]] | None = None,
    lifecycle_evidence: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
    connector_registry: ConnectorRegistry | None = None,
    tasks: Sequence[TaskRecord] | None = None,
) -> WorkspaceContract:
    """Build the client-facing workspace contract from the existing SeedLab projections."""
    home = _default_home(root)
    kernel = _seed_kernel(home)
    record = kernel.get(seed_id)
    model_store = configured_model_store(home)
    run_log = configured_run_log(home)
    artifact_store = configured_artifact_store(home)
    persisted_sources = configured_provenance_store(home).all_for_seed(seed_id)
    registry = connector_registry or configured_connector_registry(home)
    all_registrations = registry.all_for_seed(seed_id)
    registrations = [
        registration
        for registration in all_registrations
        if registration.state in {"registered", "active"}
    ]
    registered_sources = [
        registration.source for registration in registrations if registration.source
    ]
    source_value = source or (
        registered_sources[-1]
        if registered_sources
        else (persisted_sources[-1] if persisted_sources and not all_registrations else None)
    )

    state = _project_state(
        seed_id,
        source=source_value,
        model_store=model_store,
        run_log=run_log,
        artifact_store=artifact_store,
    )
    project = ProjectHub(kernel).contract(seed_id, state=state)
    task_list = list(tasks) if tasks is not None else list(
        configured_task_store(home).all_for_seed(seed_id)
    )
    project["tasks"] = [task.to_dict() for task in task_list]
    deployment = _latest_deployment(home, seed_id)
    if deployment is not None:
        project["deployment"] = deployment.to_dict()
    model_list = model
    if model_list is None:
        seeded_models = model_store.all_for_seed(seed_id)
        if seeded_models:
            model_list = seeded_models[-1]
    run_list = None if runs is None else list(runs)
    artifact_list = None if artifacts is None else list(artifacts)
    blueprint_list = None if blueprints is None else list(blueprints)
    manifest_value = manifest
    module_list = None if modules is None else list(modules)
    finding_list = None if findings is None else list(findings)

    persisted_manifest_evidence = (
        manifest_evidence
        if manifest_evidence is not None
        else configured_manifest_evidence_store(home).all_for_seed(seed_id)
    )
    durable_lifecycle = _durable_lifecycle_evidence(
        home,
        seed_id,
        hardware_records=hardware_records,
        manifest_evidence=persisted_manifest_evidence,
    )
    merged_lifecycle = _merge_lifecycle_evidence(durable_lifecycle, lifecycle_evidence)
    packages = workspace_packages(
        record,
        source=source_value,
        files=list(source_files or []),
        model=model_list,
        runs=run_list if run_list is not None else run_log.for_seed(seed_id),
        artifacts=build_report_artifacts(
            artifact_list if artifact_list is not None else artifact_store.all_for_seed(seed_id)
        ),
        blueprints=blueprint_list,
        manifest=manifest_value,
        modules=module_list,
        findings=finding_list,
        manifest_evidence=persisted_manifest_evidence or None,
        hardware_records=hardware_records,
        lifecycle_evidence=merged_lifecycle,
    )
    seed: dict[str, object] = {
        "id": record.identity.seed_id,
        "name": record.identity.name,
        "owner": record.identity.owner,
        "status": record.status,
        "purpose": record.identity.purpose,
    }
    return WorkspaceContract(
        contract_version=WORKSPACE_CONTRACT_VERSION,
        seed=seed,
        project=project,
        project_state={
            "seed_id": state.seed_id,
            "sources": list(state.sources),
            "connectors": list(state.connectors),
            "models": list(state.models),
            "builds": list(state.builds),
            "tests": list(state.tests),
            "targets": list(state.targets),
            "risks": list(state.risks),
            "decisions": list(state.decisions),
        },
        packages=tuple(WorkspacePackageRecord(package, payload) for package, payload in packages),
    )


def _artifact_store(root: Path) -> ArtifactStore:
    return configured_artifact_store(root)


def _merge_lifecycle_evidence(
    durable: Mapping[str, Sequence[Mapping[str, object]]] | None,
    supplied: Mapping[str, Sequence[Mapping[str, object]]] | None,
) -> Mapping[str, Sequence[Mapping[str, object]]] | None:
    """Overlay an explicit projection seam without replacing durable records.

    Callers may provide records produced by a higher-level adapter, but the workspace contract
    must still include the records persisted by the Seed services. Explicit values win per
    category so migration adapters can temporarily supply a canonical replacement while the
    other categories continue to come from the local durable stores.
    """
    if durable is None and supplied is None:
        return None
    merged: dict[str, Sequence[Mapping[str, object]]] = {
        key: tuple(dict(record) for record in records)
        for key, records in (durable or {}).items()
    }
    for key, records in (supplied or {}).items():
        merged[key] = tuple(dict(record) for record in records)
    return merged


def _durable_lifecycle_evidence(
    home: Path,
    seed_id: str,
    *,
    hardware_records: Sequence[HardwareRecord] | None,
    manifest_evidence: Sequence[ManifestRunEvidence],
) -> Mapping[str, Sequence[Mapping[str, object]]] | None:
    """Read the existing lifecycle stores into one read-only workspace projection.

    This function deliberately does not instantiate mutating stores when their files are absent.
    The records remain owned by their existing services; this is only a typed, fail-loud read of
    their persisted evidence. A missing store is an honest empty category, while malformed state
    raises instead of being presented as a healthy empty projection.
    """
    workshop_root = home / "workshop"
    hardware_root = home / "hardware"
    deployments_root = home / "deployments" / "runs"
    has_durable_state = any(
        (
            (workshop_root / f"{seed_id}.drafts.json").is_file(),
            (workshop_root / "drafts.json").is_file(),
            (workshop_root / f"{seed_id}.json").is_file(),
            (workshop_root / "approvals").is_dir(),
            (hardware_root / "rollbacks").is_dir(),
            (hardware_root / "promotions").is_dir(),
            deployments_root.is_dir(),
            hardware_records is not None,
            bool(manifest_evidence),
        )
    )
    if not has_durable_state:
        return None

    lifecycle: dict[str, list[Mapping[str, object]]] = {
        key: [] for key in _LIFECYCLE_KEYS
    }
    lifecycle["catalog"] = [_catalog_record(part) for part in load_catalog()]
    draft_records: list[Mapping[str, object]] = []
    for draft_path in (workshop_root / f"{seed_id}.drafts.json", workshop_root / "drafts.json"):
        draft_records.extend(_load_drafts(draft_path, seed_id))
    lifecycle["drafts"] = draft_records
    lifecycle["content"] = _load_workshop_content(seed_id)
    lifecycle["tests"] = [
        _manifest_run_record(item) for item in manifest_evidence if item.seed_id == seed_id
    ]
    lifecycle["approvals"] = _load_approvals(workshop_root / "approvals", seed_id)
    lifecycle["activations"] = [
        _hardware_record(item) for item in (hardware_records or ())
        if seed_id in item.consumers
    ]
    lifecycle["health"] = _load_deployment_runs(deployments_root, seed_id)
    lifecycle["rollbacks"] = _load_rollbacks(hardware_root / "rollbacks", seed_id)
    lifecycle["promotions"] = _load_promotions(hardware_root / "promotions")
    return lifecycle


def _load_workshop_content(seed_id: str) -> list[Mapping[str, object]]:
    """Project published Creator Workshop overlays into SeedLab evidence.

    The Workshop state file remains the content authority for the live Seed overlay.  This is a
    read-only bridge: the engineering registry and Master Client see the same published records,
    while no second content catalog or live-world mutation path is introduced.
    """
    from kernel.world import workshop_state

    return [
        {
            "seed_id": seed_id,
            "kind": change["kind"],
            "payload": dict(change["payload"]),
            "state": "published",
        }
        for change in workshop_state.load_changes(seed_id)
    ]


def _catalog_record(part: Part) -> dict[str, object]:
    """Serialize a validated catalog Part without exposing a second catalog authority."""
    values = asdict(part)  # Part is the validated dataclass returned by load_catalog().
    values["reuse_score"] = len(values.get("reuse", {}))
    return values


def _manifest_run_record(item: ManifestRunEvidence) -> dict[str, object]:
    return {
        "evidence_id": item.evidence_id,
        "manifest_id": item.manifest_id,
        "manifest_digest": item.manifest_digest,
        "seed_id": item.seed_id,
        "job_id": item.job_id,
        "event_id": item.event_id,
        "status": item.status,
        "target_profile": item.target_profile,
        "required_components": list(item.required_components),
        "created_at": item.created_at,
    }


def _hardware_record(item: HardwareRecord) -> dict[str, object]:
    return {
        "component_id": item.component_id,
        "version": item.version,
        "state": item.state,
        "license": item.license,
        "provenance": item.provenance,
        "consumers": list(item.consumers),
        "history": list(item.history),
    }


def _load_json_list(path: Path, *, label: str) -> list[object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {label} evidence: {path}") from exc
    if not isinstance(raw, list):
        raise ValueError(f"invalid {label} evidence: {path} must contain a list")
    return raw


def _load_drafts(path: Path, seed_id: str) -> list[Mapping[str, object]]:
    if not path.is_file():
        return []
    try:
        raw_state = json.loads(path.read_text(encoding="utf-8"))
        records: list[Mapping[str, object]] = []
        if isinstance(raw_state, Mapping) and raw_state.get("version") == 1:
            owners = raw_state.get("owners")
            if not isinstance(owners, Mapping):
                raise TypeError("Workshop draft owners must be a mapping")
            for owner_id, drafts in owners.items():
                if not isinstance(owner_id, str) or not isinstance(drafts, list):
                    raise TypeError("Workshop draft owner records are invalid")
                for draft in drafts:
                    if not isinstance(draft, Mapping):
                        raise TypeError("Workshop draft record must be an object")
                    records.append(
                        {
                            "seed_id": seed_id,
                            "owner_id": owner_id,
                            "kind": draft.get("kind"),
                            "summary": draft.get("summary"),
                            "payload": dict(draft.get("payload", {})),
                            "state": "draft",
                        }
                    )
            return records
        for raw in _load_json_list(path, label="CreatorDraft"):
            if not isinstance(raw, Mapping):
                raise TypeError("draft record must be an object")
            draft = CreatorDraft.from_dict(raw)
            if draft.seed_id == seed_id:
                records.append(draft.to_dict())
        return records
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, CreatorDraftError, TypeError) as exc:
        raise ValueError(f"invalid CreatorDraft evidence: {path}") from exc


def _load_approvals(path: Path, seed_id: str) -> list[Mapping[str, object]]:
    if not path.is_dir():
        return []
    records: list[Mapping[str, object]] = []
    for item in sorted(path.glob("*.json")):
        try:
            approval = ApprovalRecord.from_dict(json.loads(item.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ApprovalError) as exc:
            raise ValueError(f"invalid approval evidence: {item}") from exc
        if approval.seed_id == seed_id:
            records.append(approval.to_dict())
    return records


def _load_deployment_runs(path: Path, seed_id: str) -> list[Mapping[str, object]]:
    if not path.is_dir():
        return []
    records: list[Mapping[str, object]] = []
    for item in sorted(path.glob("*.json")):
        try:
            run = DeploymentRun.from_dict(json.loads(item.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, DeploymentError) as exc:
            raise DeploymentError(f"invalid deployment evidence: {item}") from exc
        if run.seed_id == seed_id:
            records.append(run.to_dict())
    return records


def _load_rollbacks(path: Path, seed_id: str) -> list[Mapping[str, object]]:
    if not path.is_dir():
        return []
    records: list[Mapping[str, object]] = []
    for item in sorted(path.glob("*.json")):
        try:
            raw = json.loads(item.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise TypeError("rollback record must be an object")
            rollback = RollbackRecord(
                rollback_id=str(raw["rollback_id"]),
                migration_id=str(raw["migration_id"]),
                component_id=str(raw["component_id"]),
                seed_id=str(raw["seed_id"]),
                from_version=str(raw["from_version"]),
                to_version=str(raw["to_version"]),
                backup_reference=str(raw["backup_reference"]),
                trigger=str(raw["trigger"]),
                status=str(raw["status"]),
                health=str(raw["health"]),
                operator_decision=str(raw["operator_decision"]),
                started_at=str(raw.get("started_at", "")),
                completed_at=str(raw.get("completed_at", "")),
                error=str(raw.get("error", "")),
            )
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(f"invalid rollback evidence: {item}") from exc
        if rollback.seed_id == seed_id:
            records.append(rollback.to_dict())
    return records


def _load_promotions(path: Path) -> list[Mapping[str, object]]:
    if not path.is_dir():
        return []
    store = PromotionPacketStore(path)
    records: list[Mapping[str, object]] = []
    for item in sorted(path.glob("*.json")):
        records.append(store.load(item.stem).to_dict())
    return records


def _latest_deployment(root: Path, seed_id: str) -> DeploymentRun | None:
    """Read the newest local deployment evidence for a Seed, if one exists."""
    runs_root = Path(root) / "deployments" / "runs"
    if not runs_root.is_dir():
        return None
    runs: list[DeploymentRun] = []
    for path in runs_root.glob("*.json"):
        try:
            run = DeploymentRun.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, DeploymentError) as exc:
            raise DeploymentError(f"invalid deployment evidence: {path}") from exc
        if run.seed_id == seed_id:
            runs.append(run)
    return max(runs, key=lambda run: (run.completed_at, run.run_id), default=None)
