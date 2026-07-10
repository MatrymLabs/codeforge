"""CARD: law -- legal/policy AWARENESS over the guidance sources (never legal advice).

Reads the same tracked sources as `regs`, but through a compliance-awareness lens:
jurisdiction, freshness, and a hard boundary. CodeForge tracks sources and flags
review needs; it does NOT interpret law or claim compliance. Every view ends with
"No legal conclusion. Human review required." See docs/legal_policy_awareness.md.
"""

from pathlib import Path

from parts.regulations import _NOT_MOUNTED, REGISTRY_PATH, _load

_DISCLAIMER = (
    "Compliance-awareness only - NOT legal advice. CodeForge tracks sources and flags "
    "review needs; it does not interpret law or claim compliance. Human review is "
    "required before relying on any of this."
)
_NO_CONCLUSION = "No legal conclusion. Human review required."
# The federal-guidance registry tracks federal sources; jurisdiction is asserted here,
# not derived from a per-row field, so it is stated as an assumption to confirm.
_JURISDICTION = "United States Federal (assumed from the source registry; confirm per source)"


def law_index(path: Path = REGISTRY_PATH) -> str:
    """List tracked sources through the legal-awareness lens (no conclusions)."""
    rows = _load(path)
    if not rows:
        return "No legal/policy sources are tracked. " + _NO_CONCLUSION
    header = f"{'ID':22}{'DOMAIN':12}{'STATUS':11}SOURCE"
    lines = [_DISCLAIMER, "", header, "-" * len(header)]
    for r in sorted(rows, key=lambda x: (x["authority_tier"], x["source_id"])):
        lines.append(f"{r['source_id']:22}{r['domain']:12}{r['status']:11}{r['source_name']}")
    lines.append(f"\n{len(rows)} source(s) tracked. `law <id>` for one. {_NO_CONCLUSION}")
    return "\n".join(lines)


def law_detail(source_id: str, path: Path = REGISTRY_PATH) -> str:
    """One source through the legal-awareness lens: jurisdiction, freshness, boundary."""
    rows = _load(path)
    match = next((r for r in rows if r["source_id"].lower() == source_id.lower()), None)
    if match is None:
        return f"No source '{source_id}'. Try `law` for the index. {_NO_CONCLUSION}"
    published = match["last_changed"] or "unknown"
    checked = match["last_checked"] or "(never)"
    return "\n".join(
        [
            _DISCLAIMER,
            "",
            f"Source:            {match['source_name']}  ({match['source_id']})",
            f"Jurisdiction:      {_JURISDICTION}",
            f"Issuing domain:    {match['domain']}  ·  authority tier {match['authority_tier']}",
            f"Publication date:  {published}  (confirm with `library verify {match['source_id']}`)",
            f"Freshness/status:  {match['status']}  ·  last checked {checked}",
            f"Official source:   {match['official_url']}",
            "Applicability:     Not determined - human review required.",
            f"Legal conclusion:  {_NO_CONCLUSION}",
        ]
    )


def law(arg: str = "", path: Path | None = None) -> str:
    """Dispatch: '' -> the awareness index; otherwise one source's awareness card.

    REGISTRY_PATH is resolved at call time (not bound as a default), so the tick and
    tests can repoint it."""
    root = path if path is not None else REGISTRY_PATH
    if not root.exists():
        return _NOT_MOUNTED
    arg = arg.strip()
    if not arg:
        return law_index(path=root)
    return law_detail(arg, path=root)
