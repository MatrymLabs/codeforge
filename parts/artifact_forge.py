"""CARD: artifact_forge -- stamp a portfolio-artifact repo skeleton (boilerplate, never logic).

The forge's dev-experience tool for building portfolio artifacts to a hiring-manager standard. It
materializes the standardized skeleton a credible junior/mid project needs -- a case-study README,
sequential Nygard ADRs, a design doc, an API-spec stub, a test-plan checklist, a reusable CI
workflow, a docker-compose file, and a `.env.example` -- into a target directory, so every new
artifact starts consistent and documented instead of blank.

The guardrail is the point: it generates **structure and boilerplate, never business logic or
learning-bearing code**. It writes the README you fill in and the ADR skeleton you decide inside,
not the app. That keeps the "genuine understanding" line honest (the human-keel doctrine): the
forge frames the workshop; the engineer builds the machine.

Inputs: an artifact name (a safe slug), a kind (`service` | `full-stack` | `cli`), and a
destination. Output: a list of written files. Fail-loud and safe-by-construction: an unsafe name,
an unknown kind, a path that would escape the destination, or an existing file (without an explicit
overwrite) is refused before anything is written.

Provenance: original implementation. The repository-layout and README conventions are the
publicly documented portfolio-presentation practice (predictable `/docs`, `/adr`,
`/.github/workflows` layout; a case-study README leading with the live demo); no code copied. This
turns the repo's own reference layouts (`docs/repo_templates/*`) from prose into a live generator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# The artifact shapes this forge knows. `service` is a Python backend; `full-stack` adds the
# backend/frontend split (per docs/repo_templates/full_stack.md); `cli` is a lean command-line tool.
KINDS = ("service", "full-stack", "cli")

# A safe artifact slug: lowercase, starts with a letter, hyphen-separated. Frozen here because it
# names a directory and a package -- an unsafe value must never reach the filesystem.
_SLUG = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class ScaffoldError(ValueError):
    """A refused scaffold request (bad name, unknown kind, unsafe path, or would overwrite):
    fail loud before writing anything, never a half-materialized skeleton."""


@dataclass(frozen=True)
class ScaffoldPlan:
    """A planned skeleton: the artifact's name, kind, and the relative-path -> content file map.

    Planning is separated from writing so the file set can be inspected and tested without touching
    the filesystem (renderers are pure, architecture law 1).
    """

    name: str
    kind: str
    files: dict[str, str]


def _readme(name: str, description: str) -> str:
    """The case-study README template: lead with the live demo, then problem, decisions, stack."""
    title = name.replace("-", " ").title()
    desc = description or "One line: what this is and who it is for."
    return f"""# {title}

> {desc}

**Live demo:** <ADD A PUBLIC URL FIRST -- an undeployed project reads as incomplete>
**Demo credentials:** <if login-gated, provide read-only demo creds>

![screenshot](docs/screenshot.png) <!-- a screenshot or GIF is the second thing a reviewer sees -->

## Problem

<One paragraph: the real problem this solves. Not "a todo app" -- the specific, honest problem.>

## Key decisions and trade-offs

<The 2-4 choices a reviewer will ask about, each with WHY and what you traded away. Link the ADRs
in `docs/adr/`.>

## Tech stack (and why)

| Layer | Choice | Why |
|-------|--------|-----|
| Back end | <e.g. FastAPI> | <why this over the alternative> |
| Data | <e.g. Postgres> | <why> |
| Front end | <e.g. React + TypeScript> | <why> |
| Deploy | <e.g. Render> | <why> |

## Features

- <the feature that makes this "real": input validation, auth, pagination, error handling...>

## Local setup

```bash
cp .env.example .env      # fill in the values (no secrets are committed)
docker compose up         # a stranger should be able to run it from here
```

## Testing

```bash
<the one command that runs the suite>
```

See `docs/test-plan.md` for what is covered (happy path, invalid input, unauthorized, failure,
boundary, recovery).

