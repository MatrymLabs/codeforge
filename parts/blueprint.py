"""CARD: blueprint -- the Blueprint: a software idea forged into a structured spec.

The forge's planning artifact. A Blueprint captures an idea as DATA before any code: a
permanent label, a title, the intent, the requirements it must satisfy, the security it must
account for (threat model, trust boundaries, authz, failure modes: required, so security is
designed in, not bolted on), and the tasks that would build it. It is authored from the
operator's own words (the Architect NPC advises but never invents) and saved as a JSON record
with a Markdown twin, so a plan is git-diffable
evidence, not a chat log. A loader gate validates every field and fails loud; the static
renderer (`parts/blueprint_render.py`) projects it to HTML. State is the JSON; Markdown and
HTML are projections (architecture law 1: text never mutates the record).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parts.shelf import record_loader

# Identity is a permanent lowercase_snake_case label (frozen identifier, like room/item keys).
_LABEL = re.compile(r"^[a-z][a-z0-9_]*$")
_STATUSES = ("draft", "validated")


class BlueprintError(ValueError):
    """A malformed Blueprint: fail loud at the gate, never render a half-formed plan."""


@dataclass(frozen=True)
class Blueprint:
    """One forged plan: identity, intent, the requirements it must meet, and the build tasks."""

    blueprint_id: str
    title: str
    intent: str
    requirements: tuple[str, ...]
    # Security-by-design: threat model, trust boundaries, authz, failure modes. Required and
    # fail-loud, so no plan is filed without stating what can go wrong (security left of tests).
    security: tuple[str, ...]
    tasks: tuple[str, ...] = ()
    stack: tuple[tuple[str, str], ...] = ()  # (layer, choice) pairs; a plan may not have chosen yet
    status: str = "draft"  # draft | validated -- a VeritasGate label, never inflated


def _clean_list(raw: Any, field: str, bp_id: str) -> tuple[str, ...]:
    """A list of non-empty strings, or a loud refusal."""
    if not isinstance(raw, list):
        raise BlueprintError(
            f"blueprint {bp_id!r}: '{field}' must be a list, got {type(raw).__name__}"
        )
    out: list[str] = []
    for i, item in enumerate(raw):
        text = str(item).strip()
        if not text:
            raise BlueprintError(f"blueprint {bp_id!r}: '{field}[{i}]' is empty")
        out.append(text)
    return tuple(out)


def from_dict(raw: Any) -> Blueprint:
    """Validate a raw mapping into a Blueprint. Every gap fails loud, early, and by name."""
    if not isinstance(raw, dict):
        raise BlueprintError(f"expected a mapping, got {type(raw).__name__}")
    bp_id = str(raw.get("blueprint_id", "")).strip()
    if not _LABEL.match(bp_id):
        raise BlueprintError(f"blueprint_id {bp_id!r} must be lowercase_snake_case")
    title = str(raw.get("title", "")).strip()
    if not title:
        raise BlueprintError(f"blueprint {bp_id!r}: 'title' is required")
    intent = str(raw.get("intent", "")).strip()
    if not intent:
        raise BlueprintError(f"blueprint {bp_id!r}: 'intent' is required")
    requirements = _clean_list(raw.get("requirements", []), "requirements", bp_id)
    if not requirements:
        raise BlueprintError(f"blueprint {bp_id!r}: needs at least one requirement")
    security = _clean_list(raw.get("security", []), "security", bp_id)
    if not security:
        raise BlueprintError(
            f"blueprint {bp_id!r}: needs at least one 'security' consideration "
            "(threat model, trust boundaries, authz, failure modes) -- security by design"
        )
    tasks = _clean_list(raw.get("tasks", []), "tasks", bp_id) if raw.get("tasks") else ()
    stack_raw = raw.get("stack", {})
    if not isinstance(stack_raw, dict):
        raise BlueprintError(f"blueprint {bp_id!r}: 'stack' must be a mapping of layer -> choice")
    stack = tuple((str(layer), str(choice)) for layer, choice in stack_raw.items())
    status = str(raw.get("status", "draft"))
    if status not in _STATUSES:
        raise BlueprintError(f"blueprint {bp_id!r}: status must be one of {_STATUSES}")
    return Blueprint(bp_id, title, intent, requirements, security, tasks, stack, status)


def to_dict(bp: Blueprint) -> dict[str, Any]:
    """The canonical JSON record."""
    return {
        "blueprint_id": bp.blueprint_id,
        "title": bp.title,
        "intent": bp.intent,
        "requirements": list(bp.requirements),
        "security": list(bp.security),
        "tasks": list(bp.tasks),
        "stack": {layer: choice for layer, choice in bp.stack},
        "status": bp.status,
    }


def to_markdown(bp: Blueprint) -> str:
    """The human-readable twin: a plan a reviewer can read in a diff."""
    lines = [
        f"# {bp.title}",
        "",
        f"*{bp.intent}*",
        "",
        f"- **id:** `{bp.blueprint_id}`",
        f"- **status:** {bp.status}",
        "",
        "## Requirements",
        "",
    ]
    lines += [f"{i}. {r}" for i, r in enumerate(bp.requirements, 1)]
    lines += ["", "## Security", ""]
    lines += [f"- {s}" for s in bp.security]
    if bp.tasks:
        lines += ["", "## Tasks", ""]
        lines += [f"- [ ] {t}" for t in bp.tasks]
    if bp.stack:
        lines += ["", "## Stack", ""]
        lines += [f"- **{layer}:** {choice}" for layer, choice in bp.stack]
    return "\n".join(lines) + "\n"


# --- files: JSON record + Markdown twin under blueprints/ --------------------


def _root(root: Path | None = None) -> Path:
    """Repo root, resolved at call time so tests can point at a tmp dir."""
    return root if root is not None else Path(__file__).resolve().parent.parent


def blueprints_dir(root: Path | None = None) -> Path:
    """Where authored Blueprints live (examples included)."""
    return _root(root) / "blueprints"


def load_blueprint(path: Path) -> Blueprint:
    """Read and validate one Blueprint JSON file (a GATE: a bad file fails loud)."""
    return record_loader.load_record(path, from_dict, error=BlueprintError, label="blueprint")


def load_all(root: Path | None = None) -> list[Blueprint]:
    """Every filed Blueprint, sorted by id. A missing directory is empty, not an error."""
    return record_loader.load_dir(
        blueprints_dir(root), from_dict, error=BlueprintError, label="blueprint", recursive=True
    )


def write_blueprint(bp: Blueprint, root: Path | None = None) -> tuple[Path, Path]:
    """File a Blueprint as its JSON record and Markdown twin; returns both paths."""
    base = blueprints_dir(root)
    base.mkdir(parents=True, exist_ok=True)
    json_path = base / f"{bp.blueprint_id}.json"
    md_path = base / f"{bp.blueprint_id}.md"
    json_path.write_text(json.dumps(to_dict(bp), indent=2) + "\n", encoding="utf-8")
    md_path.write_text(to_markdown(bp), encoding="utf-8")
    return json_path, md_path


# --- the tick verb: `blueprint [list | show <id> | render <id>]` -------------


def _find(bp_id: str, root: Path | None = None) -> Blueprint | None:
    return next((b for b in load_all(root) if b.blueprint_id == bp_id), None)


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
        from parts.blueprint_render import write_html

        path = write_html(found, root=root)
        return f"Rendered '{found.blueprint_id}' to {path}"

    if sub == "draft":
        if not rest:
            return "Describe the idea: blueprint draft <what you want to build>"
        from parts.architect import ArchitectError
        from parts.blueprint_ai import BlueprintDraftError, build_claude_drafter

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
