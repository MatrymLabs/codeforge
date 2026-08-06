"""Runtime-independent, bounded JSON state for script attachments."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from kernel.shelf.atomic_write import atomic_write_text


class StateStoreError(ValueError):
    """State is malformed, too large, or addressed incorrectly."""


class StateConflict(StateStoreError):
    """A compare-and-set write used a stale state version."""


def _json_safe(value: Any) -> None:
    if value is None or isinstance(value, (str, int, bool)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise StateStoreError("state must not contain NaN or infinite numbers")
        return
    if isinstance(value, list):
        for item in value:
            _json_safe(item)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for item in value.values():
            _json_safe(item)
        return
    raise StateStoreError("state must contain only JSON-compatible values")


class InMemoryStateStore:
    def __init__(self, *, max_bytes: int = 64 * 1024) -> None:
        if max_bytes < 128:
            raise ValueError("max_bytes is too small")
        self.max_bytes = max_bytes
        self._values: dict[str, tuple[int, dict[str, Any]]] = {}

    def read(self, partition: str) -> tuple[int, dict[str, Any]]:
        if not partition.strip():
            raise StateStoreError("partition must not be empty")
        version, value = self._values.get(partition, (0, {}))
        return version, dict(value)

    def compare_and_set(
        self, partition: str, expected_version: int, value: Mapping[str, Any]
    ) -> int:
        _json_safe(dict(value))
        encoded = json.dumps(
            dict(value), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        if len(encoded) > self.max_bytes:
            raise StateStoreError("state size quota exceeded")
        current, _ = self.read(partition)
        if current != expected_version:
            raise StateConflict(f"expected state version {expected_version}, current is {current}")
        next_version = current + 1
        self._values[partition] = (next_version, dict(value))
        return next_version

    def snapshot(self, partition: str) -> dict[str, object]:
        version, value = self.read(partition)
        return {"partition": partition, "version": version, "value": value}


class FileStateStore(InMemoryStateStore):
    """Atomic JSON-backed state store; the interpreter heap is never persisted."""

    def __init__(self, path: Path, *, max_bytes: int = 64 * 1024) -> None:
        self.path = Path(path)
        super().__init__(max_bytes=max_bytes)
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise StateStoreError("state file must contain an object")
            for partition, entry in raw.items():
                if not isinstance(partition, str) or not isinstance(entry, dict):
                    raise StateStoreError("malformed state entry")
                version = entry.get("version")
                value = entry.get("value")
                if not isinstance(version, int) or not isinstance(value, dict):
                    raise StateStoreError("malformed state version or value")
                _json_safe(value)
                self._values[partition] = (version, value)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise StateStoreError(f"cannot load state store {self.path}: {exc}") from exc

    def compare_and_set(
        self, partition: str, expected_version: int, value: Mapping[str, Any]
    ) -> int:
        version = super().compare_and_set(partition, expected_version, value)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.path, json.dumps(self._serializable(), indent=2, sort_keys=True) + "\n"
        )
        return version

    def _serializable(self) -> dict[str, object]:
        return {
            partition: {"version": version, "value": value}
            for partition, (version, value) in self._values.items()
        }
