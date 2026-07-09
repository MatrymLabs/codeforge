"""CARD: workshop -- the engineering cockpit inside the MUD (display-only).

The Workshop room is where you engineer through the world. This card renders the
cockpit menu and fronts the read-only tools available today: browsing the hardware
catalog and searching it for a reusable part. Commands that RUN things
(diagnostics, tests, the Architect NPC) arrive later, behind the safe command
relay -- see docs/holodeck/SAFETY.md. This card never executes a subprocess.
"""

from parts.hardware import Part, catalog_text, load_catalog

WORKSHOP_ROOM = "workshop"  # the seed room label this cockpit lives in

_LIVE = (
    ("catalog / hardware / parts", "browse the reusable-parts catalog"),
    ("reuse <term>", "find cataloged parts for a need (e.g. reuse audit)"),
    ("console", "list the read-only diagnostic commands"),
    ("run <check> / diagnostics", "run allowlisted checks (lint, types, tests, git)"),
)
_COMING = (
    ("ai <prompt>", "ask the Architect NPC (advisory)"),
    ("blueprint", "draft a plan for a new part"),
)


def workshop_menu() -> str:
    """The cockpit menu: what the Workshop offers today, and what's coming."""
    lines = ["== The Forge Workshop -- engineering cockpit ==", "", "Live tools:"]
    lines += [f"  {cmd:<28}{desc}" for cmd, desc in _LIVE]
    lines += ["", "Coming (see docs/holodeck/ROADMAP.md):"]
    lines += [f"  {cmd:<28}{desc}" for cmd, desc in _COMING]
    return "\n".join(lines)


def catalog_view() -> str:
    """The hardware catalog, rendered in-world."""
    return catalog_text()


def _haystack(part: Part) -> str:
    """Everything about a part, lowercased, for a plain substring search."""
    fields = [part.id, part.name, part.category, *part.tags]
    fields += list(part.reuse.keys()) + list(part.reuse.values())
    return " ".join(fields).lower()


def reuse_search(term: str) -> str:
    """Find cataloged parts whose id/name/tags/category/domain-uses mention `term`."""
    query = term.strip().lower()
    if not query:
        return "Reuse what? Try: reuse audit"
    hits = [part for part in load_catalog() if query in _haystack(part)]
    if not hits:
        return f"No cataloged part matches '{term}'. Browse them all with: catalog"
    lines = [f"Parts matching '{term}':"]
    for part in hits:
        lines.append(f"  [{part.id}] {part.name} -- {part.category}")
        for domain, use in part.reuse.items():
            if query in domain.lower() or query in use.lower():
                lines.append(f"      {domain}: {use}")
    return "\n".join(lines)