## Deployment

<How it reaches its live URL: the PaaS, the CI deploy job, the one manual step if any.>

## What I would do differently

<The honest "at 10x scale / with more time" reflection. This is the senior-signal section.>
"""


def _design_doc(name: str) -> str:
    """A design-doc template (context, goals/non-goals, alternatives, tradeoffs)."""
    return f"""# Design doc: {name}

Status: draft
Author: <you>

## Context and problem

<What system/user problem this solves, and why it is worth building.>

## Goals

- <the concrete outcomes this must achieve>

## Non-goals

- <what this deliberately does NOT do (scope discipline)>

## The design

<Data model, the main flow, the interfaces. A diagram beats a paragraph.>

## Alternatives considered

1. **<alternative A>** -- rejected because <reason>.
2. **<alternative B>** -- deferred because <reason>.

## Consequences

- **Positive:** <what this buys>
- **Negative (named honestly):** <the real cost / the thing that could bite later>

## Test strategy

<Unit / integration / e2e split, and the failure modes each covers.>
"""


def _api_spec() -> str:
    """An API-spec stub (the deliverable a reviewer scans for API maturity)."""
    return """# API specification

<Auto-generate this from the framework where possible (FastAPI serves /openapi.json; highlight it
in the README). This file is the human-readable companion.>

## Conventions

- **Versioning:** <path or header versioning; backward-compatibility policy>
- **Errors:** a consistent error envelope, e.g. `{ "error": { "code", "message", "detail" } }`
- **Pagination:** <cursor or offset; the parameters and the response shape>
- **Idempotency:** <if any mutation is retried, the Idempotency-Key contract>
- **Auth:** <the scheme; where the token goes>

## Endpoints

| Method | Path | Auth | Purpose | Errors |
|--------|------|------|---------|--------|
| GET | /health | none | liveness/readiness | - |
| ... | ... | ... | ... | ... |
"""


def _test_plan() -> str:
    """A test-plan checklist (the test pyramid as an explicit, checkable strategy)."""
    return """# Test plan

The test pyramid as an explicit strategy: many fast unit tests, fewer integration tests, a thin
layer of end-to-end tests. Every feature earns the seven cases below, not just the happy path.

## Per-feature checklist

