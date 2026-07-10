# Tooling Strategy (Frameless Python)

*Companion to [`frameless_python.md`](frameless_python.md). This is where a tool earns, or
fails to earn, its place. Python's standard library and CodeForge's own architecture are the
spine; every external tool is a deliberate, documented, removable integration.*

Repo: `codeforge` · Baseline audit: 2026-07-10

---

## Executive summary

CodeForge is already a **Phase 3** repo by the roadmap below. The professional dev-tooling
and portfolio-proof stacks are integrated and deliberate: Ruff, mypy, pytest + pytest-cov +
hypothesis, pip-audit, bandit, detect-secrets, a CycloneDX SBOM, CodeQL, and Dependabot, all
gated through the Make Ritual and GitHub Actions. The CLI is hand-rolled stdlib argv dispatch
(`parts/cli.py`), not even argparse; content is YAML validated by my own loader gates. So the
value of this audit is **not** adding tools. It is (1) documenting the frameless choices so
they are defensible in an interview, and (2) naming the few genuine gaps. Only one tool is a
clear `integrate_now` candidate (OpenSSF Scorecard); everything else is already present or is
`integrate_later` / `research_only`.

---

## Current tool inventory (what is already integrated)

| Category | Tool(s) present | Config / evidence |
|---|---|---|
| CLI | stdlib argv dispatch (no argparse) | `parts/cli.py` |
| Packaging | pyproject + setuptools, pinned deps + `dev` extras | `pyproject.toml` |
| Lint / format | Ruff (`E,F,I,UP,B,SIM`, line 100) | `[tool.ruff]` |
| Types | mypy (py313, `warn_unused_ignores`) | `[tool.mypy]` |
| Testing | pytest, pytest-cov, hypothesis (property marker) | `[tool.pytest.ini_options]` |
| Automation | Make Ritual (~35 targets), no pre-commit | `Makefile` |
| Security | pip-audit, bandit, detect-secrets, cyclonedx-bom | `Makefile`, `[tool.bandit]`, CI |
| CI | GitHub Actions `ci.yml` + `codeql.yml` + docker smoke | `.github/workflows/` |
| Supply chain | Dependabot, CodeQL, SBOM artifact | `.github/dependabot.yml`, `codeql.yml` |
| Docs | rich raw Markdown, ADRs, runbooks, postmortems | `docs/` |
| Data / state | SQLite via SQLAlchemy behind `parts/db.py` | `parts/db.py` |

Runtime dependencies (the shipped wheel): `pyyaml`, `sqlalchemy`, `fastapi`, `uvicorn`,
`websockets`. Everything else is a dev/CI-time gate, not runtime identity.

---

## Decision matrix

Status labels are defined at the bottom of this doc. Grounded in the inventory above.

