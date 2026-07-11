# Frameless Python (CodeForge's identity)

*CodeForge is frameless Python. Python's standard library and my own architecture are the
spine. External tools are professional integrations, not the identity of the project.*

## What "frameless" means here

CodeForge is **not** a framework project and **not** a pile of dependencies. It is a
Python-native engineering machine. The engine tick, the command spine, the classification
registry, the QA/safety gates, the seed loader, the event bus, the report writers: all of
it is my own architecture built on the standard library. Where a professional tool earns
its place, it is integrated deliberately, configured in the open, documented with a reason,
and kept removable.

The one-line positioning:

> CodeForge is a Python-native engineering machine that integrates professional tools where
> they improve proof, quality, safety, speed, or maintainability.

What CodeForge will **not** say:

- "CodeForge is a Ruff project." / "a pytest project." / "a FastAPI app."
- "CodeForge is an Evennia clone." / "just a wrapper around tools."

## The evidence it is actually frameless

| Concern | How CodeForge does it | Standard-library / own-architecture proof |
|---|---|---|
| CLI parsing | hand-rolled argv dispatch, no argparse framework | `parts/cli.py` |
| Config / content | YAML seeds validated by my own loader gates | `parts/seed.py` |
| State | SQLite via SQLAlchemy (a data tool, behind my own `parts/db.py`) | `parts/db.py` |
| Events | my own in-process event bus | `parts/events.py` |
| Reports | my own `ReportWriter`, plain Markdown | `parts/reporting.py` |
| Classification | my own registry + designations, not a plugin framework | `parts/registry.py` |
| Task running | Make + shell, the Ritual | `Makefile` |
| Diagnostics UI | plain-text renders, deterministic and testable, no TUI library | `parts/terminal.py`, `parts/frameup.py` |

The tools that *are* present (Ruff, mypy, pytest, pip-audit, bandit, detect-secrets,
cyclonedx, CodeQL, Dependabot) are **dev-time and CI-time quality gates**, not the runtime
identity. The shipped engine depends on a short, defensible list, every runtime dependency
justified in `dependency_ledger.toml` (the source of truth, gated by `make deps`): `pyyaml`,
`sqlalchemy`, `fastapi`, `uvicorn`, `websockets`, `pydantic`, `structlog`.

## The frameless rule (ask before adding a tool)

Before recommending any external tool, answer:

1. Can Python's standard library do this first?
2. Would the tool make the result more *professional*?
3. Would it make the result easier to *maintain*?
4. Would it help *prove* job-ready integration skill?
5. Would it add unnecessary dependency weight?
6. Can I explain this tool clearly in an interview?

If the answer is not strong on 2-4, the recommendation is `stdlib_first`, `research_only`,
or `integrate_later`. The full evaluation model, decision matrix, and roadmap live in
[`tooling_strategy.md`](tooling_strategy.md).

## Why this is a portfolio asset, not a limitation

An interviewer who sees "frameless Python" should read: *this person built the architecture,
understands what each tool does, chose tools deliberately, documented why, and can remove or
replace any of them.* That is a stronger signal than a repo that imports ten frameworks and
cannot explain any of them. The tools earn their place; the architecture is mine.
