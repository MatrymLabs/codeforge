"""CARD: evolution.store -- persist a bake-off as dated, reproducible evidence.

An EvolutionRun is written to `reports/evolution/<run_id>.json` (structured, every metric)
plus `<run_id>.txt` (the rendered human-selection report). `reports/*` is git-ignored, so
runs are reproducible-from-commit evidence, never committed. The MUD reads these read-only;
producing a run is a separate authorized step (`make evolution`), never a MUD side effect.

Serialization is `dataclasses.asdict` (the whole run is frozen dataclasses), so there is one
source of truth and no hand-maintained schema to drift.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from parts.evolution.bakeoff import EvolutionRun, render_run

_ROOT = Path(__file__).resolve().parent.parent.parent


def evolution_dir(root: Path | None = None) -> Path:
    """Where run evidence lives -- resolved at call time so tests can redirect it.
    Override with CODEFORGE_EVOLUTION_DIR (default: <repo>/reports/evolution)."""
    if root is not None:
        return root
    override = os.environ.get("CODEFORGE_EVOLUTION_DIR")
    return Path(override).expanduser() if override else _ROOT / "reports" / "evolution"


def to_dict(run: EvolutionRun) -> dict[str, Any]:
    """The full run as a plain dict (via asdict -- one source of truth, no drift)."""
    return asdict(run)


def write_run(run: EvolutionRun, root: Path | None = None) -> Path:
    """Write <run_id>.json (structured) + <run_id>.txt (rendered). Returns the .json path."""
    target = evolution_dir(root)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / f"{run.run_id}.json"
    json_path.write_text(json.dumps(to_dict(run), indent=2) + "\n", encoding="utf-8")
    (target / f"{run.run_id}.txt").write_text(render_run(run) + "\n", encoding="utf-8")
    return json_path


def list_runs(root: Path | None = None) -> list[str]:
    """Every stored run id, newest filename last (sorted). Empty if none produced yet."""
    target = evolution_dir(root)
    if not target.is_dir():
        return []
    return sorted(p.stem for p in target.glob("*.json"))


def load_summary(run_id: str, root: Path | None = None) -> dict[str, Any] | None:
    """The structured run record, or None if there is no such run."""
    path = evolution_dir(root) / f"{run_id}.json"
    if not path.exists():
        return None
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def load_report(run_id: str, root: Path | None = None) -> str | None:
    """The rendered report text for a run, or None if there is no such run."""
    path = evolution_dir(root) / f"{run_id}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else None
