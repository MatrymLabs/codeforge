"""CARD: store_index -- organize the Hardware Store catalog by V3 engineering domain and address.

The V3 catalog layers four responsibilities: a permanent IDENTITY (the part's slug `id`, never
changes), a hierarchical CATALOG ADDRESS (domain.ordinal, a computed filing aid), a DISPLAY view,
and METADATA tags. This part realizes the addressing and search layers WITHOUT touching a card:
domains live in `catalog/domains.yaml`, each existing `category` maps to one domain, and a part's
address is derived (domain code + an alphabetical ordinal within the domain). Labels are identity,
numbers are filing aids (parts/catalog.py). It reads only; it never renumbers or edits a card.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from parts.hardware import Part, load_catalog
from parts.paths import resolved_path
from parts.shelf import loader_cache

_UNFILED = "00"


class DomainError(ValueError):
    """The domain taxonomy is malformed -- fail loud, never file against a broken map."""


@dataclass(frozen=True)
class Domain:
    """One V3 engineering domain: a stable code, a name, and the categories it claims."""

    code: str
    name: str
    categories: frozenset[str]


def _domains_path() -> Path:
    return resolved_path(
        "CODEFORGE_DOMAINS", Path(__file__).resolve().parent.parent / "catalog" / "domains.yaml"
    )


def _parse_domains(source: Path) -> list[Domain]:
    raw: Any = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    entries = raw.get("domains") if isinstance(raw, dict) else None
    if not isinstance(entries, list) or not entries:
        raise DomainError("domains.yaml must have a non-empty 'domains' list")
    domains: list[Domain] = []
    seen_codes: set[str] = set()
    claimed: dict[str, str] = {}
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict) or "code" not in entry or "name" not in entry:
            raise DomainError(f"domain #{i}: needs 'code' and 'name'")
        code = str(entry["code"])
        if code in seen_codes:
            raise DomainError(f"domain code {code!r} is not unique")
        seen_codes.add(code)
        cats = entry.get("categories", []) or []
        if not isinstance(cats, list):
            raise DomainError(f"domain {code!r}: 'categories' must be a list")
        for cat in cats:
            if cat in claimed:
                raise DomainError(f"category {cat!r} claimed by both {claimed[cat]!r} and {code!r}")
            claimed[str(cat)] = code
        domains.append(Domain(code, str(entry["name"]), frozenset(str(c) for c in cats)))
    return domains


def load_domains(path: Path | None = None) -> list[Domain]:
    """Load and validate the domain taxonomy. Cached until the file changes on disk."""
    source = path or _domains_path()
    if not source.exists():
        raise DomainError(f"domain taxonomy not found at {source}")
    return loader_cache.load_cached(source, _parse_domains)


def domain_for(part: Part, domains: list[Domain]) -> Domain | None:
    """The domain that claims this part's category, or None if unmapped."""
    return next((d for d in domains if part.category in d.categories), None)


def addressed(parts: list[Part], domains: list[Domain]) -> list[tuple[str, Part]]:
    """Pair each part with its derived catalog address (domain.ordinal), sorted for stable display.

    The ordinal is an alphabetical filing aid within a domain -- it may shift as parts are added;
    the part's slug id never does. Unmapped parts file under domain 00.
    """
    keyed = sorted(
        parts,
        key=lambda p: ((domain_for(p, domains) or Domain(_UNFILED, "", frozenset())).code, p.id),
    )
    out: list[tuple[str, Part]] = []
    counters: dict[str, int] = {}
    for part in keyed:
        code = (domain_for(part, domains) or Domain(_UNFILED, "", frozenset())).code
        counters[code] = counters.get(code, 0) + 1
        out.append((f"{code}.{counters[code]:03d}", part))
    return out


def display_designation(
    part_id: str,
    catalog: list[Part] | None = None,
    domains: list[Domain] | None = None,
) -> str | None:
    """The catalog display designation for a part: `PRT-<domain.ordinal>`, or None if uncatalogued.

    Derived from the taxonomy, never stored: the address is a filing aid that may shift as parts
    are added, while the slug id is identity (ADR-0008, catalog_v3_redesign.md). So a manifest or
    doc computes this at render time rather than freezing a number that can go stale.
    """
    cat = catalog if catalog is not None else load_catalog()
    doms = domains if domains is not None else load_domains()
    for address, part in addressed(cat, doms):
        if part.id == part_id:
            return f"PRT-{address}"
    return None


def search(parts: list[Part], query: str, *, domains: list[Domain] | None = None) -> list[Part]:
    """Multi-field search: match query against id, name, purpose, category, maturity, tags."""
    q = query.strip().lower()
    if not q:
        return []
    domains = domains if domains is not None else []
    hits: list[Part] = []
    for part in parts:
        domain = domain_for(part, domains)
        haystack = " ".join(
            [part.id, part.name, part.purpose, part.category, part.maturity, *part.tags]
        )
        if domain:
            haystack += " " + domain.name
        if q in haystack.lower():
            hits.append(part)
    return hits


def render_index(parts: list[Part] | None = None, domains: list[Domain] | None = None) -> str:
    """Render the catalog organized by V3 engineering domain, each part at its derived address."""
    parts = parts if parts is not None else load_catalog()
    domains = domains if domains is not None else load_domains()
    by_code = {d.code: d for d in domains}
    lines = ["Hardware Store -- V3 catalog by engineering domain", ""]
    current = None
    for address, part in addressed(parts, domains):
        code = address.split(".")[0]
        if code != current:
            current = code
            name = by_code[code].name if code in by_code else "Unfiled"
            lines.append(f"[{code}] {name}")
        lines.append(f"    {address}  {part.id:<22} {part.name}  ({part.maturity})")
    filed = {a.split(".")[0] for a, _ in addressed(parts, domains)}
    lines.append("")
    lines.append(f"{len(parts)} parts across {len(filed)} domains.")
    return "\n".join(lines)


def store(arg: str = "") -> str:
    """The `store` verb: `store` shows the V3 domain index; `store find <query>` searches it."""
    arg = arg.strip()
    if arg.lower().startswith("find"):
        query = arg[4:].strip()
        domains = load_domains()
        hits = search(load_catalog(), query, domains=domains)
        if not hits:
            return f"No parts match '{query}'."
        lines = [f"Parts matching '{query}':"]
        lines += [f"  [{p.id}] {p.name} -- {p.category}" for p in hits]
        return "\n".join(lines)
    return render_index()
