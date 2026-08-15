"""CARD: cli -- one door to the whole workshop: the codeforge command.

Installed via [project.scripts] in pyproject.toml, so the venv grows
real commands: `codeforge <verb>` for operations, and `spark` -- the
one-word world igniter, named for the plaque on the anvil.

Handlers import lazily: `codeforge grant` should not have to load
the entire world to edit one archive casefile.
"""

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

USAGE = """codeforge -- hardware-store counter for the world engine

  spark                                ignite the multiplayer server
  codeforge serve                      same thing, formal attire
  codeforge play                       solo terminal session
  codeforge play --seed <game>         boot a different game (see: codeforge seeds)
  codeforge onboard                    run the onboarding workflow (same engine as the game quest)
  codeforge journey --region R --waypoints a,b,c   generate + prove a playable journey region
  codeforge host --region R --waypoints a,b,c      install a journey as a bootable World Package
  codeforge seeds                      list installed games (seeds)
  codeforge grant <name> <rank>        host-shell authority (player/wizard/owner)
  codeforge migrate <char> <account>   move a v1 password onto an account
  codeforge migrate-db                 import legacy JSON saves into SQLite
  codeforge passwd <account>           rotate an account password (prompted)
  codeforge refactor <f> <fn> <o> <n>  verifier-gated safe rename (dry-run; --apply to write)
  codeforge seedlab proof             run the SeedLab platform proof and write a report artifact
  codeforge seedlab audit             write the SeedLab module audit artifact
  codeforge api                        serve the HTTP admin API on port 8000
  codeforge web                        serve the browser gate (WebSocket play) on $PORT
  codeforge help                       this text

A seed IS a game. `--seed <game>` (or the FORGE_SEED env var, which `spark` reads)
selects which world the engine boots.
"""


def _seeds_available() -> list[str]:
    """List installed games without importing the world (keeps env-before-import clean)."""
    content_root = Path(__file__).resolve().parent.parent / "content"
    default_blueprints_root = content_root / "blueprints"
    default_seeds_root = content_root / "seeds"
    configured_root = os.environ.get("CODEFORGE_BLUEPRINTS_ROOT")
    if configured_root is None:
        configured_root = os.environ.get("CODEFORGE_SEEDS_ROOT")
    root = Path(
        configured_root
        if configured_root is not None
        else (default_blueprints_root if default_blueprints_root.is_dir() else default_seeds_root)
    )
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if (p / "rooms.yaml").is_file())


def _pop_seed(args: list[str]) -> str | None:
    """Extract Blueprint selection from args, accepting both spellings."""
    selected = None
    for flag in ("--blueprint", "--seed"):
        if flag not in args:
            continue
        i = args.index(flag)
        name = args[i + 1] if i + 1 < len(args) else ""
        del args[i : i + 2]
        if selected is None or flag == "--blueprint":
            selected = name
    return selected


# --- one handler per verb (each lazy-imports its own deps, so `codeforge grant` never loads
# uvicorn or the gateway). The dispatch table below routes to them; main() stays a thin router.
# Each takes the full arg list (verb at args[0]) and returns a process exit code. ---
Command = Callable[[list[str]], int]


def _cmd_seeds(args: list[str]) -> int:
    for name in _seeds_available():
        print(name)
    return 0


def _cmd_serve(args: list[str]) -> int:
    from adapters.gateway import serve

    serve()
    return 0


def _cmd_play(args: list[str]) -> int:
    from forge import game_loop

    game_loop()
    return 0


def _cmd_onboard(args: list[str]) -> int:
    from kernel.onboarding import drive

    drive()  # the Workflow Engine's practical adapter: the same core as the game quest
    return 0


def _cmd_grant(args: list[str]) -> int:
    if len(args) != 3:
        print(USAGE)
        return 1
    from kernel.world.characters import set_rank

    print(set_rank(args[1], args[2]))
    return 0


def _cmd_migrate(args: list[str]) -> int:
    if len(args) != 3:
        print(USAGE)
        return 1
    from kernel.world.accounts import migrate

    print(migrate(args[1], args[2]))
    return 0


def _cmd_api(args: list[str]) -> int:
    import uvicorn

    from adapters.api import app
    from kernel.shelf.config import Settings

    # Honor $PORT like the web command does; Settings types + validates it.
    uvicorn.run(app, host="0.0.0.0", port=Settings.load().port)
    return 0


