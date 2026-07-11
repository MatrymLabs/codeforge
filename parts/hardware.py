"""CARD: hardware -- the cross-domain reusable-parts catalog (the hardware store).

`make store` auto-lists every engine part from its `CARD:` line. This catalog goes
one level deeper for the parts worth REUSING: it records, per part, where the same
code serves *outside* the game -- government, finance, compliance, records, general
software. The metaphor is a hardware store: one well-made part, many jobs.

The source of truth is data: `catalog/parts.yaml` (override with `CODEFORGE_CATALOG`).
A malformed entry fails loud at load -- a bad part is never stocked. Listing the
catalog has zero side effects (no seed load, no world boot).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from parts import loader_cache

_REQUIRED = ("id", "name", "source", "category", "purpose", "maturity", "risk", "reuse")
# "shipped" reads as its own definition (shipped + tested on main) -- no out-of-context
# overclaim, unlike "production".
_MATURITY = ("prototype", "beta", "shipped")
_RISK = ("low", "medium", "high")
# Free-to-Use rule: only stock parts whose provenance is clearly free to use. A part's
# source_status must be one of these; anything unclear is not stocked in the first place.
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


def _default_catalog_path() -> Path:
    """Where the catalog lives -- resolved at call time so tests can point
    CODEFORGE_CATALOG at a fixture (default args evaluate at def time)."""
    override = os.environ.get("CODEFORGE_CATALOG")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parent.parent / "catalog" / "parts.yaml"


@dataclass(frozen=True)
class Part:
    """One reusable part: what it is, and every domain it serves."""

    id: str
    name: str
    source: str
    category: str
    purpose: str
    maturity: str
    risk: str
    reuse: dict[str, str]
    tags: list[str] = field(default_factory=list)
    reuse_score: int = 0
    source_status: str = "original"  # provenance: original / mit / apache-2.0 / ...
    license: str = "MIT"  # the reuse license (this repo's own code is MIT)
    influence: str = ""  # the KNOWN PATTERN it was rebuilt from -- harvest patterns, not code
    experimental: str = (
        ""  # the road NOT taken: the deliberate alternative (framework or frameless)
    )


class CatalogError(ValueError):
    """A catalog entry is malformed -- fail loud, never stock a bad part."""


def _coerce(raw: Any, index: int) -> Part:
    if not isinstance(raw, dict):
        raise CatalogError(f"part #{index}: expected a mapping, got {type(raw).__name__}")
    missing = [key for key in _REQUIRED if key not in raw]
    if missing:
        raise CatalogError(f"part #{index}: missing {', '.join(missing)}")
    maturity = str(raw["maturity"])
    if maturity not in _MATURITY:
        raise CatalogError(f"part {raw['id']!r}: maturity must be one of {_MATURITY}")
    risk = str(raw["risk"])
    if risk not in _RISK:
        raise CatalogError(f"part {raw['id']!r}: risk must be one of {_RISK}")
    source_status = str(raw.get("source_status", "original"))
    if source_status not in _SOURCE_STATUS:
        raise CatalogError(
            f"part {raw['id']!r}: source_status must be a free-to-use status {_SOURCE_STATUS}"
        )
    reuse = raw["reuse"]
    if not isinstance(reuse, dict) or not reuse:
        raise CatalogError(
            f"part {raw['id']!r}: reuse must be a non-empty mapping of domain -> use"
        )
    return Part(
        id=str(raw["id"]),
        name=str(raw["name"]),
        source=str(raw["source"]),
        category=str(raw["category"]),
        purpose=str(raw["purpose"]).strip(),
        maturity=maturity,
        risk=risk,
        reuse={str(domain): str(use) for domain, use in reuse.items()},
        tags=[str(tag) for tag in raw.get("tags", [])],
        reuse_score=int(raw.get("reuse_score", 0)),
        source_status=source_status,
        license=str(raw.get("license", "MIT")),
        influence=str(raw.get("influence", "")),
        experimental=str(raw.get("experimental", "")).strip(),
    )


def _parse_catalog(source: Path) -> list[Part]:
    """Parse and validate a catalog file into Parts (a bad row raises before caching)."""
    data = yaml.safe_load(source.read_text()) or []
    if not isinstance(data, list):
        raise CatalogError("catalog root must be a list of parts")
    return [_coerce(entry, number) for number, entry in enumerate(data, start=1)]


def load_catalog(path: Path | None = None) -> list[Part]:
    """Load and validate the catalog. A missing catalog is empty, not an error.

    Parsed once and reused until `catalog/parts.yaml` changes on disk, via the shared
    mtime-guarded loader cache (EXP-001; the pattern now lives in `parts/loader_cache.py`).
    """
    source = path or _default_catalog_path()
    if not source.exists():
        return []
    return loader_cache.load_cached(source, _parse_catalog)


def find_part(part_id: str, path: Path | None = None) -> Part | None:
    """Return the part with this id, or None."""
    for part in load_catalog(path):
        if part.id == part_id:
            return part
    return None


def part_haystack(part: Part) -> str:
    """Everything about a part, lowercased -- for a plain substring search."""
    fields = [part.id, part.name, part.category, *part.tags]
    fields += list(part.reuse.keys()) + list(part.reuse.values())
    return " ".join(fields).lower()


def catalog_text(path: Path | None = None) -> str:
    """Render the catalog as display text: each part and every domain it serves."""
    parts = load_catalog(path)
    if not parts:
        return "CODEFORGE HARDWARE CATALOG -- no parts cataloged yet (see catalog/parts.yaml)."
    lines = ["CODEFORGE HARDWARE CATALOG -- reusable parts across domains", ""]
    for part in parts:
        lines.append(
            f"[{part.id}] {part.name}  ({part.category} | {part.maturity} | risk={part.risk})"
        )
        lines.append(f"    source: {part.source}  ({part.source_status}, {part.license})")
        if part.influence:
            lines.append(f"    pattern: {part.influence}")
        lines.append(f"    {part.purpose}")
        for domain, use in part.reuse.items():
            lines.append(f"    - {domain:<11} {use}")
        if part.experimental:
            # The road not taken: the alternative we weighed for this part -- a framework we
            # declined, or (now that we build architecture-first) the frameless path we
            # declined. Shown so the choice reads as deliberate, not as ignorance of the tools.
            lines.append(f"    road not taken: {part.experimental}")
        lines.append("")
    lines.append(f"{len(parts)} part(s) cataloged.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(catalog_text())
