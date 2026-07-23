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
# uvicorn or the gateway). The dispatch table below routes to them; main() stays a thin router. ---
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
    from parts.onboarding import drive

    drive()  # the Workflow Engine's practical adapter: the same core as the game quest
    return 0


def _cmd_grant(args: list[str]) -> int:
    if len(args) != 3:
        print(USAGE)
        return 1
    from parts.characters import set_rank

    print(set_rank(args[1], args[2]))
    return 0


def _cmd_migrate(args: list[str]) -> int:
    if len(args) != 3:
        print(USAGE)
        return 1
    from parts.accounts import migrate

    print(migrate(args[1], args[2]))
    return 0


def _cmd_api(args: list[str]) -> int:
    import uvicorn

    from parts.api import app
    from parts.shelf.config import Settings

    # Honor $PORT like the web command does; Settings types + validates it.
    uvicorn.run(app, host="0.0.0.0", port=Settings.load().port)
    return 0


def _cmd_web(args: list[str]) -> int:
    import uvicorn

    from parts.shelf.config import Settings
    from parts.web_gateway import app as web_app

    # Hosts (Render/Fly) hand us the port on $PORT; Settings types + validates it.
    uvicorn.run(web_app, host="0.0.0.0", port=Settings.load().port)
    return 0


def _cmd_migrate_db(args: list[str]) -> int:
    from parts.accounts import import_legacy_json

    print(import_legacy_json())
    return 0


def _cmd_passwd(args: list[str]) -> int:
    if len(args) != 2:
        print(USAGE)
        return 1
    import getpass

    from parts.accounts import rotate_account_secret

    pw = getpass.getpass(f"New password for {args[1]}: ")
    again = getpass.getpass("Type it again: ")
    if pw != again:
        print("Mismatch. Nothing changed.")
        return 1
    # NOTE: CodeQL flags this as clear-text-logging, but it is a confirmed FALSE POSITIVE --
    # rotate_account_secret returns only a status string ("Password rotated for <acct>.", etc.),
    # never the password. CodeQL coarsely taints any return of a function that RECEIVES a password;
    # three refactors (helper, outcome-code, inline literals) all still tripped it, so the alert is
    # dismissed in the UI rather than contorting the code around a broken query.
    print(rotate_account_secret(args[1], pw))
    return 0


# Verb -> handler. The strings are the frozen public CLI surface; order is display order only.
_COMMANDS: dict[str, Command] = {
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

    cmd = args[0] if args else "serve"  # bare `codeforge` boots the server
    handler = _COMMANDS.get(cmd)
    if handler is not None:
        return handler(args)
    print(USAGE)
    return 0 if cmd in ("help", "-h", "--help") else 1


def spark() -> None:
    """Every world begins as one."""
    from parts.gateway import serve

    serve()
