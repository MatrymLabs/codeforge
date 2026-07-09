"""CARD: regulations -- reference federal guidance from the Guidance Library.

While you build programs in the forge, `regs` surfaces the tracked federal
sources (CMMC, FAR/DFARS, NIST, CUI, NARA, DCAA...) so code can cite the right
authority. The library is the single source of truth; this card only reads its
registry -- it never copies or edits it.

Point FGL_REGISTRY at the library's source_registry.csv, or clone
federal-guidance-library alongside codeforge (the default).
"""

import csv
import os
from pathlib import Path

REGISTRY_PATH = Path(
    os.environ.get("FGL_REGISTRY", "../federal-guidance-library/data/source_registry.csv")
)

_NOT_MOUNTED = (
    "The guidance library is not mounted. Clone federal-guidance-library beside "
    "codeforge, or set FGL_REGISTRY to its data/source_registry.csv."
)


def _load(path: Path) -> list[dict[str, str]]:
    """Read the library registry CSV, skipping '#' comment and blank lines."""
    lines = [
        ln
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    return list(csv.DictReader(lines))


def regulations_index(domain: str | None = None, path: Path = REGISTRY_PATH) -> str:
    """List tracked sources, optionally filtered to one domain."""
    rows = _load(path)
    if domain is not None:
        rows = [r for r in rows if r["domain"].lower() == domain.lower()]
    if not rows:
        return f"No guidance filed for domain '{domain}'."
    header = f"{'ID':22}{'TIER':5}{'DOMAIN':12}SOURCE"
    lines = [header, "-" * len(header)]
    for r in sorted(rows, key=lambda x: (x["authority_tier"], x["source_id"])):
        lines.append(
            f"{r['source_id']:22}T{r['authority_tier']:<4}{r['domain']:12}{r['source_name']}"
        )
    lines.append(f"\n{len(rows)} source(s) filed. `regs <id>` for detail.")
    return "\n".join(lines)


def regulation_detail(source_id: str, path: Path = REGISTRY_PATH) -> str:
    """Render one source's record card (case-insensitive id match)."""
    rows = _load(path)
    match = next((r for r in rows if r["source_id"].lower() == source_id.lower()), None)
    if match is None:
        return f"No source '{source_id}'. Try `regs` for the index."
    controls = ", ".join(c for c in match["related_internal_controls"].split(";") if c) or "(none)"
    owner = match["internal_owner"] or "(unassigned)"
    last = match["last_checked"] or "(never)"
    version = match["current_version_or_date"] or "unknown"
    changed = match["last_changed"] or "unknown"
    return "\n".join(
        [
            f"== {match['source_id']} — {match['source_name']} ==",
            f"Tier {match['authority_tier']} · {match['domain']} · status: {match['status']}",
            f"Version: {version} · published/last changed: {changed} · last checked: {last}",
            f"Owner: {owner} · cadence: {match['refresh_frequency']}",
            f"Controls: {controls}",
            f"Source: {match['official_url']}",
            f"Reliance: {match['legal_reliance_note'] or '(none noted)'}",
        ]
    )


def regulations_search(query: str, path: Path = REGISTRY_PATH) -> str:
    """List sources whose id, name, or domain mention `query` (e.g. 'nist')."""
    rows = _load(path)
    hits = [
        r
        for r in rows
        if query.lower() in f"{r['source_id']} {r['source_name']} {r['domain']}".lower()
    ]
    if not hits:
        return f"No source or match for '{query}'. Try `regs` for the index."
    header = f"{'ID':22}{'TIER':5}{'DOMAIN':12}SOURCE"
    lines = [f"Guidance matching '{query}':", header, "-" * len(header)]
    for r in sorted(hits, key=lambda x: (x["authority_tier"], x["source_id"])):
        lines.append(
            f"{r['source_id']:22}T{r['authority_tier']:<4}{r['domain']:12}{r['source_name']}"
        )
    lines.append(f"\n{len(hits)} match(es). `regs <id>` for detail.")
    return "\n".join(lines)


def regs(arg: str = "", path: Path = REGISTRY_PATH) -> str:
    """Dispatch: '' -> index; a known domain -> filtered index; an exact id ->
    detail; otherwise a keyword search across id/name/domain (e.g. `regs nist`)."""
    if not path.exists():
        return _NOT_MOUNTED
    arg = arg.strip()
    if not arg:
        return regulations_index(path=path)
    rows = _load(path)
    if arg.lower() in {r["domain"].lower() for r in rows}:
        return regulations_index(domain=arg, path=path)
    if any(r["source_id"].lower() == arg.lower() for r in rows):
        return regulation_detail(arg, path=path)
    return regulations_search(arg, path=path)
