# Full-Stack Readiness Checklist (CodeForge)

*Honest self-assessment against the 2026 research (`docs/research/full_stack_python_requirements.md`).
`[x]` present, `[~]` partial, `[ ]` planned. VeritasGate labels applied. Last audited: 2026-07-10.*

## Backend (strong)

- [x] Backend entry point (`forge.py` tick; `parts/cli.py`; FastAPI admin surface)
- [x] Project config (`pyproject.toml`, env-based via `CODEFORGE_DB`, `FGL_REGISTRY`)
- [x] Error handling (loud validation at boundaries; `SeedError`, gates)
- [x] Input validation (seed loader gates, rank checks, password parsing rules)
- [x] AuthN/AuthZ (salted pbkdf2 accounts; rank-gated `@`-verbs; owner Basic auth on admin)
- [x] Tests (435, 91.5% coverage) + quality gates (`make check`)
- [x] Security boundaries (bandit, Scorecard, CodeQL, secret scan, SBOM)
- [x] Containerized (Dockerfile, CI docker smoke, live demo)
- [~] Documented API - FastAPI admin exists but the contract is not yet showcased/OpenAPI-surfaced
- [~] Database - SQLite via SQLAlchemy (deliberate embedded choice; not PostgreSQL)
- [ ] Migrations tool (Alembic) - `codeforge migrate-db` exists; not a full migration framework

## Frontend (the gap being closed)

- [~] Semantic HTML proof - one gateway page (`parts/web/index.html`); dashboard planned
- [ ] CSS layout proof - responsive, accessible stylesheet (planned with the dashboard)
- [ ] Responsive design proof (planned)
- [ ] Accessibility basics (labels, focus, keyboard nav) (planned)
- [ ] Static or server-rendered dashboard (planned: FastAPI server-rendered, real data)
- [ ] Report display page (planned: career/QA/hardware/perf views)
- [ ] Browser/E2E tests for the dashboard (planned)

## Decisions (from the pioneer questions, 2026-07-10)

- **First proof:** FastAPI **server-rendered** read-only dashboard (semantic HTML + responsive/
  accessible CSS), rendering **real** codeforge data, as an **in-repo add-on module**
  (`parts/web` dashboard), not MUD-engine core. Preserves frameless-Python identity (no JS
  build system) while proving HTML/CSS + backend/frontend separation.
- **Second flagship (planned, target = full-stack developer):** a separate **Next.js + React +
  TypeScript** app consuming a codeforge JSON API, matching the research's separated
  architecture and the mainstream employer expectation.

## Smallest full-stack proof (what "done" looks like for phase 1)

1. `GET /` -> server-rendered dashboard (Jinja template): status cards for career board, QA
   board, hardware store, and the latest perf report.
2. `GET /api/status` -> read-only JSON (the same data), the seam a future React app consumes.
3. Semantic HTML5 (`header/nav/main/section/footer`), responsive CSS (flin/grid), accessible
   labels + focus states, no framework.
4. Tests: the routes return 200 and the rendered page contains real data; JSON matches the
   renderers.
5. A screenshot + a short "frontend decisions" doc.

## Honest labels

- Dashboard: **planned** (not yet built).
- Next.js/TS front end: **planned** (separate repo, phase 2).
- FastAPI admin: **working** (backend); its public API contract: **needs docs/showcase**.
