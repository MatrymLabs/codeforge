"""CARD: cli -- one door to the whole workshop: the codeforge command.

Installed via [project.scripts] in pyproject.toml, so the venv grows
real commands: `codeforge <verb>` for operations, and `spark` -- the
one-word world igniter, named for the plaque on the anvil.

Handlers import lazily: `codeforge grant` should not have to load
the entire world to edit one archive casefile.
"""

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
  codeforge seeds                      list installed games (seeds)
  codeforge grant <name> <rank>        host-shell authority (player/wizard/owner)
  codeforge migrate <char> <account>   move a v1 password onto an account
  codeforge migrate-db                 import legacy JSON saves into SQLite
  codeforge passwd <account>           rotate an account password (prompted)
  codeforge refactor <f> <fn> <o> <n>  verifier-gated safe rename (dry-run; --apply to write)
  codeforge api                        serve the HTTP admin API on port 8000
  codeforge web                        serve the browser gate (WebSocket play) on $PORT
  codeforge help                       this text

A seed IS a game. `--seed <game>` (or the FORGE_SEED env var, which `spark` reads)
selects which world the engine boots.
"""


def _seeds_available() -> list[str]:
    """List installed games without importing the world (keeps env-before-import clean)."""
    root = Path(__file__).resolve().parent.parent / "seeds"
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if (p / "rooms.yaml").is_file())


def _pop_seed(args: list[str]) -> str | None:
    """Extract `--seed <name>` from args (mutates in place). Returns the name or None."""
    if "--seed" not in args:
        return None
    i = args.index("--seed")
    name = args[i + 1] if i + 1 < len(args) else ""
    del args[i : i + 2]
    return name


# --- one handler per verb (each lazy-imports its own deps, so `codeforge grant` never loads
# uvicorn or the gateway). The dispatch table below routes to them; main() stays a thin router.
# Each takes the full arg list (verb at args[0]) and returns a process exit code. ---
Command = Callable[[list[str]], int]


def _cmd_seeds(args: list[str]) -> int:
    for name in _seeds_available():
        print(name)
    return 0


def _cmd_serve(args: list[str]) -> int:
    from parts.gateway import serve

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
    from parts.world.characters import set_rank

    print(set_rank(args[1], args[2]))
    return 0


def _cmd_migrate(args: list[str]) -> int:
    if len(args) != 3:
        print(USAGE)
        return 1
    from parts.world.accounts import migrate

    print(migrate(args[1], args[2]))
    return 0


def _cmd_api(args: list[str]) -> int:
    import uvicorn

    from kernel.shelf.config import Settings
    from parts.api import app

    # Honor $PORT like the web command does; Settings types + validates it.
    uvicorn.run(app, host="0.0.0.0", port=Settings.load().port)
    return 0


def _cmd_web(args: list[str]) -> int:
    import uvicorn

    from kernel.shelf.config import Settings
    from parts.web_gateway import app as web_app

    # Hosts (Render/Fly) hand us the port on $PORT; Settings types + validates it.
    uvicorn.run(web_app, host="0.0.0.0", port=Settings.load().port)
    return 0


def _cmd_migrate_db(args: list[str]) -> int:
    from parts.world.accounts import import_legacy_json

    print(import_legacy_json())
    return 0


def _cmd_passwd(args: list[str]) -> int:
    if len(args) != 2:
        print(USAGE)
        return 1
    import getpass

    from parts.world.accounts import rotate_account_secret

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


# Verb -> handler. The strings are the frozen public CLI surface; order is display order only.
_DISPATCH: dict[str, Command] = {
    "seeds": _cmd_seeds,
    "serve": _cmd_serve,
    "play": _cmd_play,
    "onboard": _cmd_onboard,
    "grant": _cmd_grant,
    "migrate": _cmd_migrate,
    "api": _cmd_api,
    "web": _cmd_web,
    "migrate-db": _cmd_migrate_db,
    "passwd": _cmd_passwd,
    "refactor": _cmd_refactor,
}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:]) if argv is None else list(argv)

    # Seed selection must set the env BEFORE any world module is imported, since
    # SEED_DIR binds at import time (the proving ground picks its program at power-on).
    seed = _pop_seed(args)
    if seed is not None:
        if seed not in _seeds_available():
            print(
                f"Unknown seed '{seed}'. Installed: {', '.join(_seeds_available()) or '(none)'}",
                file=sys.stderr,
            )
            return 2
        os.environ["FORGE_SEED"] = seed

    cmd = args[0] if args else "serve"
    handler = _DISPATCH.get(cmd)
    if handler is None:
        print(USAGE)
        return 0 if cmd in ("help", "-h", "--help") else 1
    return handler(args)


def spark() -> None:
    """Every world begins as one."""
    from parts.gateway import serve

    serve()
