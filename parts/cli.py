"""CARD: cli -- one door to the whole workshop: the codeforge command.

Installed via [project.scripts] in pyproject.toml, so the venv grows
real commands: `codeforge <verb>` for operations, and `spark` -- the
one-word world igniter, named for the plaque on the anvil.

Handlers import lazily: `codeforge grant` should not have to load
the entire world to edit one record.
"""

import sys

USAGE = """codeforge -- the world engine

  spark                                ignite the multiplayer server
  codeforge serve                      same thing, formal attire
  codeforge play                       solo terminal session
  codeforge grant <name> <rank>        host-shell authority (player/wizard/owner)
  codeforge migrate <char> <account>   move a v1 password onto an account
  codeforge migrate-db                 import legacy JSON saves into SQLite
  codeforge passwd <account>           rotate an account password (prompted)
  codeforge help                       this text
"""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:]) if argv is None else list(argv)
    cmd = args[0] if args else "serve"

    if cmd == "serve":
        from parts.gateway import serve

        serve()
        return 0
    if cmd == "play":
        from forge import game_loop

        game_loop()
        return 0
    if cmd == "grant" and len(args) == 3:
        from parts.characters import set_rank

        print(set_rank(args[1], args[2]))
        return 0
    if cmd == "migrate" and len(args) == 3:
        from parts.accounts import migrate

        print(migrate(args[1], args[2]))
        return 0
    if cmd == "migrate-db":
        from parts.accounts import import_legacy_json

        print(import_legacy_json())
        return 0
    if cmd == "passwd" and len(args) == 2:
        import getpass

        from parts.accounts import set_account_password

        pw = getpass.getpass(f"New password for {args[1]}: ")
        again = getpass.getpass("Type it again: ")
        if pw != again:
            print("Mismatch. Nothing changed.")
            return 1
        print(set_account_password(args[1], pw))
        return 0
    print(USAGE)
    return 0 if cmd in ("help", "-h", "--help") else 1


def spark() -> None:
    """Every world begins as one."""
    from parts.gateway import serve

    serve()
