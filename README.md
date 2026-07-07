# CodeForge 🔨

![CI](https://github.com/MatrymLabs/codeforge/actions/workflows/ci.yml/badge.svg)

**A Python-native modular MUD engine and reusable code workshop.**
Classic MUD soul — rooms, keys, locked doors, talking NPCs — on modern Python
architecture: typed schemas, validated data-driven worlds, gated shipping, and
a self-generating parts catalog.

```
== The Old Library ==
Dust drifts between towering shelves. An oak door in the back is sealed shut.
Exits: west, north
You see a copper key here.
The librarian is here.

> talk librarian
The librarian says: "That oak door? Sealed for years. A copper key went missing ages ago..."

> take key
You take a copper key.

> unlock door with key
You unlock the oak door with a copper key.

> go north
== The Sealed Archive ==
Forbidden shelves climb into darkness. The air tastes of secrets and old ink.
```

## Quick start

```bash
git clone git@github.com:MatrymLabs/codeforge.git
cd codeforge
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make check     # lint, typecheck, 41 tests
make run       # step into The First Forge
```

## The Hardware Store

Every engine component is a **card**: one module, one purpose, one test twin.
This inventory is **generated from the code itself** (`make store` reads each
card's docstring) — documentation that cannot go stale:

```
#   CARD      TESTED  PURPOSE
------------------------------------------------------------
1   catalog   yes     the filing system. List world components by number
2   doors     yes     lockable barriers between rooms
3   items     yes     objects, containment, take/drop/inventory
4   npcs      yes     characters who live in rooms and talk
5   save      yes     snapshot persistence for world state
6   seed      yes     load and validate room packs from YAML
7   store     yes     the hardware store inventory. List engine parts and purposes
8   world     yes     world graph, direction aliases, movement
```

## The control panel

| Button          | What it does                                              |
|-----------------|-----------------------------------------------------------|
| `make fix`      | Auto-format and auto-repair lint findings                 |
| `make check`    | The ritual: format check → lint → typecheck → tests       |
| `make coverage` | Test coverage report (currently ~90%)                     |
| `make audit`    | Scan dependencies for known vulnerabilities               |
| `make ship`     | Run all gates, then push — refuses dirty trees & red gates|
| `make run`      | Play The First Forge                                      |
| `make world`    | Numbered catalog of rooms and NPCs (operator view)        |
| `make store`    | Numbered catalog of engine parts (developer view)         |

## Architecture principles

- **The world is data.** Rooms live in `seeds/first-forge/rooms.yaml`, not in
  Python. Every room is born complete via a three-layer template merge:
  engine defaults → file `template:` block → the room's own fields.
- **Labels are identity, names are display.** Machines link by
  `lowercase_snake_case` labels; humans read names. The seed loader *gates*
  labels: bad format gets a suggested fix, duplicates are refused (plain YAML
  would silently overwrite), and dangling exits are named before the world
  can boot.
- **State is canonical, text is a projection.** Only validated actions mutate
  world state; every screen of text is rendered *from* state. Saves persist
  facts (`"oak_door": {"locked": false}`), never prose.
- **Every card ships with a test twin.** `parts/x.py` ↔ `tests/test_x.py`,
  enforced by the store catalog's `TESTED` column. A scripted robot player
  drives the real game loop end-to-end in integration tests.

## Repository layout

```
codeforge/
  forge.py              # entry point: the power switch
  parts/                # the hardware store shelves (engine cards)
  tests/                # one test twin per card + integration tests
  seeds/first-forge/    # the starter world, as data
  .github/workflows/    # CI: the ritual on every push
```

## Roadmap

- [x] Playable core loop: movement, items, locked doors, NPCs
- [x] Snapshot persistence (`save` / `load`)
- [x] Data-driven world: YAML seed with validation gates
- [x] Self-generating world & parts catalogs
- [ ] Items and NPCs join the seed (fully data-driven world)
- [ ] Gateway arc: sessions → engine tick → multi-client server
- [ ] Seed packages: install, preview, rollback (the Auto-Injector)

## License

MIT — see [LICENSE](../../../Downloads/LICENSE).
