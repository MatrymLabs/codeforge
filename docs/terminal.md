# The in-game computer (`terminal`)

*The FORGE TERMINAL: one read-only console in the Diagnostic Console room that runs every
diagnostic program from one place. It computes nothing itself, it **wires** the renderers
the project already owns behind a single computer-terminal surface.*

## In the MUD

```
terminal            # boot screen + the program menu
terminal <name>     # run one program, framed like a console
```

## Wired programs

| Program | Runs |
|---------|------|
| `terminal functions` | Hardware Store functions check (live demo of each part) |
| `terminal inspect` | the frame-up: green/yellow/red health of every system |
| `terminal career` | the Career Evidence board |
| `terminal pioneer` | Pioneer Mode (doctrine, risk ladder, experiments) |
| `terminal pm` | the project status dashboard |
| `terminal truth` | VeritasGate: claims vs reality |
| `terminal qa` | the QA board (every filed object graded) |
| `terminal docs` | the documentation gap check |

Each entry dispatches to that system's existing renderer (composition, not duplication).
It is **read-only**, no state is changed, nothing is run that isn't already a safe render.

## Relation to `console`

The `console` (FailsafeRunner) runs allowlisted `make` gates (lint, tests, security) through
a guarded runner, never a raw shell. The `terminal` runs the in-MUD diagnostic *views*. They
sit side by side at the Diagnostic Console: `console` to run the gates, `terminal` to read
the machine's state.
