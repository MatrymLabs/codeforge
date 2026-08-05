"""Durable, validated state for Creator Workshop publications.

Published changes are an append-only overlay over the shipped Seed package; base Seed files are
never rewritten and unpublished drafts are durable until the owner explicitly publishes or rolls
them back.
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


def draft_state_path(seed_id: str) -> Path:
    """Return the exact path for unpublished, owner-scoped Workshop drafts.

    Drafts and published overlays have separate files so a failed publish can never silently
    rewrite the immutable Seed package or the already-published overlay.  The explicit environment
    override keeps tests and packaged deployments away from a developer's home directory.
    """
    configured = os.environ.get("CODEFORGE_WORKSHOP_DRAFTS", "").strip()
    if configured:
        return Path(configured).expanduser()
    path = state_path(seed_id)
    return path.with_name(f"{path.stem}.drafts{path.suffix}")


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


def load_drafts(seed_id: str) -> dict[str, list[dict[str, Any]]]:
    """Load unpublished changes grouped by owner, rejecting malformed state loudly."""
    path = draft_state_path(seed_id)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkshopStateError(f"cannot read Workshop drafts {path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise WorkshopStateError(f"Workshop drafts {path} must contain version 1 state")
    owners = raw.get("owners")
    if not isinstance(owners, dict):
        raise WorkshopStateError(f"Workshop drafts {path} must contain an owners mapping")
    drafts: dict[str, list[dict[str, Any]]] = {}
    for owner, values in owners.items():
        if not isinstance(owner, str) or not owner.strip() or not isinstance(values, list):
            raise WorkshopStateError(f"Workshop drafts {path} contains an invalid owner entry")
        checked: list[dict[str, Any]] = []
        for index, value in enumerate(values):
            if not isinstance(value, dict):
                raise WorkshopStateError(f"Workshop drafts {path} entry {index} is invalid")
            kind = value.get("kind")
            summary = value.get("summary")
            payload = value.get("payload")
            if kind not in {"create_npc", "create_item"} or not isinstance(summary, str):
                raise WorkshopStateError(
                    f"Workshop drafts {path} entry {index} has invalid metadata"
                )
            if not isinstance(payload, dict) or not all(
                isinstance(payload.get(key), str) and payload[key].strip()
                for key in ("label", "name", "room")
            ):
                raise WorkshopStateError(
                    f"Workshop drafts {path} entry {index} has invalid payload"
                )
            checked.append({"kind": kind, "summary": summary, "payload": dict(payload)})
        drafts[owner] = checked
    return drafts


def save_drafts(seed_id: str, drafts: dict[str, list[dict[str, Any]]]) -> None:
    """Atomically persist owner-scoped unpublished Workshop changes."""
    path = draft_state_path(seed_id)
    if not any(drafts.values()):
        clear_drafts(seed_id)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    owners = {
        owner: [
            {
                "kind": change["kind"],
                "summary": change["summary"],
                "payload": dict(change["payload"]),
            }
            for change in changes
        ]
        for owner, changes in drafts.items()
        if changes
    }
    atomic_write_text(path, json.dumps({"version": 1, "owners": owners}, indent=2) + "\n")


def clear_drafts(seed_id: str) -> None:
    """Remove unpublished state for one exact Seed during isolated cleanup or recovery."""
    path = draft_state_path(seed_id)
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise WorkshopStateError(f"cannot clear Workshop drafts {path}: {exc}") from exc


def clear_changes(seed_id: str) -> None:
    """Test/deployment cleanup for one exact Seed overlay."""
    path = state_path(seed_id)
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise WorkshopStateError(f"cannot clear Workshop state {path}: {exc}") from exc


def remove_change(seed_id: str, kind: str, label: str) -> None:
    """Remove one exact published overlay entry for a governed rollback."""
    changes = load_changes(seed_id)
    remaining = [
        change
        for change in changes
        if not (change["kind"] == kind and change["payload"].get("label") == label)
    ]
    if len(remaining) == len(changes):
        raise WorkshopStateError(f"published change {kind}/{label} was not found")
    save_changes(seed_id, remaining)