def _cmd_web(args: list[str]) -> int:
    import uvicorn

    from adapters.web_gateway import app as web_app
    from kernel.shelf.config import Settings

    # Hosts (Render/Fly) hand us the port on $PORT; Settings types + validates it.
    uvicorn.run(web_app, host="0.0.0.0", port=Settings.load().port)
    return 0


def _cmd_migrate_db(args: list[str]) -> int:
    from kernel.world.accounts import import_legacy_json

    print(import_legacy_json())
    return 0


def _cmd_passwd(args: list[str]) -> int:
    if len(args) != 2:
        print(USAGE)
        return 1
    import getpass

    from kernel.world.accounts import rotate_account_secret

    pw = getpass.getpass(f"New password for {args[1]}: ")
    again = getpass.getpass("Type it again: ")
    if pw != again:
        print("Mismatch. Nothing changed.")
        return 1
    # NOTE: CodeQL flags this as clear-text-logging, but it is a confirmed FALSE POSITIVE --
    # rotate_account_secret returns only a status string ("Password rotated for <acct>.", etc.),
    # never the password. CodeQL coarsely taints any return of a function that RECEIVES a password;
    # the alert is dismissed in the UI rather than contorting the code around a broken query.
    print(rotate_account_secret(args[1], pw))
    return 0


def _cmd_refactor(args: list[str]) -> int:
    """Scope-correct, verifier-gated rename of a local/param inside ONE function.

    `codeforge refactor <file> <func> <old> <new> [--apply] [--deep] [--samples N]`

    Dry-run by default: prints a unified diff and the behavioural verdict, writes NOTHING.
    `--apply` writes the file, but ONLY when the rename PRESERVED behaviour -- a refused
    (broken/inconclusive) transform is never written and exits non-zero. Verification EXECUTES
    the target function, so point it at trusted/authorized source only.
    """
    import argparse
    import difflib

    from kernel.refactor import RefactorError, refactor_available, verified_rename

    parser = argparse.ArgumentParser(
        prog="codeforge refactor",
        description="Scope-correct, verifier-gated rename of a local/param inside one function.",
    )
    parser.add_argument("file", help="the .py file to edit")
    parser.add_argument("func", help="the function whose local/param to rename")
    parser.add_argument("old", help="the current local/param name")
    parser.add_argument("new", help="the new name")
    parser.add_argument(
        "--apply", action="store_true", help="write the change (default: dry-run diff preview)"
    )
    parser.add_argument(
        "--deep", action="store_true", help="add the CrossHair deep gate (needs the [verify] extra)"
    )
    parser.add_argument(
        "--samples", type=int, default=200, help="behavioural sample count (default: 200)"
    )
    try:
        ns = parser.parse_args(args[1:])
    except SystemExit as exc:  # argparse exits on -h / bad args; route it through our exit code
        return exc.code if isinstance(exc.code, int) else 2

    if not refactor_available():
        print(
            "the refactor tool needs the optional dependency: "
            "pip install 'codeforge[refactor]' (libcst).",
            file=sys.stderr,
        )
        return 2

    path = Path(ns.file)
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"cannot read {ns.file}: {exc}", file=sys.stderr)
        return 2

    try:
        result = verified_rename(source, ns.func, ns.old, ns.new, samples=ns.samples, deep=ns.deep)
    except RefactorError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    if not result.applied:
        print(
            f"REFUSED -- {ns.old} -> {ns.new} in {ns.func} did not preserve behaviour "
            f"(verdict: {result.verdict})."
        )
        if result.counterexample:
            print(f"  counterexample: {result.counterexample}")
        for note in result.notes:
            print(f"  {note}")
        return 1

    if ns.apply:
        path.write_text(result.source, encoding="utf-8")
        print(f"applied: {ns.old} -> {ns.new} in {ns.func} ({ns.file}); verdict {result.verdict}.")
        return 0

    diff = difflib.unified_diff(
        source.splitlines(keepends=True),
        result.source.splitlines(keepends=True),
        fromfile=f"a/{ns.file}",
        tofile=f"b/{ns.file}",
    )
    sys.stdout.writelines(diff)
    print(f"dry-run: verdict {result.verdict}. Pass --apply to write {ns.file}.")
    return 0


