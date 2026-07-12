"""CARD: manifest -- the typed Part Manifest: a reusable part's machine-readable contract.

A PartManifest captures everything known about one reusable part: identity, purpose,
interfaces, dependencies, adapters, tests, and provenance. It is the machine-readable
twin of the hand-written Markdown manifest in docs/hardware/<part_id>.md and the formal
contract a manufacturing loop traces against.

Source of truth: YAML files under docs/hardware/<part_id>.yaml (one per part).
A malformed manifest fails loud at load -- a bad part is never traced.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from parts import loader_cache

_REQUIRED = ("part_id", "name", "version", "maturity", "purpose", "source", "domain")
_MATURITY = ("prototype", "beta", "shipped")
_SOURCE_STATUS = (
    "original",
    "stdlib",
    "public-domain",
    "cc0",
    "unlicense",
    "0bsd",
    "mit",
    "bsd",
    "apache-2.0",
)

_ROOT = Path(__file__).resolve().parent.parent


class ManifestError(ValueError):
    """A part manifest is malformed -- fail loud, never trace a bad part."""


@dataclass(frozen=True)
class PartManifest:
    """One reusable part's contract: everything the manufacturing loop needs to trace it."""

    part_id: str
    name: str
    version: str
    maturity: str
    purpose: str
    source: str
    domain: str
    inputs: str = ""
    outputs: str = ""
    interfaces: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    security: str = ""
    tests: tuple[str, ...] = ()
    license: str = "MIT"
    source_status: str = "original"
    owner: str = ""
    adapters: tuple[str, ...] = ()


def from_dict(raw: Any) -> PartManifest:
    """Validate a raw mapping into a PartManifest. Every gap fails loud, early, by name."""
    if not isinstance(raw, dict):
        raise ManifestError(f"expected a mapping, got {type(raw).__name__}")
    # strip before the required-check so a whitespace-only field fails loud, not late
    missing = [key for key in _REQUIRED if not str(raw.get(key, "")).strip()]
    if missing:
        raise ManifestError(f"manifest missing required fields: {', '.join(missing)}")
    maturity = str(raw["maturity"])
    if maturity not in _MATURITY:
        raise ManifestError(f"maturity {maturity!r} must be one of {_MATURITY}")
    source_status = str(raw.get("source_status", "original"))
    if source_status not in _SOURCE_STATUS:
        raise ManifestError(f"source_status {source_status!r} must be one of {_SOURCE_STATUS}")

    def _str_list(field: str) -> tuple[str, ...]:
        """List fields must be lists: a bare `field:` in YAML is None, not []. Fuzz-found."""
        value = raw.get(field) or []
        if not isinstance(value, list):
            raise ManifestError(f"'{field}' must be a list, got {type(value).__name__}")
        return tuple(str(item) for item in value)

    return PartManifest(
        part_id=str(raw["part_id"]),
        name=str(raw["name"]),
        version=str(raw["version"]),
        maturity=maturity,
        purpose=str(raw["purpose"]).strip(),
        source=str(raw["source"]),
        domain=str(raw["domain"]),
        inputs=str(raw.get("inputs", "")).strip(),
        outputs=str(raw.get("outputs", "")).strip(),
        interfaces=_str_list("interfaces"),
        dependencies=_str_list("dependencies"),
        security=str(raw.get("security", "")).strip(),
        tests=_str_list("tests"),
        license=str(raw.get("license", "MIT")),
        source_status=source_status,
        owner=str(raw.get("owner", "")),
        adapters=_str_list("adapters"),
    )


def to_dict(manifest: PartManifest) -> dict[str, Any]:
    """The canonical dict form (round-trips through from_dict)."""
    return {
        "part_id": manifest.part_id,
        "name": manifest.name,
        "version": manifest.version,
        "maturity": manifest.maturity,
        "purpose": manifest.purpose,
        "source": manifest.source,
        "domain": manifest.domain,
        "inputs": manifest.inputs,
        "outputs": manifest.outputs,
        "interfaces": list(manifest.interfaces),
        "dependencies": list(manifest.dependencies),
        "security": manifest.security,
        "tests": list(manifest.tests),
        "license": manifest.license,
        "source_status": manifest.source_status,
        "owner": manifest.owner,
        "adapters": list(manifest.adapters),
    }


def to_markdown(manifest: PartManifest) -> str:
    """Human-readable projection of a manifest."""
    lines = [
        f"# Part Manifest: {manifest.name}",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| **part_id** | `{manifest.part_id}` |",
        f"| **name** | {manifest.name} |",
        f"| **version** | {manifest.version} ({manifest.maturity}) |",
        f"| **purpose** | {manifest.purpose} |",
        f"| **source** | `{manifest.source}` |",
        f"| **domain** | {manifest.domain} |",
    ]
    if manifest.interfaces:
        lines.append(f"| **interfaces** | `{'`, `'.join(manifest.interfaces)}` |")
    if manifest.dependencies:
        lines.append(f"| **dependencies** | `{'`, `'.join(manifest.dependencies)}` |")
    if manifest.tests:
        lines.append(f"| **tests** | `{'`, `'.join(manifest.tests)}` |")
    if manifest.adapters:
        lines.append(f"| **adapters** | `{'`, `'.join(manifest.adapters)}` |")
    lines.append(
        f"| **license** | {manifest.license} | **source_status** | {manifest.source_status} |"
    )
    lines.append("")
    return "\n".join(lines) + "\n"


# --- file loading: YAML manifests under docs/hardware/ -----------------------


def _manifests_dir(root: Path | None = None) -> Path:
    return (root or _ROOT) / "docs" / "hardware"


def _parse_manifest(path: Path) -> PartManifest:
    """Parse and validate one YAML manifest file."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return from_dict(raw)


def load_manifest(path: Path) -> PartManifest:
    """Load and validate one manifest YAML, cached by mtime."""
    return loader_cache.load_cached(path, _parse_manifest)


def load_all(root: Path | None = None) -> list[PartManifest]:
    """Every filed manifest, sorted by part_id. A missing directory is empty, not an error."""
    base = _manifests_dir(root)
    if not base.is_dir():
        return []
    paths = sorted(base.glob("*.yaml"))
    return sorted([load_manifest(p) for p in paths], key=lambda m: m.part_id)


def find_manifest(part_id: str, root: Path | None = None) -> PartManifest | None:
    """Return the manifest with this part_id, or None."""
    for m in load_all(root):
        if m.part_id == part_id:
            return m
    return None
