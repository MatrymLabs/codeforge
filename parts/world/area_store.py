"""CARD: area_store -- the holding bench for generated areas: preview, save, promote, export.

The forge (parts/world/caves.py) makes an area; this is where it waits between generation and
publication. It gives the developer the prompt's admin loop: generate an area, preview it, then
regenerate until it is right, promote it from GENERATED_LOCAL to AUTHORED_LOCAL (a human accepts it
into the world's authored lore), and export it to a world-data file. Persistence is a plain JSON
directory (world_areas/, git-ignored and reproducible from the seed) so a generated area is mutable
dev state, kept apart from the static canon in seeds/.

Promotion is the one authority act: it is the human saying "this generated content is now mine,"
so it refuses anything that is not GENERATED_LOCAL (canon can never be "promoted", nor an already
authored area re-promoted). Every store function is small and pure over a directory, so the whole
lifecycle is testable without a running world. `run(argv)` is the mutating half of the `world` CLI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from parts.world import caves
from parts.world.seed import SeedError

# Generated areas are reproducible dev state, not canon: a git-ignored directory beside the repo,
# overridable per-call so tests never touch the real one.
_AREA_DIR = Path(__file__).resolve().parent.parent.parent / "world_areas"


def _dir(area_dir: Path | None) -> Path:
    where = area_dir if area_dir is not None else _AREA_DIR
    where.mkdir(parents=True, exist_ok=True)
    return where


def _path(area_id: str, area_dir: Path | None) -> Path:
    return _dir(area_dir) / f"{area_id}.json"


def save_area(area: dict[str, Any], area_dir: Path | None = None) -> Path:
    """Persist a generated area to its JSON file (stable key order, so a re-save diffs clean)."""
    path = _path(area["id"], area_dir)
    path.write_text(json.dumps(area, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_area(area_id: str, area_dir: Path | None = None) -> dict[str, Any]:
    """Read a stored area. Fails loud (SeedError) if it was never generated or saved."""
    path = _path(area_id, area_dir)
    if not path.exists():
        raise SeedError(f"no stored area {area_id!r} (generate it first)")
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def list_areas(area_dir: Path | None = None) -> list[str]:
    """The ids of every area currently on the bench, sorted."""
    return sorted(p.stem for p in _dir(area_dir).glob("*.json"))


def generate_and_save(
    region_id: str, seed: int, *, size: int | None = None, area_dir: Path | None = None
) -> dict[str, Any]:
    """Forge a cave for (region, seed) and put it on the bench. Deterministic: regenerating with the
    same inputs overwrites with an identical area (the admin loop's 'regenerate before publish')."""
    area = caves.generate_cave(region_id, seed, size=size)
    save_area(area, area_dir)
    return area


def promote(area_id: str, area_dir: Path | None = None) -> dict[str, Any]:
    """Promote GENERATED_LOCAL -> AUTHORED_LOCAL: a human accepts the area into authored lore. Bumps
    the version and re-saves. Refuses anything not GENERATED_LOCAL, so canon or an already-authored
    area can never be promoted by mistake."""
    area = load_area(area_id, area_dir)
    status = area.get("canon_status")
    if status != "GENERATED_LOCAL":
        raise SeedError(
            f"cannot promote {area_id!r}: only GENERATED_LOCAL is promotable (got {status!r})"
        )
    area["canon_status"] = "AUTHORED_LOCAL"
    area["version"] = int(area.get("version", 1)) + 1
    save_area(area, area_dir)
    return area


def export_area(area_id: str, dest: Path, area_dir: Path | None = None) -> Path:
    """Write a stored area to a world-data file the developer chooses (for review or committing into
    seeds/). The export is a snapshot; the bench copy is unchanged."""
    area = load_area(area_id, area_dir)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(area, indent=2, sort_keys=True), encoding="utf-8")
    return dest


def preview(area: dict[str, Any]) -> str:
    """A human-readable summary of a generated area: its identity, provenance, and the shape the
    forge guaranteed, plus its validation verdict."""
    rooms = area["rooms"]
    lines = [
        f"{area['display_name']}  [{area['id']}]",
        f"  {area.get('identity', '')}".rstrip(),
        f"  region {area['region_id']} | biome {area['biome']} | {area['subtype']}",
        f"  status {area['canon_status']} | seed {area['generation_seed']} | {len(rooms)} rooms",
        f"  entrance: {area['entrance']} | return via {area['return_room']}",
        f"  landmark: {area['landmark']}",
        f"  hazard: {area['hazard']} | resource: {area['resource']}",
    ]
    if area.get("hidden"):
        lines.append(f"  hidden: {area['hidden']}")
    if area.get("rumor"):
        lines.append(f"  {area['rumor']}")
    lines.append(f"  micro-story: {area['micro_story']}")
    verdict = "VALID" if not area.get("validation") else f"INVALID: {area['validation']}"
    lines.append(f"  validation: {verdict}")
    return "\n".join(lines)


# The mutating half of the `world` command family (the read-only half is parts/world/survey.py).
_COMMANDS = ("generate-area", "preview-area", "promote", "export", "list-areas")


def run(argv: list[str], area_dir: Path | None = None) -> tuple[int, str]:
    """Dispatch a mutating `world` subcommand. Returns (exit_code, text): 0 ok, 1 refused, 2 usage.
    A bad argument or a failed store op is reported honestly, never swallowed."""
    if not argv:
        return 2, _usage()
    command, rest = argv[0], argv[1:]
    try:
        if command == "generate-area":
            return _cmd_generate(rest, area_dir)
        if command == "preview-area":
            if not rest:
                return 2, "usage: world preview-area <area-id>"
            return 0, preview(load_area(rest[0], area_dir))
        if command == "promote":
            if not rest:
                return 2, "usage: world promote <area-id>"
            area = promote(rest[0], area_dir)
            return 0, f"promoted {area['id']} -> {area['canon_status']} (version {area['version']})"
        if command == "export":
            if len(rest) < 2:
                return 2, "usage: world export <area-id> <dest-file>"
            path = export_area(rest[0], Path(rest[1]), area_dir)
            return 0, f"exported {rest[0]} -> {path}"
        if command == "list-areas":
            ids = list_areas(area_dir)
            return 0, "\n".join(ids) if ids else "(no generated areas on the bench)"
    except SeedError as exc:
        return 1, f"refused: {exc}"
    return 2, f"unknown mutating subcommand: {command!r}\n\n{_usage()}"


def _cmd_generate(rest: list[str], area_dir: Path | None) -> tuple[int, str]:
    """world generate-area <region> [--seed N] [--size N]: forge, save, and preview an area."""
    if not rest:
        return 2, "usage: world generate-area <region> [--seed N] [--size N]"
    region_id = rest[0]
    seed, size = 0, None
    flags = rest[1:]
    for i in range(0, len(flags) - 1, 2):
        if flags[i] == "--seed":
            seed = int(flags[i + 1])
        elif flags[i] == "--size":
            size = int(flags[i + 1])
    area = generate_and_save(region_id, seed, size=size, area_dir=area_dir)
    return 0, preview(area)


def _usage() -> str:
    available = "\n".join(f"  world {c}" for c in _COMMANDS)
    return f"Area generation (mutating half of the `world` tool):\n{available}"
