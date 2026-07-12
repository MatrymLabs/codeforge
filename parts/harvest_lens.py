"""CARD: harvest_lens -- scan source for reusable-pattern candidates not yet in the Hardware Store.

The Hardware Store grows by harvesting proven patterns; this Lens automates the gap analysis we ran
by hand to find `stream-framer` and `typed-event-bus`. It reads Python source with `ast`, finds
symbols whose name or docstring matches a known engineering-pattern signal, and reports the ones NOT
already stocked in the catalog as candidate cards. As code is written, the store learns what it
could preserve next. It READS only: it never writes a card (a human reviews, builds the core + two
adapters + tests + provenance, and files it). Heuristic by design: it surfaces candidates, and the
engineer decides.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

# A signal (a substring in a symbol name or docstring) -> the reusable pattern it hints at.
PATTERN_SIGNALS: dict[str, str] = {
    "bus": "event bus / pub-sub",
    "queue": "queue / task queue",
    "pool": "resource pool",
    "cache": "cache",
    "retry": "retry policy",
    "breaker": "circuit breaker",
    "framer": "stream framer",
    "reducer": "state reducer",
    "throttle": "rate limiting",
    "backoff": "backoff schedule",
    "scheduler": "scheduling",
    "parser": "parsing",
    "supervisor": "supervisor / lifecycle",
    "debounce": "debounce",
    "batch": "batching",
    "pipeline": "pipeline",
    "dispatcher": "dispatch",
    "interner": "interning / flyweight",
}


class HarvestError(ValueError):
    """The Lens was handed source it could not parse."""


@dataclass(frozen=True)
class Candidate:
    """A reusable-pattern candidate found in source but not yet stocked as a card."""

    symbol: str  # the class or function name that hinted at a pattern
    signal: str  # the matched pattern keyword
    pattern: str  # a human description of the pattern
    line: int  # where the symbol is defined


def scan_source(source: str, *, stocked: frozenset[str] = frozenset()) -> list[Candidate]:
    """Return reusable-pattern candidates in `source` whose signal is not already `stocked`."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise HarvestError(f"could not parse source: {exc}") from exc
    seen: set[tuple[str, str]] = set()
    candidates: list[Candidate] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        haystack = f"{node.name} {ast.get_docstring(node) or ''}".lower()
        for signal, pattern in PATTERN_SIGNALS.items():
            key = (node.name, signal)
            if signal in haystack and signal not in stocked and key not in seen:
                seen.add(key)
                candidates.append(Candidate(node.name, signal, pattern, node.lineno))
    return candidates


def stocked_signals(catalog_text: str) -> frozenset[str]:
    """Which pattern signals the catalog already mentions, so the Lens does not re-flag them."""
    lowered = catalog_text.lower()
    return frozenset(signal for signal in PATTERN_SIGNALS if signal in lowered)


def draft_card(candidate: Candidate) -> dict[str, str]:
    """A draft card stub. A human completes it (core + adapters + tests) before filing."""
    return {
        "id": f"{candidate.signal}-candidate",
        "pattern": candidate.pattern,
        "found_in": candidate.symbol,
        "status": "candidate: needs a core + two adapters + tests + provenance to earn a card",
    }


def render_candidates(candidates: list[Candidate]) -> str:
    """A human-readable harvest report."""
    if not candidates:
        return "Harvest Lens: no new pattern candidates. The store is current."
    lines = ["Harvest Lens: reusable-pattern candidates not yet stocked:"]
    lines += [f"  L{c.line}: {c.symbol} -> {c.pattern} (signal '{c.signal}')" for c in candidates]
    lines.append("Each needs a core + two adapters + tests + provenance before it earns a card.")
    return "\n".join(lines)


def harvest(arg: str = "") -> str:
    """The `harvest` verb: scan the parts library for patterns not yet stocked in the store."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    stocked = stocked_signals((root / "catalog" / "parts.yaml").read_text(encoding="utf-8"))
    found: list[Candidate] = []
    for path in sorted((root / "parts").glob("*.py")):
        found.extend(scan_source(path.read_text(encoding="utf-8"), stocked=stocked))
    return render_candidates(found)
