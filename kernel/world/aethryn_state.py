"""CARD: aethryn_state -- small persistent seam for reversible compiled world state."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from kernel.world.aethryn_models import content_digest


class WorldStateError(ValueError):
    """A state transition or persisted state record is invalid."""


@dataclass(frozen=True)
class WorldStateSnapshot:
    values: Mapping[str, str]
    digest: str


class WorldStateStore:
    """Persist and project packet-declared reversible values without mutating room records."""

    def __init__(self, path: Path, schema: Mapping[str, Mapping[str, Any]]) -> None:
        self.path = path
        self.schema = schema

    def _read(self) -> dict[str, str]:
        if not self.path.is_file():
            return {key: str(spec.get("initial_value", "")) for key, spec in self.schema.items()}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in raw.items()
        ):
            raise WorldStateError(
                f"persisted world state {self.path} must be a mapping of text keys and values"
            )
        return dict(raw)

    def values(self) -> dict[str, str]:
        values = self._read()
        for key, spec in self.schema.items():
            value = values.get(key, str(spec.get("initial_value", "")))
            allowed = spec.get("reversible_values", [])
            if allowed and value not in allowed:
                raise WorldStateError(
                    f"world state {key!r} has invalid value {value!r}; use one of {allowed}"
                )
            values[key] = value
        return values

    def get(self, key: str) -> str:
        if key not in self.schema:
            raise WorldStateError(
                f"world state key {key!r} is not declared by the compiled package"
            )
        return self.values()[key]

    def set(self, key: str, value: str) -> None:
        if key not in self.schema:
            raise WorldStateError(
                f"world state key {key!r} is not declared by the compiled package"
            )
        allowed = self.schema[key].get("reversible_values", [])
        if allowed and value not in allowed:
            raise WorldStateError(
                f"world state {key!r} cannot become {value!r}; use one of {allowed}"
            )
        values = self.values()
        values[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(values, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def snapshot(self) -> WorldStateSnapshot:
        values = self.values()
        return WorldStateSnapshot(values=values, digest=content_digest(values))

    def restore(self, snapshot: WorldStateSnapshot) -> None:
        if content_digest(snapshot.values) != snapshot.digest:
            raise WorldStateError(
                "world state snapshot digest does not match its values; restore refused"
            )
        for key, value in snapshot.values.items():
            if key not in self.schema:
                raise WorldStateError(f"world state snapshot contains undeclared key {key!r}")
            allowed = self.schema[key].get("reversible_values", [])
            if allowed and value not in allowed:
                raise WorldStateError(
                    f"world state snapshot value {value!r} is not allowed for {key!r}"
                )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(dict(snapshot.values), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def project_cistern_text(base_description: str, store: WorldStateStore) -> str:
    """Render the slice's state as text while leaving the canonical room record unchanged."""
    status = store.get("greenhold.cistern_status")
    if status == "flowing":
        projection = (
            "The civic gauge has risen: the old cistern is flowing again, "
            "and the public channel runs clear."
        )
    else:
        projection = (
            "The civic gauge sits low: the old cistern remains below service level, "
            "and the public channel is dry."
        )
    return f"{base_description}\n\n{projection}"


def configured_store(seed_name: str) -> WorldStateStore | None:
    """Find the published Aethryn state schema without creating state during startup."""
    if seed_name != "aethryn":
        return None
    root = Path(__file__).resolve().parents[2]
    configured_schema = os.environ.get("AETHRYN_STATE_SCHEMA", "").strip()
    schema_paths = (
        [Path(configured_schema)]
        if configured_schema
        else sorted(
            (root / "content" / "seeds" / "aethryn" / "generated").glob("*/world_state.yaml")
        )
    )
    raw: dict[str, Any] = {}
    for schema_path in schema_paths:
        if not schema_path.is_file():
            continue
        loaded = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise WorldStateError(f"Aethryn state schema {schema_path} must be a mapping")
        raw.update(loaded)
    if not raw:
        return None
    state_path = Path(
        os.environ.get(
            "AETHRYN_STATE_PATH",
            str(root / "content" / "seeds" / "aethryn" / "world_state.json"),
        )
    )
    return WorldStateStore(state_path, raw)


def project_room_text(room_id: str, base_description: str, store: WorldStateStore) -> str:
    """Project any state record attached to a room while preserving the base room text."""
    for key, spec in store.schema.items():
        if spec.get("room_id") == room_id:
            if key == "greenhold.cistern_status":
                return project_cistern_text(base_description, store)
            value = store.get(key)
            template = str(spec.get("visible_projection", "")).strip()
            if template:
                return f"{base_description}\n\n{template.replace('{value}', value)}"
    return base_description
