"""CARD: cast -- forge a standalone game project (a "cast") from a seed pack + the engine.

A seed PACK is a game's content (`seeds/<name>/*.yaml`). A CAST is what leaves the forge:
a standalone, installable project poured from the engine + one chosen seed pack + config.

The pipeline: `plan_cast` (dry run, writes nothing) -> `generate_cast` (POURS the engine + the
cast's own seed + scaffold + a `generated` manifest with real deps declared; proof a package
assembles) -> `validate_cast` (boots the cast and runs a command corpus; proof it RUNS) ->
`install_check` (a clean venv + only the cast's declared deps + boot; proof it runs in dependency
ISOLATION). `pour_selective` (detachment D2) vendors ONLY the target surfaces' module closure
(`vendored-selective`) and proves the cut with the BROAD harness (every surface command must run),
so a slimmer game carries none of the engineering stack. Two honesty rules hold the line:

  1. `engine_strategy` is `vendored-whole` by default; `vendored-selective` is offered ONLY behind
     the broad validation harness that proves every surface command still runs on the cut. Never a
     false a-la-carte module list; a claim of a cut is made only when the harness passes.
  2. It never touches `seeds/`, `--seed`, or `FORGE_SEED` -- it READS a seed pack and would
     WRITE a new cast elsewhere. The frozen identifiers stay frozen.

See docs/seed_architecture.md for the full doctrine (seed pack vs cast, the phased plan).
"""

from __future__ import annotations

import json
import shutil
import subprocess  # nosec B404 -- fixed argv, no shell; used only to smoke-boot a poured cast
import sys
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_ROOT = _ROOT / "seed_templates"
SEEDS_ROOT = _ROOT / "seeds"

PLANNED = "planned"
READY = "ready"
BLOCKED = "blocked"
GENERATED = "generated"  # poured to disk (Phase 2), not yet booted
VALIDATED = "validated"  # poured AND smoke-booted (boots + ticks in the current environment)
NOT_VALIDATED = "not_validated"  # poured but failed its smoke boot
VENDORED_WHOLE = "vendored-whole"  # the cast carries every parts/ module (default, honest interim)
VENDORED_SELECTIVE = "vendored-selective"  # the cast carries only its surfaces' module closure (D2)

# What a generated cast ignores at runtime - the same categories a cast must never carry.
_CAST_GITIGNORE = (
    "# A CodeForge cast. Runtime state, secrets, and caches never live in the repo.\n"
    "*.db\nsave.json\ncharacters.json\naccounts.json\n*.kdbx\n"
    ".env\n.venv/\n__pycache__/\n*.pyc\nreports/\nsecurity-evidence/\n"
)

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
    status: str = PLANNED  # planned | generated | validated | not_validated | detached
    detached: bool = False
    isolation_proven: bool = False  # booted in a fresh venv with only its own declared deps
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
        f"Cast plan - {plan.cast_name} (from template '{plan.template}')",
        "",
        f"  seed_id         {m.seed_id}",
        f"  starter pack    {m.starter_seed_pack}",
        f"  engine strategy {m.engine_strategy}",
        f"  status          {m.status}  (dry run - nothing written)",
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
        f"{glyph} {plan.verdict.upper()} - "
        + (
            "this cast could be poured (generation lands in a later phase)."
            if plan.verdict == READY
            else "resolve the blocker(s) above before this cast can be poured."
        ),
    ]
    return "\n".join(lines)


def _scaffold_readme(m: CastManifest) -> str:
    return (
        f"# {m.seed_name}\n\n"
        f"A standalone game **cast** poured from CodeForge (`{m.template}` template) with the "
        f"`{m.starter_seed_pack}` seed pack as its world.\n\n"
        f"- Engine strategy: `{m.engine_strategy}` (the engine is vendored whole).\n"
        f"- Poured at CodeForge commit `{m.codeforge_commit}`.\n\n"
        "## Honest status\n"
        f"This cast is **{m.status}**: the directory is assembled (engine + seed + config).\n"
        "It is NOT yet detached or proven to boot on its own - that is a later CodeForge phase.\n"
        "See `cast_manifest.json` for the full provenance and known limitations.\n"
    )


def _scaffold_seed_toml(m: CastManifest) -> str:
    return (
        "# The world this cast runs. The seed pack under seeds/ is the game's content.\n"
        "[world]\n"
        f'seed_pack = "{m.starter_seed_pack}"\n'
        f'name = "{m.seed_name}"\n'
    )


