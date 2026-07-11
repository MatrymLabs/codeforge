# Running CodeForge - start the servers, log into The First Forge

This is the operator's guide: how to ignite the engine, the three doors into a
world, and a first walk through **The First Forge** (the default game). Every
command here is copy-paste runnable from the repo root.

> **A seed is a game.** The engine boots one *seed pack* - a whole world of
> rooms, items, NPCs, callings, and a splash screen. The default seed is
> `first-forge`. Swap the seed (`--seed` or `FORGE_SEED`) and the same engine
> becomes a different game. This guide uses the default; everything applies to
> any seed.

---

## 0. One-time setup

```bash
git clone git@github.com:MatrymLabs/codeforge.git
cd codeforge
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make check          # lint + mypy + tests - prove the engine is sound before you run it
```

`make check` must be green. If it isn't, stop - a red gate means the code you're
about to run is broken, not that you should run it anyway.

Re-activate the venv (`source .venv/bin/activate`) in every new shell before the
commands below. The console scripts `spark` and `codeforge` only exist on your
PATH while the venv is active.

---

## 1. Three doors into a world

CodeForge runs three ways. Pick by what you want to do.

| Door | Command | What it is | Who connects |
|---|---|---|---|
| **Solo** | `codeforge play` | A single-player terminal loop. No network, no login. | Just you, in this terminal. |
| **Multiplayer** | `spark` | The threaded TCP gateway on port **4000**. Real MUD server. | Anyone with `nc`/telnet/Mudlet to your host. |
| **Container** | `docker run …` | The same gateway, packaged. | Same as multiplayer, but isolated. |

There is also a fourth, separate server - the **HTTP admin API** (`codeforge api`,
port 8000) - covered in §6. It is not how players log in.

### 1a. Solo (fastest - no server, no account)

```bash
codeforge play                          # boot the default game, first-forge
codeforge play --seed spiral-ascent  # boot a different game
codeforge seeds                         # list every installed game first
```

You spawn straight into the world's first room. Skip to §4 for the walkthrough -
solo play has no front desk.

### 1b. Multiplayer gateway (the real server)

```bash
spark                     # ignite the server on 0.0.0.0:4000 (default game)
# or, same thing:
codeforge serve
# boot a different game on the server:
FORGE_SEED=spiral-ascent spark
```

You'll see:

```text
CodeForge gateway listening on 0.0.0.0:4000
Connect with:  nc <this-machine> 4000   (or any telnet client)
Press Ctrl+C to shut down.
```

Leave it running. Open a **second terminal** (or another machine on the network)
to connect - see §2.

### 1c. Container (the shipped image)

```bash
docker build -t codeforge .                        # build once
docker run -p 4000:4000 -v codeforge_data:/data codeforge
# boot a different game:
docker run -p 4000:4000 -e FORGE_SEED=spiral-ascent codeforge
```

The `-v codeforge_data:/data` volume carries the database (accounts, characters)
across container restarts. The container runs as a non-root user and stores state
at `/data/codeforge.db`.

---

## 1½. ⚒ The ritual - one command for all of it

For the daily "bring everything online" moment, there's a single command that
lights the whole workshop in sequence:

```bash
make ritual          # or, once bound as a phrase:  start the ritual
```

Four stages light up in order:

1. **Ignition** - the gates run (`make check`: lint · types · tests). A red gate
   **stops the ritual** - the forge never lights on broken code.
2. **Mirror** - syncs with GitHub: fast-forwards your branch if it's behind,
   names any unpushed commits. It never force-syncs and never auto-pushes a dirty
   tree.
3. **The Forge** - lights the gateway on :4000 and waits until the socket is
   truly accepting connections. If a forge is *already* burning on :4000, the
   ritual joins it instead of starting a second one.
4. **The Gate** - opens the MUD window at the front desk, ready to log in. It
   connects with a bundled stdlib client (`scripts/mud_client.py`) that honors
   the password blackout even where `telnet` isn't installed - so your password
   stays hidden. (`nc` cannot do this; the ritual only falls back to it with a
   loud warning, and never for a real login.)

When you leave (`QUIT` or `Ctrl-C`), the ritual **banks the coals**: a server it
lit, it puts out. A server it merely joined, it leaves burning. Boot a different
game with `FORGE_SEED=spiral-ascent make ritual`.

### Bind the phrase `start the ritual`

`make` targets are single words, so to type the literal phrase, add this shell
function to your `~/.bashrc` (a `start` command doesn't exist on Linux, so this
is safe):

```bash
start() {
  if [ "$*" = "the ritual" ]; then
    make -C "$HOME/Projects/MatrymLabs/codeforge" ritual
  else
    echo "start: only 'the ritual' is known here"; return 1
  fi
}
```

Reload with `source ~/.bashrc`, then anywhere:

```bash
start the ritual
```

### Closing the ritual

At day's end, the counterpart secures the workshop:

```bash
make ritual-down     # or, bound as a phrase:  complete the ritual
```

It **banks any forge** still burning on :4000 (a detached server, or a ghost from
an old launch), stops any codeforge containers, and gives an honest **muster** -
uncommitted changes and unpushed commits - so nothing is lost overnight. It never
pushes for you; it just tells the truth. (`start the ritual` already banks the
forge it lit when you quit - this catches everything else, and is safe to run
twice.)

To bind the phrase, add a `complete` function to `~/.bashrc`. `complete` *is* a
bash builtin (programmable completion), so the function delegates every other use
straight to it - bash completion keeps working:

```bash
complete() {
  if [ "$*" = "the ritual" ]; then
    make -C "$HOME/Projects/MatrymLabs/codeforge" ritual-down
  else
    command complete "$@"   # fall through to the real builtin
  fi
}
```

