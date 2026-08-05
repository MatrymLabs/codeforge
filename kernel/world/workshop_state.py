"""Durable, validated state for Creator Workshop publications.

Published changes are an append-only overlay over the shipped Seed package; base Seed files are
never rewritten and experimental drafts remain in memory until the owner explicitly publishes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from kernel.shelf.atomic_write import atomic_write_text


class WorkshopStateError(ValueError):
    """Persisted Workshop state is malformed or cannot be safely read."""


def state_path(seed_id: str) -> Path:
    configured = os.environ.get("CODEFORGE_WORKSHOP_STATE", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".config" / "codeforge" / "workshop" / f"{seed_id}.json"


def load_changes(seed_id: str) -> list[dict[str, Any]]:
    path = state_path(seed_id)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkshopStateError(f"cannot read Workshop state {path}: {exc}") from exc
    if not isinstance(raw, list):
        raise WorkshopStateError(f"Workshop state {path} must contain a list")
    changes: list[dict[str, Any]] = []
    for index, value in enumerate(raw):
        if not isinstance(value, dict) or value.get("kind") not in {"create_npc", "create_item"}:
            raise WorkshopStateError(f"Workshop state {path} entry {index} is invalid")
        payload = value.get("payload")
        if not isinstance(payload, dict) or not all(
            isinstance(payload.get(key), str) and payload[key].strip()
            for key in ("label", "name", "room")
        ):
            raise WorkshopStateError(f"Workshop state {path} entry {index} has invalid payload")
        changes.append({"kind": value["kind"], "payload": dict(payload)})
    return changes


def save_changes(seed_id: str, changes: list[dict[str, Any]]) -> None:
    path = state_path(seed_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(changes, indent=2) + "\n")


def clear_changes(seed_id: str) -> None:
    """Test/deployment cleanup for one exact Seed overlay."""
    path = state_path(seed_id)
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise WorkshopStateError(f"cannot clear Workshop state {path}: {exc}") from exc