def _cmd_seedlab(args: list[str]) -> int:
    """SeedLab proof and audit commands: repeatable report artifacts for the platform layer."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="codeforge seedlab",
        description="Run SeedLab proofs and audits, writing stable JSON report artifacts.",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    proof = sub.add_parser("proof", help="run the local platform proof and write a report")
    proof.add_argument(
        "--root",
        default=".seedlab/proof",
        help="directory used for the durable proof stores (default: .seedlab/proof)",
    )
    proof.add_argument(
        "--report",
        default="reports/seedlab-platform-proof.json",
        help=(
            "where to write the JSON report artifact (default: reports/seedlab-platform-proof.json)"
        ),
    )
    proof.add_argument(
        "--owner",
        default="josh",
        help="owner recorded on the created Seed (default: josh)",
    )

    audit = sub.add_parser("audit", help="write a SeedLab module audit report")
    audit.add_argument(
        "--report",
        default="reports/seedlab-module-audit.json",
        help="where to write the JSON audit artifact (default: reports/seedlab-module-audit.json)",
    )

    repository = sub.add_parser(
        "repo-proof", help="model a repository read-only and write its durable report"
    )
    repository.add_argument(
        "--source", required=True, help="repository or plain directory to model"
    )
    repository.add_argument(
        "--store",
        default=".seedlab/repository-proof",
        help="directory used for durable repository-proof records",
    )
    repository.add_argument(
        "--report",
        default="reports/seedlab-repository-proof.json",
        help="where to write the JSON report artifact",
    )

    try:
        ns = parser.parse_args(args[1:])
    except SystemExit as exc:
        return int(exc.code or 0)

    from kernel.seedlab.audit import audit_seedlab_modules, render_seedlab_audit
    from kernel.seedlab.platform_proof import run_first_platform_proof
    from kernel.seedlab.repository_proof import model_repository, persist

    if ns.subcommand == "proof":
        result = run_first_platform_proof(Path(ns.root), owner=ns.owner)
        report = result.to_dict()
        report["module_audit"] = audit_seedlab_modules().to_dict()
        report_path = Path(ns.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"proof complete: {result.seed_id}")
        print(f"report written: {report_path}")
        print(result.hub_text)
        return 0

    if ns.subcommand == "repo-proof":
        proof_record = model_repository(Path(ns.source))
        stored = persist(proof_record, Path(ns.store))
        report_path = Path(ns.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps({"repository": proof_record.to_dict(), "stored": str(stored)}, indent=2),
            encoding="utf-8",
        )
        print(f"repository proof complete: {proof_record.source_id}")
        print(f"report written: {report_path}")
        print(
            f"vcs: {proof_record.vcs}, branch: {proof_record.branch}, commit: {proof_record.commit}"
        )
        return 0

    audit_report = audit_seedlab_modules()
    report_path = Path(ns.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(audit_report.to_dict(), indent=2), encoding="utf-8")
    print(render_seedlab_audit(audit_report))
    print(f"audit written: {report_path}")
    return 0


def _cmd_journey(args: list[str]) -> int:
    """Generate, link, and PROVE a waypoint-journey game region end to end: the whole pipeline
    (Form-grade intent -> generate -> link -> operate -> recover) as one real operation. Writes
    playable seed content to `--dest` and reports whether a live player can travel it and it
    survives a restart. No decorative rooms: the command performs the real operation."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="codeforge journey",
        description="Generate a waypoint journey, write it as seed content, and prove it plays.",
    )
    parser.add_argument("--region", required=True, help="the region name")
    parser.add_argument(
        "--waypoints", required=True, help="comma-separated snake_case room labels, in order"
    )
    parser.add_argument("--dest", default="journey_out", help="where to write the seed content")
    try:
        ns = parser.parse_args(args[1:])
    except SystemExit as exc:  # argparse exits on -h / bad args; route it through our exit code
        return int(exc.code or 0)

    from kernel.domains.game_session import RESUMED, operate_and_recover
    from kernel.domains.journey import JourneyError, journey_region

    waypoints = [w.strip() for w in ns.waypoints.split(",") if w.strip()]
    try:
        spec = journey_region(ns.region, waypoints)
    except JourneyError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    dest = Path(ns.dest)
    report = operate_and_recover(spec, dest)
    if report.verdict == RESUMED:
        print(
            f"RESUMED: '{report.region}' -- {len(waypoints)} waypoint(s); "
            f"quest '{report.quest_id}' reaches '{report.terminal}'."
        )
        print(f"  playable seed content written to {dest}")
        return 0
    print(f"{report.verdict.upper()}: {report.detail}", file=sys.stderr)
    return 1