---

## 2. Connect to the running server

From any machine that can reach the host, use **any** of these:

```bash
python3 scripts/mud_client.py <host> 4000   # bundled - masks your password, no deps
telnet <host> 4000                          # classic - also masks the password
nc <host> 4000                              # simplest, but CANNOT mask the password
```

Or point a real MUD client (**Mudlet**, TinTin++, MUSHclient) at `<host>` port
`4000`. `<host>` is `localhost` if you're on the same machine. For logging in,
prefer the bundled client, `telnet`, or Mudlet - anything that honors the telnet
echo blackout so your password stays hidden.

> **Note on raw `nc`:** the gateway blacks out the password prompt using telnet
> option negotiation (IAC WILL/WONT ECHO). Real telnet clients and Mudlet honor
> it, so your password is masked. Raw `nc` ignores negotiation, so you may *see*
> your password as you type - that's a quirk of `nc`, not a leak in the server.
> The password is still hashed the same way.

---

## 3. The front desk - logging into The First Forge

Every connection to the gateway meets the login dialogue before it reaches the
game, and it **must authenticate** - there is no anonymous access. You have two
choices at the first prompt:

```text
=========================================================
            T H E   F I R S T   F O R G E
=========================================================
Character (character@account) or NEW:
```

### Option A - Register a new legend (first time)

Type `NEW`. You'll be asked for a handle and a password:

```text
Character (character@account) or NEW: NEW
Choose your character@account: climber@matlabs
Choose a password: ********
Welcome, Climber@matlabs.
```

- The handle is **`character@account`**: `climber` is the character; `matlabs` is
  the account that owns it. One account can own several characters.
- Handles are `lowercase_snake_case`; capitalization is only for display.
- The password is salted **pbkdf2-sha256** at rest - never stored or logged in
  plaintext. Mixed-case passwords are preserved exactly (case is *not* mangled).

### Option B - Return to an existing character

Type the full `character@account` and its password:

```text
Character (character@account) or NEW: climber@matlabs
Password: ********
Welcome back, Climber@matlabs.
```

Characters persist across server restarts - job, level, XP, location, and rank
are remembered; stats and resources recompute on restore.

Pressing Enter with no input does **not** grant access - the door simply
re-prompts. Login is required.

Once you see **`Welcome`** / **`Welcome back`**, you're in the world at the
`>` prompt.

---

## 4. Your first session (First Forge)

Type `HELP` any time for the full command list. A first run, start to level-up:

```text
> look                     # where am I? (The Cold Forge)
> jobs                     # the callings this world offers
> job vanguard             # choose one - you can't fight without a calling
> score                    # your character sheet: level, XP, HP/MP
> name Climber              # set your display name
> north                    # walk to the Broken Courtyard
> attack dummy             # strike the training dummy...
> attack dummy             # ...it collapses, then reassembles itself, and you gain XP
> score                    # watch the XP climb toward the next level
```

Core verbs:

```text
look                       inventory                talk <npc>
go <dir> | n/s/e/w/u/d     take <item> / drop       say <message>
jobs / job <calling>       score                    who
attack <target>            unlock <door> with <key> regs [topic|id]
name <yourname>            passwd                    save / load / quit
```

`regs` reads the Federal Guidance Library (a sibling repo) read-only, if one is
mounted - a clean "not mounted" message shows when it isn't.

---

## 5. Wizard & owner verbs (`@`-prefixed)

Authority is ranked: **player → wizard → owner**. Admin verbs check rank before
any code runs. Grant a rank from the host shell (the server operator's power):

```bash
codeforge grant climber wizard      # or: owner
```

Then, logged in as that character, the `@`-verbs unlock - e.g. `@teleport`,
`@grant`, `@shutdown`. A player without the rank is refused, loudly.

---

## 6. The HTTP admin API (a separate server)

Distinct from the game gateway. It exposes a read/observe surface over the
canonical world; mutations require **owner-account HTTP Basic auth**.

```bash
codeforge api            # serves on http://0.0.0.0:8000
```

Renderers and HTTP reads never mutate the world - state is canonical, text and
JSON are only projections of it. Run this only if you want the admin surface;
players never touch it.

---

## 7. Stopping, ports, and knobs

**Stop a server:** `Ctrl+C` in its terminal. For the container:
`docker rm -f <name>`.

**Environment knobs:**

| Variable | Default | What it does |
|---|---|---|
| `FORGE_SEED` | `first-forge` | Which game the engine boots. Read once at startup. |
| `CODEFORGE_DB` | repo-root `codeforge.db` | Absolute path to the SQLite database. Set this for containers or a chosen data dir. |
| `CODEFORGE_SEEDS_ROOT` | repo `seeds/` | Where seed packs live. Set only for installed/containerized deploys where the package sits apart from the seeds. |

**Ports:** game gateway **4000**, HTTP admin **8000**.

---

## 8. Troubleshooting

- **"I installed a fix but the server didn't change."** A running server is a
  snapshot of the code at launch. Stop it and restart. Check for a ghost:
  `lsof -i :4000` and `docker ps`, kill the stray, relaunch from the repo root.
- **`KeyError` / "Seed file not found" on boot.** The seed pack isn't where the
  engine is looking. For an installed/containerized run, set `CODEFORGE_SEEDS_ROOT`
  to the seeds directory.
- **A second, empty database appears.** You launched from the wrong directory in
  an old checkout. The DB path is now anchored to the repo root by default; set
  `CODEFORGE_DB` to an absolute path to be certain.
- **I can see my password when typing over `nc`.** Expected - raw `nc` ignores
  telnet echo negotiation (see §2). Use telnet or Mudlet for the blackout.
