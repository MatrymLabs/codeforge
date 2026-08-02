"""CARD: blueprint_verb -- the in-game `blueprint` verb over the kernel Blueprint model.

The command face of the Blueprint (style-guide section 2 split): the pure model - the
dataclass, validation, load/write, markdown projection - lives in `kernel/blueprint.py`;
this thin dispatcher is the caller-layer verb that browses, reads, renders (via
`kernel/blueprint_render.py`), and drafts (via the Claude Architect) filed plans. The lazy
render/AI imports live HERE so the kernel model stays pure (no upward reaches).
"""

from __future__ import annotations

from pathlib import Path

from kernel.blueprint import _find, load_all, to_markdown


def blueprint(arg: str = "", root: Path | None = None) -> str:
    """The in-game `blueprint` verb: browse, read, or render a filed plan to HTML."""
    parts = arg.split(maxsplit=1)
    sub = parts[0].lower() if parts else ""
    rest = parts[1].strip() if len(parts) > 1 else ""

    if sub in ("", "list"):
        plans = load_all(root)
        if not plans:
            return "No blueprints filed yet. Author one under blueprints/ (JSON + Markdown twin)."
        lines = ["FORGED BLUEPRINTS", ""]
        lines += [f"  {b.blueprint_id:20} {b.title}  [{b.status}]" for b in plans]
        lines += [
            "",
            "  blueprint show <id>   -- read the plan",
            "  blueprint render <id> -- project it to HTML",
            "  blueprint draft <idea> -- draft a new plan with Claude (needs the AI Architect)",
        ]
        return "\n".join(lines)

    if sub == "show":
        found = _find(rest, root)
        return to_markdown(found) if found else f"No blueprint filed as '{rest}'."

    if sub == "render":
        found = _find(rest, root)
        if not found:
            return f"No blueprint filed as '{rest}'."
        from kernel.blueprint_render import write_html

        path = write_html(found, root=root)
        return f"Rendered '{found.blueprint_id}' to {path}"

    if sub == "draft":
        if not rest:
            return "Describe the idea: blueprint draft <what you want to build>"
        from adapters.architect import ArchitectError
        from adapters.blueprint_ai import BlueprintDraftError, build_claude_drafter

        try:
            drafter = build_claude_drafter()
        except ArchitectError as exc:
            return f"Blueprint drafting needs the Claude Architect: {exc}"
        try:
            drafted = drafter.draft(rest)
        except BlueprintDraftError as exc:
            return f"Could not draft: {exc}"
        return "DRAFT - AI-generated (Tier-4), review before filing:\n\n" + to_markdown(drafted)

    return "Unknown blueprint action. Try: blueprint list | show <id> | render <id> | draft <idea>."
