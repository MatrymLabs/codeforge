"""CARD: cast -- forge a standalone game project (a "cast") from a seed pack + the engine.

A seed PACK is a game's content (`seeds/<name>/*.yaml`). A CAST is what leaves the forge:
a standalone, installable project poured from the engine + one chosen seed pack + config.

This is the Phase-1 scaffold. It PLANS a cast -- a dry run that lists what it *would* copy
and the manifest it *would* write -- and it WRITES NOTHING. Real generation, migration, and
detachment come in later phases. Two honesty rules hold the line:

  1. The plan reports `engine_strategy: "vendored-whole"` -- never a false a-la-carte module
     list. The engine is one coupled package; it cannot yet be selected apart. No claim
     without correspondence.
  2. It never touches `seeds/`, `--seed`, or `FORGE_SEED` -- it READS a seed pack and would
     WRITE a new cast elsewhere. The frozen identifiers stay frozen.

See docs/seed_architecture.md for the full doctrine (seed pack vs cast, the phased plan).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_ROOT = _ROOT / "seed_templates"
SEEDS_ROOT = _ROOT / "seeds"

PLANNED = "planned"
READY = "ready"
BLOCKED = "blocked"

# What a cast must NEVER carry out of the forge -- state, secrets, evidence, flagship
# identity, the other games. Grounded in .gitignore + the safety rules.
_EXCLUDE_CATEGORIES: tuple[str, ...] = (
    "runtime state (codeforge.db · save.json · characters/accounts.json · *.kdbx)",
    "secrets (.env · .secrets.baseline audit trail)",
    "generated evidence (reports/ · security-evidence/ · coverage.xml)",
    "environment + caches (.venv/ · __pycache__/)",
    "the OTHER seed packs (a cast carries only its own game)",
    "flagship branding (README · CHANGELOG · CAPTAINS_LOG · DEVELOPMENT_PLAN)",
    "CodeForge-only dev tooling + the seed generator itself",
)


class CastError(Exception):
    """A malformed template or a missing prerequisite -- fail loud, never guess."""


@dataclass(frozen=True)
class CastManifest:
    """What a cast is and where it came from. Written into the cast (later phases);
    for now, produced by the dry-run plan so the shape is real and testable."""

    seed_id: str
    seed_name: str
    template: str
    generated_by: str = "CodeForge"
    codeforge_commit: str = "unknown"
    engine_strategy: str = "vendored-whole"
    starter_seed_pack: str = ""
    status: str = PLANNED  # planned | generated | detached | validated | not_validated
    detached: bool = False
    copied_categories: list[str] = field(default_factory=list)
    excluded_categories: list[str] = field(default_factory=list)
    known_limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def write_manifest(manifest: CastManifest, path: Path) -> None:
    """Serialize a manifest to JSON (used by the real generator; here for round-trip tests)."""
    path.write_text(json.dumps(manifest.to_dict(), indent=2) + "\n", encoding="utf-8")


def read_manifest(path: Path) -> CastManifest:
    """Read a manifest back; a malformed file fails loud."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CastError(f"unreadable cast manifest at {path}: {exc}") from exc
    return CastManifest(**data)


def available_templates(root: Path | None = None) -> list[str]:
    """The seed templates on the shelf -- dirs under seed_templates/ with a manifest."""
    base = root or TEMPLATES_ROOT
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if (p / "template_manifest.json").is_file())


def load_template(name: str, root: Path | None = None) -> dict:
    """Load a template blueprint; a missing or malformed manifest fails loud (a GATE)."""
    manifest = (root or TEMPLATES_ROOT) / name / "template_manifest.json"
    if not manifest.is_file():
        avail = ", ".join(available_templates(root)) or "(none)"
        raise CastError(f"unknown template '{name}'. Available: {avail}")
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CastError(f"malformed template_manifest.json for '{name}': {exc}") from exc
    for req in ("template_id", "starter_seed_pack", "engine_strategy"):
        if req not in data:
            raise CastError(f"template '{name}' is missing required key '{req}'")
    return data


