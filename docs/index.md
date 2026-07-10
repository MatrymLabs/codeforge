# CodeForge

A Python-native multiplayer **MUD engine** wrapped in a **self-auditing engineering stack** -
a portfolio-grade workshop of small, tested, reusable parts.

Classic MUD soul (rooms, exits, items, locked doors, NPCs, jobs, XP, combat) on a modern body:
a pure-function engine tick, a threaded TCP gateway, a WebSocket browser gate, account auth
(salted pbkdf2), SQLite or PostgreSQL via SQLAlchemy, a FastAPI admin surface and a live
HTMX dashboard, YAML-seeded worlds, and CI on GitHub Actions.

!!! note "Readiness, not certification"
    This project proves engineering *readiness* with automated evidence. Claims conform to
    the code, and a truth audit reports gaps rather than faking them. Nothing here is a
    compliance or certification claim.

## Start here

- [Run it](RUNNING.md) - start the servers, log in, run the ritual.
- [Architecture](architecture.md) - the engine tick, the drivers, canonical state.
- [Full-stack forge decision](full_stack_forge_decision.md) - architecture-first Python:
  custom core plus the frameworks that earn their place.

## The through-line

CodeForge is a deliberate convergence of disciplines: software engineering, game/world
design, classification and systems thinking, instructional design, Lean Six Sigma, project
management, safety/QA, and truth/evidence discipline. Each system is real and tested.

- **The web layer.** A [live HTMX dashboard](dashboard.md) over the forge's own evidence, a
  typed [JSON API contract](dashboard.md), a [Blueprint renderer](blueprint_renderer.md), and
  a [Claude-backed Architect](architect_brain.md) that is an API key away.
- **The data layer.** [SQLite by default, PostgreSQL for production](database.md), with
  Alembic migrations and [typed configuration](configuration.md).
- **The audit stack.** [Frame-up](frame_up.md), [VeritasGate](veritas.md),
  [Safety and QA](safety_qa_system.md), and [repo integrity](repo_integrity.md) - the machine
  grades itself.
- **The evidence.** A [career board](career_evidence_board.md) maps the work to job-ready
  skills with cited proof; the [hiring matrix](hiring_requirement_matrix.md) measures it
  against 2026 expectations.

## The source

The code lives at [github.com/MatrymLabs/codeforge](https://github.com/MatrymLabs/codeforge),
MIT licensed, CI-green on every merge.