def _engine_runtime_deps(base: Path) -> tuple[list[str], str]:
    """The engine's runtime deps + requires-python, read from the source pyproject so a cast's deps
    track the engine's. Falls back to a safe minimum if the file is absent (e.g. a test fixture)."""
    fallback = (["pyyaml", "sqlalchemy", "pydantic"], ">=3.11")
    pyproject = base / "pyproject.toml"
    if not pyproject.is_file():
        return fallback
    import tomllib

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return fallback
    proj = data.get("project", {})
    deps = [str(d) for d in proj.get("dependencies", [])] or fallback[0]
    return deps, str(proj.get("requires-python", fallback[1]))


def _scaffold_pyproject(m: CastManifest, deps: list[str], requires_python: str) -> str:
    slug = m.seed_name.lower().replace(" ", "-") or "cast"
    dep_lines = "".join(f'    "{d}",\n' for d in deps)
    return (
        "[project]\n"
        f'name = "{slug}"\n'
        'version = "0.1.0"\n'
        f'description = "A CodeForge cast: {m.seed_name}"\n'
        f'requires-python = "{requires_python}"\n'
        "dependencies = [\n"
        f"{dep_lines}"
        "]\n"
    )


def _vendor_selective(parts_src: Path, parts_dest: Path, modules: set[str], ignore: object) -> None:
    """Copy only the named top-level modules (a file `<m>.py` or a subpackage dir `<m>/`), plus the
    always-required `__init__.py`. The engine's remaining modules are left out (detachment D2)."""
    parts_dest.mkdir(parents=True)
    shutil.copy2(parts_src / "__init__.py", parts_dest / "__init__.py")
    for m in sorted(modules):
        as_file, as_dir = parts_src / f"{m}.py", parts_src / m
        if as_file.is_file():
            shutil.copy2(as_file, parts_dest / f"{m}.py")
        elif as_dir.is_dir():
            shutil.copytree(as_dir, parts_dest / m, ignore=ignore)  # type: ignore[arg-type]


def generate_cast(
    plan: CastPlan, dest: Path, *, modules: set[str] | None = None, root: Path | None = None
) -> Path:
    """Phase 2: pour a planned cast to `dest` - vendor the engine (whole by default, or SELECTIVELY
    when `modules` names the closure to carry, D2), copy the cast's OWN seed pack, and write the
    scaffold + a `generated` manifest. Returns the cast root.

    Honest scope: this ASSEMBLES a standalone project directory. A selective vendor is only SAFE
    when a broad harness confirms it (run every surface command against the cut) - the caller does
    that; this just pours what it is told. Refuses a BLOCKED plan or a non-empty destination; never
    touches `seeds/` or the frozen identifiers.
    """
    if plan.verdict != READY:
        raise CastError(
            f"cannot generate a {plan.verdict.upper()} cast: resolve the blocker(s) first"
        )
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise CastError(f"destination {dest} is not empty; refusing to overwrite a cast")
    base = root or _ROOT
    starter = plan.manifest.starter_seed_pack
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    dest.mkdir(parents=True, exist_ok=True)
    # 1. the engine: vendored WHOLE by default, or SELECTIVELY when a module closure is given (D2)
    if modules is None:
        shutil.copytree(base / "parts", dest / "parts", ignore=ignore)
        strategy = VENDORED_WHOLE
    else:
        _vendor_selective(base / "parts", dest / "parts", modules, ignore)
        strategy = VENDORED_SELECTIVE
    shutil.copy2(base / "forge.py", dest / "forge.py")
    # 2. only this cast's OWN seed pack (never the other games)
    shutil.copytree(base / "seeds" / starter, dest / "seeds" / starter, ignore=ignore)
    # 3. the fresh scaffold + the manifest, marked generated
    generated = replace(plan.manifest, status=GENERATED, engine_strategy=strategy)
    deps, requires_python = _engine_runtime_deps(base)  # the cast declares the engine's real deps
    write_manifest(generated, dest / "cast_manifest.json")
    (dest / "README.md").write_text(_scaffold_readme(generated), encoding="utf-8")
    (dest / "seed.toml").write_text(_scaffold_seed_toml(generated), encoding="utf-8")
    (dest / "pyproject.toml").write_text(
        _scaffold_pyproject(generated, deps, requires_python), encoding="utf-8"
    )
    (dest / ".gitignore").write_text(_CAST_GITIGNORE, encoding="utf-8")
    return dest


# The one-command smoke boot install_check runs (import the cast's OWN engine and drive one tick).
_BOOT_PROBE = (
    "import forge; from parts.session import Session; "
    "out = forge.handle_command(Session(player_id='_validate'), 'help'); "
    "print(out[:60]); assert out.strip()"
)

