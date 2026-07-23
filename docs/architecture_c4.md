# CodeForge - C4 model view

The [C4 model](https://c4model.com/) describes software at four zoom levels. The two that
carry the most signal are here: **Level 1 (System Context)** shows who uses CodeForge and
what it depends on; **Level 2 (Container)** shows the runnable pieces inside and how one
command flows through them. The prose walkthrough and the design decisions live in
[architecture.md](architecture.md) and [adr/](adr/); this file is the map.

Both diagrams render on GitHub (Mermaid). They are pinned by
`tests/test_architecture_c4.py`: every code module named below must exist on disk, so the
map can never quietly drift from the engine it claims to describe.

## Level 1 - System Context

```mermaid
flowchart TB
    player["Player<br/>(Mudlet / telnet / terminal)"]
    owner["Owner / Wizard<br/>(rank-gated admin)"]

    subgraph forge["CodeForge - a Python-native MUD engine + self-auditing stack"]
        engine["Engine and world"]
    end

    seeds[("YAML seed packs<br/>seeds/&lt;pack&gt;/*.yaml")]
    db[("SQLite<br/>codeforge.db")]
    fgl["Federal Guidance Library<br/>(read-only regs, optional)"]
    claude["Claude API<br/>(Architect brain, optional)"]

    player -->|"plays via the engine tick"| engine
    owner -->|"HTTP admin + @-verbs"| engine
    engine --> seeds
    engine --> db
    engine -.->|"regs verb, read-only"| fgl
    engine -.->|"blueprint AI, mockable seam"| claude
```

## Level 2 - Containers

```mermaid
flowchart TB
    subgraph drivers["Drivers (thin callers of the tick)"]
        tcp["TCP gateway<br/>parts/gateway.py"]
        term["Terminal loop<br/>parts/terminal.py"]
        web["Web admin (FastAPI)<br/>parts/api.py"]
    end

    tick["The engine tick<br/>forge.py :: handle_command<br/><b>the only door that mutates state</b>"]

    subgraph subsystems["Subsystems (parts/*)"]
        seedloader["Seed loader<br/>parts/world/seed.py"]
        registry["Classification registry<br/>parts/registry.py"]
        ranks["Authorization / ranks<br/>parts/world/ranks.py"]
        events["Event bus<br/>parts/world/events.py"]
        quality["Safety + QualityGate<br/>parts/qualitygate.py"]
        persistence["Persistence<br/>parts/world/db.py + parts/save.py"]
    end

    seedsdata[("seeds/&lt;pack&gt;/*.yaml + splash.txt")]
    dbfile[("codeforge.db")]

    tcp --> tick
    term --> tick
    web --> tick
    tick --> ranks
    tick --> registry
    tick --> events
    tick --> quality
    tick --> seedloader
    seedloader --> seedsdata
    tick --> persistence
    persistence --> dbfile
```

## Containers to code

| Container | Responsibility | Module |
|---|---|---|
| Engine tick | one command in, one response out; the only door that mutates world state | `forge.py` |
| TCP gateway | telnet front desk: authenticate before the world | `parts/gateway.py` |
| Terminal loop | solo local driver | `parts/terminal.py` |
| Web admin | rank-gated FastAPI admin surface | `parts/api.py` |
| Seed loader | validate and load the world from data, failing loud at the gate | `parts/world/seed.py` |
| Classification registry | file every object and module (the tech-order index) | `parts/registry.py` |
| Authorization | rank checks before capability | `parts/world/ranks.py` |
| Event bus | per-player echo sinks and room broadcasts | `parts/world/events.py` |
| Safety + QualityGate | readiness gates before risky actions | `parts/qualitygate.py` |
| Persistence | minimal canonical state; stats recompute on restore | `parts/world/db.py`, `parts/save.py` |

Every module path in this file is asserted to exist by the correspondence test, so a rename
that forgets the map turns the suite red instead of leaving a lie on the page.
