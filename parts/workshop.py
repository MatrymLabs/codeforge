"""CARD: workshop -- the engineering cockpit inside the MUD.

The Workshop room is where you engineer through the world. This card renders the cockpit
menu: the real tools the Workshop fronts today -- browse the reusable-parts catalog, search
it, plan with blueprints (browse/read/render, and draft one with the Claude Architect), ask
the advisory Architect NPC, and run allowlisted read-only diagnostics. Anything that RUNS
goes through the safe command relay (`parts/shelf/console.py`); anything that would EDIT files is
still gated on the later Proving Ground phases (see docs/proving_ground/). This card itself
never executes a subprocess -- it renders the menu; the verbs do the work.
"""

from parts.hardware import catalog_text, load_catalog, part_haystack

WORKSHOP_ROOM = "workshop"  # the seed room label this cockpit lives in

_INTRO = (
    "The workshop is where you engineer through the world: browse reusable parts, plan with",
    "blueprints, ask the Architect, and run read-only diagnostics -- all from the MUD.",
)

_LIVE = (
    ("catalog / hardware / parts", "browse the reusable-parts catalog"),
    ("reuse <term>", "find a cataloged part for a need (e.g. reuse audit)"),
    ("blueprint", "browse forged plans (idea -> spec -> HTML)"),
    ("blueprint show <id>", "read a plan as Markdown"),
    ("blueprint render <id>", "project a plan to a static HTML page"),
    ("blueprint draft <idea>", "draft a new plan with the Claude Architect (an API key away)"),
    ("ai <prompt>", "ask the Architect NPC (advisory, read-only)"),
    ("console / diagnostics", "run allowlisted read-only checks (lint, types, tests, git)"),
    ("security", "run the SAST scan (bandit) on the engine"),
)
_OWNER = (
    ("@forge <name>", "propose a part skeleton (writes nothing until you approve)"),
    ("@forge approve <name>", "generate the approved candidate into the workspace/ sandbox"),
    ("@arch", "step through the arch into the Proving Ground: review forged candidates"),
)
_COMING = (("cast play", "run a generated cast as its own game (the full loop, later)"),)


def workshop_menu() -> str:
    """The cockpit menu: what the Workshop offers today, and what's coming."""
    lines = ["== The Forge Workshop -- engineering cockpit ==", ""]
    lines += [f"  {line}" for line in _INTRO]
    lines += ["", "Live tools:"]
    lines += [f"  {cmd:<28}{desc}" for cmd, desc in _LIVE]
    lines += ["", "Owner tools (gated, sandboxed - see docs/proving_ground/SAFETY.md):"]
    lines += [f"  {cmd:<28}{desc}" for cmd, desc in _OWNER]
    lines += ["", "Coming (see docs/proving_ground/ROADMAP.md):"]
    lines += [f"  {cmd:<28}{desc}" for cmd, desc in _COMING]
    return "\n".join(lines)


def catalog_view() -> str:
    """The hardware catalog, rendered in-world."""
    return catalog_text()


def reuse_search(term: str) -> str:
    """Find cataloged parts whose id/name/tags/category/domain-uses mention `term`."""
    query = term.strip().lower()
    if not query:
        return "Reuse what? Try: reuse audit"
    hits = [part for part in load_catalog() if query in part_haystack(part)]
    if not hits:
        return f"No cataloged part matches '{term}'. Browse them all with: catalog"
    lines = [f"Parts matching '{term}':"]
    for part in hits:
        lines.append(f"  [{part.id}] {part.name} -- {part.category}")
        for domain, use in part.reuse.items():
            if query in domain.lower() or query in use.lower():
                lines.append(f"      {domain}: {use}")
    return "\n".join(lines)
