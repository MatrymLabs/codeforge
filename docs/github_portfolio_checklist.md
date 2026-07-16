# GitHub Portfolio Checklist (CodeForge)

*Honest self-assessment against the 2026 research (`docs/research/github_portfolio_requirements.md`).
`[x]` = verified present; `[~]` = partial; `[ ]` = missing/planned. VeritasGate rule: no box
is checked unless the artifact exists. Last audited: 2026-07-10.*

- [x] Clear repo name (`codeforge`)
- [x] Clear one-line description (repo description + README subtitle)
- [x] Strong README opening (value prop + live-demo link up top)
- [x] Status label: working/prototype/planned (README + this checklist)
- [x] Quickstart (`## Quick start`)
- [x] Installation instructions (`make env`, uv/pip)
- [x] How to run tests (`## Testing`, `make check`)
- [x] Architecture overview (`## Architecture` + `docs/architecture.md` + ADRs)
- [x] Feature list (`## Engineering systems`, `## What this demonstrates`)
- [x] Screenshots or terminal demo (`docs/demo.gif` + live demo)
- [x] Roadmap (`## Roadmap`)
- [x] License (MIT, `LICENSE`)
- [x] Security note (`SECURITY.md`)
- [x] Contributing note (`CONTRIBUTING.md`)
- [x] Changelog (`CHANGELOG.md`)
- [x] CI/testing badge if real (CI + codecov + OpenSSF Scorecard, all earned)
- [x] Tech stack section (README + `docs/tooling_strategy.md`)
- [x] Portfolio/career evidence section (`career`, `docs/career_evidence_board.md`, `## Evaluation`)
- [x] Known limitations (roadmap + honest deviations below)
- [x] Next steps (roadmap + `DEVELOPMENT_PLAN.md`)

## Beyond the base checklist (production-style signals, present)

- [x] Production-style separation: `parts/` package, `tests/`, `docs/`, `.github/`, `pyproject.toml`
- [x] Linters/formatting fail CI (ruff, gated)
- [x] Type hints + static analysis (mypy, gated)
- [x] Descriptive commits + Conventional Commits
- [x] PR hygiene (branch protection: require PR + CI + CodeQL; PRs #17-24 this cycle)
- [x] Topics/discoverability (10 topics set)
- [x] Supply-chain: Dependabot, CodeQL, SBOM, bandit, detect-secrets, OpenSSF Scorecard
- [x] Deployed live demo (Render)
- [x] Issue templates (`.github/ISSUE_TEMPLATE/`) **added 2026-07-10**

## Honest deviations (deliberate, documented, not defects)

- **`parts/` not `src/`.** The research prefers a `src/` layout. codeforge uses a `parts/`
  package + root `forge.py` (the tick). Persisted identifiers (labels, CLI verbs, CARD names)
  are frozen; a rename would break save files/seeds for cosmetic conformance. Documented in
  `CLAUDE.md` (Governing boundaries).
- **SQLite not PostgreSQL.** Deliberate embedded choice behind `parts/db.py`; the DB seam is
  the only caller, so a Postgres backend is swappable. See the full-stack readiness checklist.
- **Profile README + pinning** are manual GitHub-UI actions (not repo files); tracked in the
  hirability backlog, not claimable here.

## Open items (ranked)

1. **React/TS second flagship** - the FastAPI dashboard is shipped (`parts/dashboard.py`, HTMX,
   a11y, `e2e/`, see `docs/full_stack_readiness_checklist.md`); the remaining full-stack lever is
   a Next.js/TS `codeforge-web` second flagship.
2. **Sample PR with a linked issue** - the "collaboration signal"; the PR flow is now live.