- [ ] **Happy path** -- the intended use works.
- [ ] **Invalid input** -- bad/malformed input is refused with a clear error.
- [ ] **Unauthorized** -- an actor without permission is refused (broken access control, OWASP #1).
- [ ] **Failure path** -- a dependency error is handled, not swallowed or crashed.
- [ ] **Boundary conditions** -- empty, max, off-by-one, duplicate.
- [ ] **Recovery** -- the system returns to a good state after a failure.
- [ ] **Regression protection** -- a fixed bug gets a test so it cannot silently return.

## Layers

- **Unit:** <where; the pure logic>
- **Integration:** <the DB / API boundary, with a real or fake dependency>
- **End-to-end:** <the one or two critical user journeys (e.g. Playwright)>
- **Coverage gate in CI:** <the threshold and why>
"""


def _adr_meta() -> str:
    """ADR-0001: the meta-decision to keep ADRs (Nygard format), so the series has a root."""
    return """# ADR-0001: Record architecture decisions

Status: Accepted

## Context

We want the significant decisions on this project to be discoverable and to explain their *why*,
not just their *what*. A reviewer (and a future maintainer) should be able to read the decisions
and understand the trade-offs.

## Decision

We will keep Architecture Decision Records in `docs/adr/`, one Markdown file per decision,
sequentially numbered (`0001-...`, `0002-...`), in Michael Nygard's format
(Title / Status / Context / Decision / Consequences). New decisions copy `TEMPLATE.md`.

## Consequences

- **Positive:** the reasoning behind each decision is preserved and skimmable; the "why" survives
  staff turnover and time.
- **Negative:** a small discipline cost -- a real decision now costs a short write-up.
"""


def _adr_template() -> str:
    """The Nygard ADR template new decisions copy."""
    return """# ADR-NNNN: <short decision title>

Status: Proposed | Accepted | Superseded by ADR-XXXX

## Context

<The forces at play: the problem, the constraints, what makes this a real decision.>

## Decision

<The choice, stated plainly. "We will ...">

## Consequences

- **Positive:** <what this buys>
- **Negative:** <the cost, named honestly -- every decision has one>
"""


def _ci_yml() -> str:
    """A reusable GitHub Actions CI skeleton: lint -> test -> build -> deploy."""
    return """# Reusable CI skeleton: lint -> test -> build -> (deploy). Fill in the tool commands.
name: ci

on:
  push:
    branches: [main]
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up runtime
        run: echo "TODO set up Python/Node"
      - name: Lint
        run: echo "TODO ruff/eslint"
      - name: Type check
        run: echo "TODO mypy/tsc"
      - name: Test
        run: echo "TODO pytest/jest with coverage"
      - name: Build
        run: echo "TODO docker build (prove the image builds)"

  deploy:
    needs: check
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy
        run: echo "TODO deploy to the PaaS (a live URL is non-negotiable)"
"""


def _compose(name: str) -> str:
    """A docker-compose skeleton (app + db); values come from env, no literal secrets."""
    return f"""# Multi-service skeleton. Real values come from the environment, never committed.
services:
  app:
    build: .
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      - db

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: {name.replace("-", "_")}
      POSTGRES_USER: "${{POSTGRES_USER:-app}}"
      POSTGRES_PASSWORD: "${{POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}}"
    volumes:
      - db-data:/var/lib/postgresql/data

volumes:
  db-data:
"""


def _env_example() -> str:
    """A .env.example: variable NAMES and shapes only, never a real secret."""
    return """# Copy to .env and fill in. NEVER commit .env. Only this example is tracked.
# Values here are blank placeholders, not real credentials.

# e.g. postgresql://<user>:<password>@<host>:5432/<db>
DATABASE_URL=
POSTGRES_USER=app
# set a strong value locally; never commit it
POSTGRES_PASSWORD=
# app signing key; generate a fresh random value
SECRET_KEY=
LOG_LEVEL=info
"""


def _gitignore() -> str:
    """Sensible ignore defaults, with .env excluded and .env.example kept."""
    return """.env
*.pyc
__pycache__/
.venv/
node_modules/
dist/
build/
.coverage
coverage.xml
*.db
!.env.example
"""


def _changelog(name: str) -> str:
    """A Keep-a-Changelog stub."""
    return f"""# Changelog

All notable changes to {name}. Format: Keep a Changelog; this project uses Conventional Commits.

## [Unreleased]

- Scaffolded the repository skeleton.
"""


def plan_scaffold(name: str, kind: str = "service", *, description: str = "") -> ScaffoldPlan:
    """Plan the skeleton file set for an artifact, without touching the filesystem.

    Fails loud (`ScaffoldError`) on an unsafe name (must match a lowercase slug) or an unknown kind.
    """
    if not isinstance(name, str) or not _SLUG.match(name):
        raise ScaffoldError(
            f"artifact name must be a lowercase slug (letters, digits, hyphens), got {name!r}"
        )
    if kind not in KINDS:
        raise ScaffoldError(f"unknown kind {kind!r}; expected one of {KINDS}")

    files: dict[str, str] = {
        "README.md": _readme(name, description),
        "docs/design-doc.md": _design_doc(name),
        "docs/api-spec.md": _api_spec(),
        "docs/test-plan.md": _test_plan(),
        "docs/adr/0001-record-architecture-decisions.md": _adr_meta(),
        "docs/adr/TEMPLATE.md": _adr_template(),
        ".github/workflows/ci.yml": _ci_yml(),
        ".env.example": _env_example(),
        ".gitignore": _gitignore(),
        "CHANGELOG.md": _changelog(name),
    }
    if kind in ("service", "full-stack"):
        files["docker-compose.yml"] = _compose(name)
    if kind == "full-stack":
        files["frontend/README.md"] = (
            f"# {name} frontend\n\nReact + TypeScript client. Talks to the backend only over HTTP "
            "(the seam is the API; no shared imports).\n"
        )
        files["backend/README.md"] = (
            f"# {name} backend\n\nPython (FastAPI) service. Owns the API, the data model, and the "
            "tests.\n"
        )
    if kind == "cli":
        # A CLI needs no compose/frontend; the API spec becomes a command reference instead.
        files["docs/api-spec.md"] = (
            "# Command reference\n\n<Document each subcommand: its arguments, output, and exit "
            "codes. This is the CLI's contract.>\n"
        )
    return ScaffoldPlan(name=name, kind=kind, files=files)


def _safe_target(dest: Path, rel: str) -> Path:
    """Resolve `rel` under `dest`, refusing any path that would escape it (path-traversal guard)."""
    target = (dest / rel).resolve()
    root = dest.resolve()
    if root != target and root not in target.parents:
        raise ScaffoldError(f"unsafe path {rel!r} escapes the destination")
    return target


def materialize(plan: ScaffoldPlan, dest: Path, *, overwrite: bool = False) -> list[Path]:
    """Write the planned skeleton under `dest`, returning the files written (in sorted order).

    Safe by construction: every path is checked to stay within `dest`, and an existing file is
    refused unless `overwrite=True` -- both checked for ALL files before any is written, so a
    refusal leaves the destination untouched.
    """
    dest = Path(dest)
    targets: list[tuple[Path, str]] = []
    for rel in sorted(plan.files):
        target = _safe_target(dest, rel)
        if target.exists() and not overwrite:
            raise ScaffoldError(f"refusing to overwrite existing file: {rel} (pass overwrite=True)")
        targets.append((target, plan.files[rel]))

    written: list[Path] = []
    for target, content in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(target)
    return written


def next_adr_number(adr_dir: Path) -> int:
    """The next sequential ADR number in `adr_dir` (1 if none exist). Ignores TEMPLATE.md."""
    adr_dir = Path(adr_dir)
    if not adr_dir.is_dir():
        return 1
    numbers = [
        int(m.group(1))
        for p in adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md")
        if (m := re.match(r"(\d{4})-", p.name))
    ]
    return max(numbers) + 1 if numbers else 1


def _default_dest(name: str) -> Path:
    """Where `make artifact` writes by default: a git-ignored workspace, so a demo never pollutes
    the engine repo. The path is resolved at call time so tests can point elsewhere."""
    return Path(__file__).resolve().parent.parent / "workspace" / "artifacts" / name


def main(argv: list[str] | None = None) -> int:
    """`make artifact NAME=<slug> [KIND=...]`: stamp a portfolio-artifact skeleton.

    Writes to `workspace/artifacts/<name>/` (git-ignored) by default. Returns 2 on a refused
    request (bad name/kind, or a destination that already holds one of the files).
    """
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or not args[0].strip():
        print("usage: python -m parts.artifact_forge <name> [kind=service|full-stack|cli]")
        return 2
    name = args[0].strip()
    kind = args[1].strip() if len(args) > 1 and args[1].strip() else "service"
    try:
        plan = plan_scaffold(name, kind)
        dest = _default_dest(name)
        written = materialize(plan, dest)
    except ScaffoldError as exc:
        print(f"artifact scaffold refused: {exc}")
        return 2
    print(f"forged {len(written)} files for '{name}' ({kind}) -> {dest}")
    for path in written:
        print(f"  {path.relative_to(dest)}")
    print("\n  Guardrail: this is structure + boilerplate. You write the logic and fill the docs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