def _cmd_host(args: list[str]) -> int:
    """Install a generated journey region as a bootable World Package the server can serve:
    generate -> link -> install (rooms + quest + a `world.yaml` MANIFEST) under
    `<seed-root>/content/blueprints/<name>/`, validated through the engine's OWN manifest gate.
    Prints
    HOSTABLE and how to boot it. No decorative rooms: the command performs the real install, so a
    default `--seed-root .` writes into the live seed directory the server reads."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="codeforge host",
        description="Generate a journey region and install it as a bootable World Package (seed).",
    )
    parser.add_argument("--region", required=True, help="the region name (slugged to the seed id)")
    parser.add_argument(
        "--waypoints", required=True, help="comma-separated snake_case room labels, in order"
    )
    parser.add_argument(
        "--blueprint-root",
        "--seed-root",
        dest="seed_root",
        default=".",
        help="repo root holding content/blueprints/ (default: cwd)",
    )
    parser.add_argument("--name", default="", help="override the seed name (default: region slug)")
    parser.add_argument("--title", default="", help="override the world title (default: from name)")
    parser.add_argument(
        "--verify-recovery",
        action="store_true",
        help="after install, prove the seed survives backup + restore (loss + restart)",
    )
    try:
        ns = parser.parse_args(args[1:])
    except SystemExit as exc:  # argparse exits on -h / bad args; route it through our exit code
        return int(exc.code or 0)

    from kernel.domains.hosted_world import HOSTABLE, HostedWorldError, install_world
    from kernel.domains.journey import JourneyError, journey_region

    seed_root = Path(ns.seed_root)
    waypoints = [w.strip() for w in ns.waypoints.split(",") if w.strip()]
    try:
        spec = journey_region(ns.region, waypoints)
        world = install_world(spec, seed_root, seed_name=ns.name, title=ns.title)
    except (JourneyError, HostedWorldError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    if world.verdict != HOSTABLE:
        print(f"{world.verdict.upper()}: {'; '.join(world.problems)}", file=sys.stderr)
        return 1

    print(f"HOSTABLE: '{world.seed_name}' installed at {world.seed_dir}")
    print(f"  spawn: {world.start_room};  boot: codeforge play --seed {world.seed_name}")

    if ns.verify_recovery:
        # Prove the seed the server hosts is RESTORABLE: back up the installed package and restore
        # + verify it (byte-identical AND identity re-validated through the engine's own gates). The
        # seed is already installed, so compose the two primitives on the live artifact -- no
        # redundant re-install. A failed proof fails the command loud (never a false success).
        from kernel.domains.game_lifecycle import RECOVERED
        from kernel.domains.hosted_recovery import snapshot_seed, verify_seed_recovery

        report = verify_seed_recovery(
            world.seed_name, seed_root, snapshot_seed(Path(world.seed_dir))
        )
        if report.verdict != RECOVERED:
            print(f"  {report.verdict.upper()}: {report.detail}", file=sys.stderr)
            return 1
        n = len(report.files)
        print(f"  RECOVERED: {n} file(s) survive backup + restore; identity re-validated")

    return 0


# Verb -> handler. The strings are the frozen public CLI surface; order is display order only.
_DISPATCH: dict[str, Command] = {
    "seeds": _cmd_seeds,
    "serve": _cmd_serve,
    "play": _cmd_play,
    "onboard": _cmd_onboard,
    "journey": _cmd_journey,
    "host": _cmd_host,
    "grant": _cmd_grant,
    "migrate": _cmd_migrate,
    "api": _cmd_api,
    "web": _cmd_web,
    "migrate-db": _cmd_migrate_db,
    "passwd": _cmd_passwd,
    "refactor": _cmd_refactor,
    "seedlab": _cmd_seedlab,
}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:]) if argv is None else list(argv)

    # Seed selection must set the env BEFORE any world module is imported, since
    # SEED_DIR binds at import time (the proving ground picks its program at power-on).
    blueprint_flag = "--blueprint" in args
    seed = _pop_seed(args)
    if seed is not None:
        if seed not in _seeds_available():
            print(
                f"Unknown seed '{seed}'. Installed: {', '.join(_seeds_available()) or '(none)'}",
                file=sys.stderr,
            )
            return 2
        os.environ["FORGE_BLUEPRINT" if blueprint_flag else "FORGE_SEED"] = seed

    cmd = args[0] if args else "serve"
    handler = _DISPATCH.get(cmd)
    if handler is None:
        print(USAGE)
        return 0 if cmd in ("help", "-h", "--help") else 1
    return handler(args)


def spark() -> None:
    """Every world begins as one."""
    from adapters.gateway import serve

    serve()