# The broad-harness probe validate_cast runs: boot, then drive EVERY given command, failing loud on
# the first that raises (a missing module in a selective cast surfaces here) or a non-string return.
_VALIDATE_PROBE = r"""
import sys, json
import forge
from parts.session import Session
from parts.world import START_ROOM
s = Session(player_id="_validate", location=START_ROOM)
commands = json.loads(sys.argv[1])
for cmd in commands:
    try:
        out = forge.handle_command(s, cmd)
    except Exception as e:
        print("COMMAND FAILED: %r -> %s: %s" % (cmd, type(e).__name__, e))
        sys.exit(3)
    if not isinstance(out, str):
        print("COMMAND RETURNED NON-STRING: %r" % cmd)
        sys.exit(4)
print("OK: %d commands ran clean" % len(commands))
"""


def validate_cast(
    cast_dir: Path, *, commands: list[str] | None = None, timeout: float = 120.0
) -> tuple[bool, str]:
    """Boot a poured cast and run a command corpus against it, proving it RUNS - a subprocess with
    cwd=`cast_dir`, so `parts/seed.py` resolves the cast's own seed. `commands` defaults to a single
    tick (`help`); for a SELECTIVE cast, pass the full surface corpus so a wrongly-excluded module
    fails loud (the broad harness that makes D2 safe). Records `validated` | `not_validated`.

    Honest scope: proves the cast boots + runs in the CURRENT environment; `install_check` is the
    dependency-isolated fresh-install proof.
    """
    corpus = commands if commands is not None else ["help"]
    try:
        result = subprocess.run(  # nosec B603 -- fixed argv, no shell; boots the poured cast
            [sys.executable, "-c", _VALIDATE_PROBE, json.dumps(corpus)],
            cwd=cast_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        ok = result.returncode == 0 and bool(result.stdout.strip())
        detail = (
            result.stdout.strip()
            if ok
            else ((result.stdout.strip() + " " + result.stderr.strip())[-200:] or "no output")
        )
    except subprocess.TimeoutExpired:
        ok, detail = False, f"cast did not run the corpus within {timeout:.0f}s"
    manifest_path = cast_dir / "cast_manifest.json"
    if manifest_path.is_file():
        m = read_manifest(manifest_path)
        write_manifest(replace(m, status=VALIDATED if ok else NOT_VALIDATED), manifest_path)
    return ok, detail


def _declared_deps(pyproject_path: Path) -> list[str]:
    """The dependencies a generated cast declares in its pyproject (empty if none/unreadable)."""
    if not pyproject_path.is_file():
        return []
    import tomllib

    try:
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []
    return [str(d) for d in data.get("project", {}).get("dependencies", [])]


def _real_runner(cmd: list[str], cwd: Path | None) -> tuple[int, str]:
    """Default step runner for install_check: run one command, return (returncode, combined out)."""
    proc = subprocess.run(  # nosec B603 -- fixed argv, no shell; venv + pip + boot only
        cmd, cwd=cwd, capture_output=True, text=True, check=False
    )
    return proc.returncode, (proc.stdout + proc.stderr)


def _mark_isolation(cast_dir: Path, proven: bool) -> None:
    manifest_path = cast_dir / "cast_manifest.json"
    if manifest_path.is_file():
        write_manifest(
            replace(read_manifest(manifest_path), isolation_proven=proven), manifest_path
        )


def install_check(cast_dir: Path, workdir: Path, *, runner=None) -> tuple[bool, str]:
    """Fresh-install proof: create a clean venv under `workdir`, install ONLY the cast's declared
    deps into it, and boot the cast with that venv - so the cast runs with no dependency on
    CodeForge's environment. Records manifest `isolation_proven`; returns `(ok, detail)`.

    `runner(cmd, cwd) -> (returncode, output)` is a seam (default: real subprocess), so a test can
    exercise the orchestration without touching the network or pip. The real run needs network.
    """
    run = runner or _real_runner
    cast_dir, workdir = Path(cast_dir), Path(workdir)
    deps = _declared_deps(cast_dir / "pyproject.toml")
    if not deps:
        return False, "the cast declares no dependencies to install"
    venv = workdir / "venv"
    py = venv / "bin" / "python"
    pip = venv / "bin" / "pip"
    steps: list[tuple[list[str], Path | None]] = [
        ([sys.executable, "-m", "venv", str(venv)], None),
        ([str(pip), "install", "--quiet", *deps], None),
        ([str(py), "-c", _BOOT_PROBE], cast_dir),
    ]
    for cmd, cwd in steps:
        rc, out = run(cmd, cwd)
        if rc != 0:
            _mark_isolation(cast_dir, False)
            return (
                False,
                f"'{cmd[1] if len(cmd) > 1 else cmd[0]}' step failed: {out.strip()[-200:]}",
            )
    _mark_isolation(cast_dir, True)
    return True, "booted in a fresh venv with only its declared deps"


def pour_selective(
    template: str,
    name: str,
    dest: Path,
    surfaces: list[str],
    *,
    commit: str = "unknown",
    root: Path | None = None,
    tracer=None,
) -> tuple[Path, bool, str]:
    """Detachment D2: compute the surfaces' module closure, pour a SELECTIVE cast carrying only it,
    and validate with the BROAD harness (every surface command). Returns (cast_dir, ok, detail).

    The harness is what makes selective vendoring safe: if the closure wrongly excluded a module a
    surface command needs, that command fails loud here and the cast is marked not_validated. A
    `not_validated` selective cast means the closure was insufficient - widen the surface corpus or
    fall back to a vendored-whole cast; never ship the broken cut.
    """
    from parts import coupling

    plan = plan_cast(template, name, commit=commit, root=root)
    if plan.verdict != READY:
        raise CastError(f"cannot pour a {plan.verdict.upper()} cast: resolve the blocker(s) first")
    modules = coupling.closure(surfaces, tracer=tracer)
    out = generate_cast(plan, Path(dest), modules=modules, root=root)
    ok, detail = validate_cast(out, commands=coupling.surface_commands(surfaces))
    return out, ok, detail


def main(argv: list[str] | None = None) -> int:
    """CLI. Plan a cast (`<template> <name> [commit]`, `make cast-plan`) or pour one
    (`generate <template> <name> <dest> [commit]`, `make cast`).

    Plan writes nothing (exit 0 READY, 1 BLOCKED). Generate pours a standalone project to <dest>.
    """
    import sys

    args = argv if argv is not None else sys.argv[1:]
    if args and args[0] == "generate":
        if len(args) < 4:
            print(
                "usage: python -m parts.cast generate <template> <name> <dest> [commit]",
                file=sys.stderr,
            )
            return 2
        template, name, dest = args[1], args[2], args[3]
        commit = args[4] if len(args) > 4 else "unknown"
        try:
            plan = plan_cast(template, name, commit=commit)
            if plan.verdict != READY:
                print(render_plan(plan))
                return 1
            out = generate_cast(plan, Path(dest))
        except CastError as exc:
            print(f"cast: {exc}", file=sys.stderr)
            return 2
        print(f"poured cast '{name}' -> {out}")
        ok, detail = validate_cast(out)  # prove it runs, not just assembles
        print(f"  {'validated (boots + ticks): ' + detail if ok else 'NOT validated: ' + detail}")
        return 0 if ok else 1
    if args and args[0] == "generate-selective":
        if len(args) < 5:
            print(
                "usage: python -m parts.cast generate-selective <template> <name> <dest> "
                "<surfaces-csv> [commit]",
                file=sys.stderr,
            )
            return 2
        template, name, dest, surfaces_csv = args[1], args[2], args[3], args[4]
        commit = args[5] if len(args) > 5 else "unknown"
        surfaces = [s.strip() for s in surfaces_csv.split(",") if s.strip()]
        from parts.coupling import CouplingError

        try:
            out, ok, detail = pour_selective(template, name, Path(dest), surfaces, commit=commit)
        except (CastError, CouplingError) as exc:
            print(f"cast: {exc}", file=sys.stderr)
            return 2
        strat = read_manifest(out / "cast_manifest.json").engine_strategy
        print(f"poured cast '{name}' ({', '.join(surfaces)}, {strat}) -> {out}")
        verdict = f"validated: {detail}" if ok else f"NOT validated: {detail}"
        print(f"  {verdict}")
        return 0 if ok else 1
    if args and args[0] == "validate":
        if len(args) < 2:
            print("usage: python -m parts.cast validate <cast-dir>", file=sys.stderr)
            return 2
        ok, detail = validate_cast(Path(args[1]))
        print(f"cast validate: {'OK - ' if ok else 'FAILED - '}{detail}")
        return 0 if ok else 1
    if args and args[0] == "install-check":
        if len(args) < 3:
            print("usage: python -m parts.cast install-check <cast-dir> <workdir>", file=sys.stderr)
            return 2
        ok, detail = install_check(Path(args[1]), Path(args[2]))
        print(f"cast install-check: {'OK - ' if ok else 'FAILED - '}{detail}")
        return 0 if ok else 1
    if len(args) < 2:
        print("usage: python -m parts.cast <template> <name> [commit]", file=sys.stderr)
        print(
            "       python -m parts.cast generate <template> <name> <dest> [commit]",
            file=sys.stderr,
        )
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
