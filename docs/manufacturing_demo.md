# Manufacturing demo: forge a standalone game in one command

CodeForge is a software manufacturing platform with two outputs: an installable **World Package**
(a game) and a **Software Hardware Store** of reusable parts. This is the proof, runnable end to
end. The engine that runs the flagship MUD, one chosen seed pack, and a scaffold are poured into a
standalone project - and it is proven to boot, run, and stand on its own.

## One command

```
make forge NAME=SlimGame SURFACES=solo,save DEST=../slim-game
```

```
FORGED: SlimGame  (a standalone CodeForge cast)

  world (seed):     first-forge
  surfaces:         solo, save
  engine strategy:  vendored-selective
  engine modules:   69 vendored / 126 total  (57 shed)
  declared deps:    7
  validated:        PASS - boots and every surface command ran
  cast path:        ../slim-game

  Two outputs, one machine: this game is the World Package; the engine and the
  Hardware Store parts that made it are CodeForge's.
```

What that one command did, in order:

1. **Plan** (`plan_cast`) - read the template, decide what a cast would carry, write nothing.
2. **Selectively vendor** (`generate_cast(modules=...)`) - vendor ONLY the modules the chosen
   surfaces load (the runtime closure from `parts/coupling.py`), not the whole engine. Here a
   solo+save game **shed 57 of 126 engine modules** - it carries no self-auditing engineering
   stack, no admin/API, no manufacturing tooling, no multiplayer servers.
3. **Prove the cut** (the broad harness) - boot the poured game and run *every* solo+save command
   against it. If a wrongly-excluded module were needed, that command fails loud and the cast is
   marked `not_validated`. Here all commands ran clean, so the cut is honest: `validated`.

## The rest of the pipeline (each also a command)

| Command | What it proves |
|---|---|
| `make cast-plan TEMPLATE=... NAME=...` | dry run: what a cast *would* contain (writes nothing) |
| `make cast NAME=... DEST=...` | a package **assembles** (whole engine + seed + scaffold) and **runs** |
| `make cast-selective SURFACES=solo,save` | a package **detaches selectively**, proven by the broad harness |
| `make cast-install-check DIR=...` | a package **runs in dependency isolation** (clean venv, only its deps) |
| `make coupling` | the read-only coupling report behind the cut |
| **`make forge`** | **all of the above, one command, one summary** |

## Honesty (what this does and does not claim)

- A cut is claimed **only** when the broad harness passes; `vendored-whole` is the honest default.
- `make forge` validates in the current environment; the **dependency-isolation** proof is
  `make cast-install-check` (a clean venv). The manifest records `validated`, never `detached`.
- Surfaces available: `solo`, `save`, `multiplayer` (the WebSocket + TCP servers, traced and
  validated by import, incl. the `parts/web/` browser assets), and `admin` (the `@`-verbs, traced
  and validated at rank `owner`). Mix them: `make forge SURFACES=solo,save,multiplayer,admin` -
  even the everything-game sheds ~52 of 126 modules (the engineering/self-audit stack no game runs).
- The harness earns its keep: a `multiplayer` cut first failed loud because `web_gateway` reads a
  DATA file (`parts/web/index.html`) that module tracing cannot discover - so `web/` is now a
  declared data dependency. A cut is claimed only when the harness passes.

See `docs/vision_resync.md` (the staircase), `parts/cast.py` (the pipeline), and
`docs/reports/2026-07-14-detachment-design.md` (the D1-D3 detachment plan).