@dataclass(frozen=True)
class CastPlan:
    """The dry-run verdict: what a cast WOULD contain -- nothing is written."""

    cast_name: str
    template: str
    manifest: CastManifest
    verdict: str  # ready | blocked
    warnings: list[str]


def plan_cast(
    template: str,
    name: str,
    commit: str = "unknown",
    root: Path | None = None,
) -> CastPlan:
    """Dry-run: read the template, decide what a cast would copy, build its manifest. Writes
    nothing. Blocks (with a reason) if the template's starter seed pack is not installed."""
    base = root or _ROOT
    tpl = load_template(template, base / "seed_templates" if root else None)
    starter = tpl["starter_seed_pack"]

    warnings: list[str] = []
    seeds_root = (base / "seeds") if root else SEEDS_ROOT
    pack_present = (seeds_root / starter).is_dir()
    if not pack_present:
        warnings.append(
            f"starter seed pack '{starter}' is not installed under seeds/ -- cannot pour a world"
        )

    copied = [
        "engine (parts/ + forge.py) -- WHOLE, vendored (the engine is not yet decoupled)",
        f"seed pack '{starter}' -- the cast's world",
        "fresh scaffold (pyproject · README · seed.toml · cast_manifest · .gitignore · LICENSE)",
    ]

    limitations = [
        "engine copied whole -- module-level selection (combat/quests/...) is Phase 2, not now",
        "dry-run scaffold: this plans a cast; it does not generate, detach, or boot one",
    ]

    manifest = CastManifest(
        seed_id=f"CAST-{name.upper()}-001",
        seed_name=name,
        template=tpl["template_id"],
        codeforge_commit=commit,
        engine_strategy=tpl["engine_strategy"],
        starter_seed_pack=starter,
        status=PLANNED,
        copied_categories=copied,
        excluded_categories=list(_EXCLUDE_CATEGORIES),
        known_limitations=limitations,
    )
    verdict = READY if pack_present else BLOCKED
    return CastPlan(
        cast_name=name, template=template, manifest=manifest, verdict=verdict, warnings=warnings
    )


def render_plan(plan: CastPlan) -> str:
    """The human report for a planned cast -- what would leave the forge, and what would not."""
    m = plan.manifest
    glyph = "🟢" if plan.verdict == READY else "⛔"
    lines = [
        f"Cast plan — {plan.cast_name} (from template '{plan.template}')",
        "",
        f"  seed_id         {m.seed_id}",
        f"  starter pack    {m.starter_seed_pack}",
        f"  engine strategy {m.engine_strategy}",
        f"  status          {m.status}  (dry run — nothing written)",
        "",
        "  WOULD COPY:",
        *[f"    + {c}" for c in m.copied_categories],
        "",
        "  WOULD NEVER COPY:",
        *[f"    - {c}" for c in m.excluded_categories],
        "",
        "  KNOWN LIMITATIONS (honest):",
        *[f"    ! {c}" for c in m.known_limitations],
    ]
    if plan.warnings:
        lines += ["", "  WARNINGS:", *[f"    ! {w}" for w in plan.warnings]]
    lines += [
        "",
        f"{glyph} {plan.verdict.upper()} — "
        + (
            "this cast could be poured (generation lands in a later phase)."
            if plan.verdict == READY
            else "resolve the blocker(s) above before this cast can be poured."
        ),
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI (`python -m parts.cast <template> <name> [commit]`, `make cast-plan`): plan a cast.

    Exit 0 if the plan is READY, 1 if BLOCKED. Writes nothing -- it is a dry run.
    """
    import sys

    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 2:
        print("usage: python -m parts.cast <template> <name> [commit]", file=sys.stderr)
        print(f"templates: {', '.join(available_templates()) or '(none)'}", file=sys.stderr)
        return 2
    template, name = args[0], args[1]
    commit = args[2] if len(args) > 2 else "unknown"
    try:
        plan = plan_cast(template, name, commit=commit)
    except CastError as exc:
        print(f"cast: {exc}", file=sys.stderr)
        return 2
    print(render_plan(plan))
    return 0 if plan.verdict == READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
