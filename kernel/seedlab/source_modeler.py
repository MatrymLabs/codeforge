"""CARD: source_modeler -- extract a structured ProjectModel from a registered local source, and
store it, marking honestly what was inferred versus what could not be determined.

Stage 4 of the Seed Platform directive: turn a connected project (a `LocalSource` from Stage 3) into
a machine-readable model the Seed can inspect and the Master Client can render. It reads only what
the connector approves (manifests + file layout) and derives what it safely can:

  * identity   -- from a manifest (`pyproject.toml` / `package.json`), else the directory name.
  * entities   -- inferred from top-level packages and module names (NOT from code analysis).
  * interfaces -- detected entry points (declared scripts, `__main__.py`/`cli.py`, the manifests).
  * provenance -- carried straight from the source (the model is linked to its source evidence).

Everything it could not determine (relationships, states, actions, inputs, outputs, and the basis of
each inference) is listed in `unknowns`. The directive's rule is explicit: never claim complete
automated understanding. `model_and_store` extracts and persists in one call. No `kernel/world/`
coupling. Status: PROTOTYPED (see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from kernel.seedlab.model_store import ModelStore, model_id_for
from kernel.seedlab.project_model import ProjectModel
from kernel.seedlab.source_connector import LocalSource, SourceConnectorError

# Filenames that signal a runnable entry point (an interface a target could expose).
_ENTRY_POINTS = ("__main__.py", "cli.py", "main.py")


def _read_manifest(source: LocalSource, name: str) -> dict | None:
    """Read + parse a manifest if present and well-formed; None otherwise (never raises)."""
    try:
        text = source.read(name)
    except SourceConnectorError:
        return None
    try:
        if name == "pyproject.toml":
            return tomllib.loads(text)
        if name == "package.json":
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
    except (tomllib.TOMLDecodeError, json.JSONDecodeError):
        return None
    return None


def _resolve_identity(
    source: LocalSource, files: list[str], explicit: str | None
) -> tuple[str, str]:
    """Return (identity, note). Explicit wins; else a manifest name; else the dir name."""
    if explicit and explicit.strip():
        return explicit.strip(), "identity supplied explicitly"
    if "pyproject.toml" in files:
        data = _read_manifest(source, "pyproject.toml")
        name = (data or {}).get("project", {}).get("name")
        if isinstance(name, str) and name.strip():
            return name.strip(), "identity read from pyproject.toml"
    if "package.json" in files:
        data = _read_manifest(source, "package.json")
        name = (data or {}).get("name")
        if isinstance(name, str) and name.strip():
            return name.strip(), "identity read from package.json"
    return Path(source.root).name, "identity inferred from the directory name (no manifest name)"


def _infer_entities(files: list[str], *, cap: int = 20) -> list[str]:
    """Candidate entities from the layout: top-level packages + module stems. Inferred, capped."""
    entities: set[str] = set()
    for rel in files:
        parts = rel.split("/")
        if len(parts) > 1 and parts[0] not in ("tests", "test", "docs"):
            entities.add(parts[0])  # a top-level package/dir
        leaf = parts[-1]
        if leaf.endswith(".py") and leaf != "__init__.py" and not leaf.startswith("test_"):
            entities.add(leaf[:-3])  # a module
    return sorted(entities)[:cap]


def _infer_interfaces(source: LocalSource, files: list[str]) -> list[str]:
    """Detected entry points: declared console scripts, runnable modules, and the manifests."""
    interfaces: set[str] = set(source.identify()["manifests"])
    for rel in files:
        if rel.split("/")[-1] in _ENTRY_POINTS:
            interfaces.add(rel)
    data = _read_manifest(source, "pyproject.toml") if "pyproject.toml" in files else None
    for script in (data or {}).get("project", {}).get("scripts", {}):
        interfaces.add(f"script:{script}")
    return sorted(interfaces)


def model_from_source(source: LocalSource, *, identity: str | None = None) -> ProjectModel:
    """Extract a ProjectModel from a registered source. Fills what is safely derivable and lists
    everything else in `unknowns` -- the model never overstates what it understands."""
    files = source.list_files()
    ident, ident_note = _resolve_identity(source, files, identity)
    unknowns = [
        ident_note,
        "entities inferred from file/directory names, not from code analysis",
        "relationships, states, actions, inputs, and outputs are not inferred "
        "(no behavioral analysis performed)",
    ]
    return ProjectModel(
        identity=ident,
        provenance=source.provenance,
        entities=_infer_entities(files),
        interfaces=_infer_interfaces(source, files),
        unknowns=unknowns,
    )


def model_and_store(store: ModelStore, seed_id: str, source: LocalSource) -> ProjectModel:
    """Extract a model from a source and persist it under the Seed. Returns the stored model."""
    model = model_from_source(source)
    store.save(seed_id, model_id_for(model), model)
    return model