| Tool | Category | Status | Why |
|---|---|---|---|
| stdlib (pathlib, json, csv, sqlite3, subprocess, dataclasses, enum, typing, tomllib) | Foundation | `stdlib_first` | The spine. Reach here before any add-on. |
| argparse | CLI | `stdlib_first` | Current hand-rolled dispatch is enough; argparse is the fallback, not Typer. |
| Ruff | Quality | `integrate_now` (done) | Replaces Black + isort + Flake8; fast; already configured. |
| pytest + pytest-cov | Testing | `integrate_now` (done) | Professional testing + coverage proof; 91%+. |
| hypothesis | Testing | `integrate_now` (done) | Property tests already gate via `make property`. |
| mypy | Typing | `integrate_now` (done) | Gradual typing discipline, already green. |
| Make | Automation | `integrate_now` (done) | The Ritual interface; stays the primary control panel. |
| pip-audit | Security | `integrate_now` (done) | CVE audit in `make audit` + CI. |
| bandit | Security | `integrate_now` (done) | SAST in CI with reviewed suppressions. |
| detect-secrets | Security | `integrate_now` (done) | Baselined secret scan (`make secrets`). |
| cyclonedx-bom | Security | `integrate_now` (done) | SBOM artifact in CI. |
| CodeQL | Security | `integrate_now` (done) | GitHub-native code scanning. |
| Dependabot | Security | `integrate_now` (done) | Dependency update PRs. |
| OpenSSF Scorecard | Security | `integrate_now` (done) | The last Phase-3 signal; `scorecard.yml` + public badge, no runtime dep. |
| pre-commit | Automation | `documented_option` | `make check` + CI already gate; adds contributor friction. Optional local mirror. |
| MkDocs / Material | Docs | `portfolio_candidate` | Could publish `docs/` to the portfolio page. Not needed while Markdown reads well. |
| pdoc | Docs | `optional_dev_tool` | Zero-config API docs from existing CARD docstrings. Nice-to-have. |
| Sphinx | Docs | `research_only` | Heavyweight; reserve for a real API surface, not now. |
| uv | Packaging | `research_more` | Could speed CI installs; decide after current setuptools flow is proven. |
| Poetry / Hatch / PDM | Packaging | `research_only` | setuptools + pyproject already works; no reproducibility gap to close. |
| Typer / Click | CLI | `integrate_later` | Better UX later; today would add a framework the CLI does not need. |
| Rich | CLI | `do_not_integrate_yet` | Plain-text renders are deterministic and testable; color would complicate test twins. |
| Textual | CLI | `integrate_later` | The terminal-control-panel vision (backlog), not this phase. |
| pyinstrument / scalene / line_profiler | Perf | `research_only` | Command timing suffices in-repo; deep perf evidence lives in `pyg-perf-lab`. |
| pluggy / stevedore | Plugins | `internal_custom` | The classification registry is the CodeForge-native version; build custom first. |
| Pydantic (standalone) | Data | `stdlib_first` | dataclasses + my own validators cover it; FastAPI pulls pydantic transitively anyway. |
| Alembic | Data | `integrate_later` | Only when schema migrations outgrow `codeforge migrate-db`. |
| gitleaks / trufflehog | Security | `research_only` | detect-secrets already covers this; redundant. |
| Semgrep | Security | `research_only` | bandit + CodeQL cover SAST; revisit only for custom rules. |

---

## Top recommendations (this cycle)

**Integrated this cycle (1):**
1. **OpenSSF Scorecard** (`integrate_now`, DONE). The single professionalism/security signal
   from the Phase-3 list that was not yet wired. Shipped as `.github/workflows/scorecard.yml`
   with a public badge, no runtime dependency.

**Repo settings tuned for the score (safe, reversible):**
- All GitHub Actions pinned to full commit SHA (Scorecard Pinned-Dependencies); Dependabot
  maintains them.
- `main` branch protection enabled: require a pull request + the `check` and `docker` CI
  jobs (strict) before merging, force-push and deletion blocked. Solo-friendly (0 required
  approvals, so the owner self-merges) and no lockout (`enforce_admins=false`, an emergency
  bypass remains). This also aligns the repo with its own documented workflow
  (branch -> PR -> CI green -> merge); the local merge-to-main shortcut is retired.

**Document for later (2):**
1. **MkDocs / Material** (`portfolio_candidate`) to publish `docs/` alongside the portfolio page.
2. **pdoc** (`optional_dev_tool`) to auto-generate API docs from the CARD docstrings already written.

**Not worth adding yet (3):**
1. **Poetry / uv / Hatch** (`research_more`) - no reproducibility gap; setuptools + pinned deps works.
2. **Rich / Typer** (`do_not_integrate_yet`) - would dilute the frameless CLI and complicate test twins.
3. **pluggy / stevedore** (`internal_custom`) - the registry is already the native version.

---

## Tool Integration Review template

Copy this block for any tool under consideration; file the completed review in
`docs/reports/professional-development/` or link it from the ADR that adopts the tool.

```text
Tool Integration Review

Tool:
Category:
Official Purpose:
What problem it solves:
Standard-library alternative:
Why CodeForge might use it:
Why CodeForge might avoid it:
Professional skill it proves:
Integration difficulty:
Maintenance burden:
Startup Ritual impact:
Shutdown Ritual impact:
GitHub/portfolio value:
Security/privacy concerns:
License/source concerns:
Recommended status:
  reject / research_more / document_only / optional / integrate_later / integrate_now
Best integration point:
First safe experiment:
Evidence needed:
```

