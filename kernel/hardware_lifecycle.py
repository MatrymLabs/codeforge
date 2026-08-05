"""CARD: hardware_lifecycle -- governed Hardware Store installation state.

This registry records lifecycle state; it never imports, evaluates, or injects
component source. A component must already exist in the curated catalog and have
a validated Hardware Card before an explicit approval can install it.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from kernel.hardware import find_part
from kernel.manifest import find_manifest


class HardwareLifecycleError(ValueError):
    """A Hardware Store lifecycle operation was invalid or unsafe."""


_TRANSITIONS = {
    "discovered": {"validated"},
    "validated": {"approved"},
    "approved": {"installed"},
    "installed": {"active"},
    "active": {"disabled", "deprecated"},
    "disabled": {"active", "deprecated"},
    "deprecated": {"disabled"},
}


def default_registry_path() -> Path:
    """Return the operator registry path, with an explicit deployment/test override."""
    configured = os.environ.get("CODEFORGE_HARDWARE_REGISTRY", "").strip()
    return (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".config" / "codeforge" / "hardware-registry.json"
    )


@dataclass(frozen=True)
class HardwareRecord:
    """Persistent lifecycle evidence for one cataloged component."""

    component_id: str
    version: str
    state: str
    source: str
    license: str
    provenance: str
    consumers: tuple[str, ...] = ()
    history: tuple[str, ...] = ("discovered",)

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> HardwareRecord:
        """Load a record and reject malformed state rather than repairing it silently."""
        required = ("component_id", "version", "state", "source", "license", "provenance")
        missing = [key for key in required if not str(raw.get(key, "")).strip()]
        if missing:
            raise HardwareLifecycleError(f"Hardware record missing: {', '.join(missing)}")
        state = str(raw["state"])
        history = tuple(str(item) for item in raw.get("history", ()))
        if state not in _TRANSITIONS or not history or history[-1] != state:
            raise HardwareLifecycleError(
                f"invalid Hardware record state/history for {raw['component_id']!r}"
            )
        return cls(
            component_id=str(raw["component_id"]),
            version=str(raw["version"]),
            state=state,
            source=str(raw["source"]),
            license=str(raw["license"]),
            provenance=str(raw["provenance"]),
            consumers=tuple(str(item) for item in raw.get("consumers", ())),
            history=history,
        )


class HardwareRegistry:
    """A file-backed, explicit lifecycle registry for approved Hardware components."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def all(self) -> tuple[HardwareRecord, ...]:
        """Return all records sorted by stable component identifier."""
        if not self.path.exists():
            return ()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HardwareLifecycleError(
                f"cannot read Hardware registry {self.path}: {exc}"
            ) from exc
        if not isinstance(raw, list):
            raise HardwareLifecycleError(f"Hardware registry {self.path} must contain a list")
        return tuple(
            sorted((HardwareRecord.from_dict(item) for item in raw), key=lambda r: r.component_id)
        )

    def get(self, component_id: str) -> HardwareRecord | None:
        """Return one record, if it has been explicitly discovered."""
        return next((record for record in self.all() if record.component_id == component_id), None)

    def discover(self, component_id: str) -> HardwareRecord:
        """Register a real cataloged component after validating its Hardware Card evidence."""
        existing = self.get(component_id)
        if existing is not None:
            return existing
        part = find_part(component_id)
        manifest = find_manifest(component_id)
        if part is None:
            raise HardwareLifecycleError(f"component {component_id!r} is not in catalog/parts.yaml")
        if manifest is None:
            raise HardwareLifecycleError(
                f"component {component_id!r} has no Hardware Card manifest"
            )
        source = Path(__file__).resolve().parent.parent / manifest.source
        if not source.is_file():
            raise HardwareLifecycleError(
                f"component {component_id!r} source is missing: {manifest.source}"
            )
        if not manifest.license.strip() or not manifest.source_status.strip():
            raise HardwareLifecycleError(
                f"component {component_id!r} is missing license/provenance metadata"
            )
        record = HardwareRecord(
            component_id=part.id,
            version=manifest.version,
            state="discovered",
            source=manifest.source,
            license=manifest.license,
            provenance=manifest.source_status,
        )
        self._write((*self.all(), record))
        return record

    def transition(self, component_id: str, target: str) -> HardwareRecord:
        """Perform one explicit lifecycle transition; no transition implies activation."""
        record = self.get(component_id)
        if record is None:
            raise HardwareLifecycleError(f"component {component_id!r} is not discovered")
        if target not in _TRANSITIONS.get(record.state, set()):
            raise HardwareLifecycleError(
                f"cannot move {component_id!r} from {record.state} to {target}"
            )
        updated = HardwareRecord(
            component_id=record.component_id,
            version=record.version,
            state=target,
            source=record.source,
            license=record.license,
            provenance=record.provenance,
            consumers=record.consumers,
            history=(*record.history, target),
        )
        self._write(
            tuple(item for item in self.all() if item.component_id != component_id) + (updated,)
        )
        return updated

    def register_consumer(self, component_id: str, consumer: str) -> HardwareRecord:
        """Record a real consumer only after the component is active."""
        record = self.get(component_id)
        if record is None or record.state != "active":
            raise HardwareLifecycleError("only active components may register consumers")
        label = consumer.strip()
        if not label:
            raise HardwareLifecycleError("consumer must not be empty")
        if label in record.consumers:
            return record
        updated = HardwareRecord(
            component_id=record.component_id,
            version=record.version,
            state=record.state,
            source=record.source,
            license=record.license,
            provenance=record.provenance,
            consumers=(*record.consumers, label),
            history=record.history,
        )
        self._write(
            tuple(item for item in self.all() if item.component_id != component_id) + (updated,)
        )
        return updated

    def rollback(self, component_id: str) -> HardwareRecord:
        """Move a component to its prior safe state, retaining rollback evidence."""
        record = self.get(component_id)
        if record is None or len(record.history) < 2:
            raise HardwareLifecycleError("component has no reversible lifecycle transition")
        target = record.history[-2]
        if target not in _TRANSITIONS.get(record.state, set()):
            raise HardwareLifecycleError(f"cannot roll back {component_id!r} from {record.state}")
        return self.transition(component_id, target)

    def _write(self, records: tuple[HardwareRecord, ...]) -> None:
        """Atomically persist the registry; source files are never modified."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_text(json.dumps([asdict(record) for record in records], indent=2) + "\n")
        temporary.replace(self.path)
