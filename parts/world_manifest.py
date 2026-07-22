"""CARD: world_manifest -- a typed, validated identity for a World Package (a seed).

A seed's identity is otherwise implicit: the directory name is its id, its splash art is its title
screen, and its spawn is whatever room happens to be first in rooms.yaml. This makes that identity
EXPLICIT and typed, the way `blueprint` types a part plan and `manifest` types a part: a frozen
WorldManifest (world_id, title, version, description, start_room, authors, tags) that fails loud on
a malformed field. A seed declares one in `seeds/<world>/world.yaml`; a seed that ships none is
still described by a DERIVED manifest (declared=False) so every world is legible either way.

It reads and validates; it never mutates a seed. The engine still spawns at the first room in
rooms.yaml -- the manifest's start_room is the DECLARED spawn, and `check_world` reports when the
two disagree, so a stale manifest is caught, not trusted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parent.parent
_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")  # seed ids are lowercase, hyphenated (first-forge)


class WorldManifestError(ValueError):
    """A WorldManifest was built with an invalid field. Fails loud at construction."""


@dataclass(frozen=True)
class WorldManifest:
    """The typed identity of a World Package: what it is called, where it starts, who made it."""

    world_id: str
    title: str
    start_room: str
    version: str = "0"
    description: str = ""
    authors: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    declared: bool = (
        True  # True from a real world.yaml; False when derived from a manifest-less seed
    )


def _str_tuple(raw: Any, name: str) -> tuple[str, ...]:
    if isinstance(raw, str) or not hasattr(raw, "__iter__"):
        raise WorldManifestError(f"{name} must be a list of strings, got {raw!r}")
    return tuple(str(item) for item in raw)


def from_dict(raw: Any) -> WorldManifest:
    """Build + validate a WorldManifest from a mapping (a parsed world.yaml). Fails loud."""
    if not isinstance(raw, dict):
        raise WorldManifestError(f"a world manifest must be a mapping, got {type(raw).__name__}")
    world_id = str(raw.get("world_id", "")).strip()
    if not _ID_RE.match(world_id):
        raise WorldManifestError(
            f"world_id {world_id!r} must be lowercase, hyphenated (first-forge)"
        )
    title = str(raw.get("title", "")).strip()
    if not title:
        raise WorldManifestError(f"world {world_id!r}: 'title' is required")
    start_room = str(raw.get("start_room", "")).strip()
    if not start_room:
        raise WorldManifestError(
            f"world {world_id!r}: 'start_room' is required (the declared spawn)"
        )
    return WorldManifest(
        world_id=world_id,
        title=title,
        start_room=start_room,
        version=str(raw.get("version", "0")),
        description=str(raw.get("description", "")).strip(),
        authors=_str_tuple(raw.get("authors", ()), "authors"),
        tags=_str_tuple(raw.get("tags", ()), "tags"),
    )


def to_dict(manifest: WorldManifest) -> dict[str, Any]:
    """The canonical, round-trippable mapping (source metadata like `declared` is not content)."""
    return {
        "world_id": manifest.world_id,
        "title": manifest.title,
        "start_room": manifest.start_room,
        "version": manifest.version,
        "description": manifest.description,
        "authors": list(manifest.authors),
        "tags": list(manifest.tags),
    }


def to_markdown(manifest: WorldManifest) -> str:
    """A human-readable world card."""
    origin = "declared (world.yaml)" if manifest.declared else "derived (no world.yaml)"
    lines = [
        f"# World: {manifest.title}",
        "",
        f"- id:          {manifest.world_id}",
        f"- version:     {manifest.version}",
        f"- start room:  {manifest.start_room or '(unknown)'}",
        f"- authors:     {', '.join(manifest.authors) or '(none stated)'}",
        f"- tags:        {', '.join(manifest.tags) or '(none)'}",
        f"- source:      {origin}",
    ]
    if manifest.description:
        lines += ["", manifest.description]
    return "\n".join(lines)


def _seeds_root(root: Path | None) -> Path:
    return (root if root is not None else _ROOT) / "seeds"


def _first_room(seed_dir: Path) -> str:
    """The seed's real spawn: the first room the loader yields (matches world.START_ROOM)."""
    rooms = seed_dir / "rooms.yaml"
    if not rooms.exists():
        return ""
    from parts.seed import load_rooms  # lazy: seed.py binds env at import, keep this module light

    return next(iter(load_rooms(rooms)), "")


def describe_world(seed_name: str, root: Path | None = None) -> WorldManifest:
    """The WorldManifest for a seed: its declared `world.yaml` if present, else a derived one.

    A derived manifest (declared=False) still gives a typed identity for a seed that ships no
    world.yaml -- title de-slugged from the id, start_room read from rooms.yaml -- so every world is
    legible. It reads only; it never writes to the seed."""
    seed_dir = _seeds_root(root) / seed_name
    manifest_path = seed_dir / "world.yaml"
    if manifest_path.exists():
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        if isinstance(raw, dict):
            raw.setdefault("world_id", seed_name)
        return from_dict(raw)
    title = " ".join(word.capitalize() for word in seed_name.replace("_", "-").split("-"))
    return WorldManifest(
        world_id=seed_name,
        title=title,
        start_room=_first_room(seed_dir),
        description="(derived: this seed ships no world.yaml)",
        declared=False,
    )


def check_world(seed_name: str, root: Path | None = None) -> list[str]:
    """Reconcile a DECLARED manifest against the seed: does its start_room match the real spawn?

    Empty list == consistent (or the manifest is derived, nothing to reconcile). A declared spawn
    that does not match the seed's first room is a stale-manifest gap, surfaced not trusted."""
    manifest = describe_world(seed_name, root)
    if not manifest.declared:
        return []
    real_spawn = _first_room(_seeds_root(root) / seed_name)
    if real_spawn and manifest.start_room != real_spawn:
        return [
            f"{seed_name}: manifest start_room '{manifest.start_room}' != the seed's first room "
            f"'{real_spawn}' (the engine spawns at the first room; update world.yaml)"
        ]
    return []