---

## Dependency Approval Rule

No new runtime or dev dependency is added automatically. Any candidate must answer, in a
PR description or ADR, before it lands:

1. Why do we need this?
2. What standard-library option exists?
3. What professional skill does this prove?
4. Where will it be configured?
5. How will it be tested?
6. How will it affect the startup / shutdown Ritual?
7. How will it be documented?
8. Can it be removed later?

If the case is not strong on "need", "skill proven", and "removable", the default is
`stdlib_first`, `research_only`, or `integrate_later`.

**Enforced, not just documented.** `make deps` (part `parts/dependencies.py`, stdlib
`tomllib` only) reads the declared dependencies from `pyproject.toml` and their
justifications from `dependency_ledger.toml`, then fails loud on any dependency declared
without a ledger row (and warns on a stale row). The test twin rides `make check`, so an
unjustified dependency cannot merge silently. Adding a dependency now means adding its
row here first.

---

## Phased roadmap (where CodeForge sits)

- **Phase 1 - Frameless foundation.** stdlib, Make, pytest, Markdown docs, JSON/TOML config,
  logging, plain reports. **DONE.**
- **Phase 2 - Professional dev tooling.** Ruff, pytest, coverage, mypy (gradual), pip-audit,
  a secret scanner, (pre-commit optional). **DONE** (pre-commit deliberately deferred).
- **Phase 3 - Portfolio / GitHub proof.** GitHub Actions, Dependabot, CodeQL, SBOM, structured
  reports; MkDocs and OpenSSF Scorecard optional. **DONE** - OpenSSF Scorecard now wired
  (`scorecard.yml`); MkDocs remains a documented option.
- **Phase 4 - Seed / installability.** pyproject polish, packaging entry points, template
  generation, plugin architecture, versioned Seed manifests. **PARTIAL** (entry points +
  console scripts exist; plugin architecture stays `internal_custom`).
- **Phase 5 - Advanced platform.** Textual control panel, pluggy/entry-point plugins, web
  dashboard, FastAPI (already present for admin), SQLAlchemy (present), profilers if perf
  requires. **DEFERRED by design** until the portfolio page is live.

---

## Status label definitions

```text
stdlib_first             use Python standard library first
internal_custom          build a small CodeForge-native version first
research_only            learn about it, but do not add it
research_more            promising, decide after more evaluation
documented_option        mention it as a future option
optional_dev_tool        useful locally, not part of CodeForge identity
ritual_candidate         may belong in startup/shutdown/deep Ritual
ci_candidate             may belong in GitHub Actions
hardware_store_candidate could become a reusable CodeForge part
seed_candidate           may help generated Seeds
portfolio_candidate      helps demonstrate professional integration
integrate_now            high value, low risk, useful immediately
integrate_later          valuable, but not needed yet
do_not_integrate_yet     likely premature
blocked                  unsafe, unclear, unlicensed, or too risky
```

---

## Pioneer questions (open, for Josh)

**On the frameless identity**
- What is the boldest useful thing a tool could unlock without making CodeForge *look* like a framework?
- Which current tool, if removed, would you struggle to explain in an interview? (That one needs a doc.)

**On OpenSSF Scorecard**
- Is a public Scorecard badge worth the first below-average score it may report, as an honest-improvement story?
- Should Scorecard run on a schedule (weekly) or only on push?

**On docs tooling**
- Do you want a published doc *site* (MkDocs) now, or is clean Markdown enough until the portfolio page ships?
- Could pdoc-generated API docs from the CARD docstrings become a `terminal docs` program later?

**On the Hardware Store**
- Could a "tool review" itself become a Hardware Store part (a reusable evaluation checklist)?
- ~~Could the Dependency Approval Rule be enforced by a small in-repo gate (a `make` target that lints new deps)?~~
  **Answered:** yes - `make deps` (`parts/dependencies.py`) now enforces the ledger; the test twin rides `make check`.
