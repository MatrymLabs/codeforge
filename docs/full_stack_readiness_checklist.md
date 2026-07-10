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
- [x] Documented API - FastAPI admin + read-only `GET /api/status`; OpenAPI at `/docs`, linked from the dashboard nav
- [~] Database - SQLite via SQLAlchemy (deliberate embedded choice; not PostgreSQL)
- [ ] Migrations tool (Alembic) - `codeforge migrate-db` exists; not a full migration framework

## Frontend (phase 1 shipped)

- [x] Semantic HTML proof - server-rendered `header/nav/main/section/footer` (`parts/dashboard.py`)
- [x] CSS layout proof - responsive stylesheet, CSS grid `auto-fit` card board (inline, frameless)
- [x] Responsive design proof - `minmax(240px,1fr)` grid + viewport meta, reflows on narrow screens
- [x] Accessibility basics - `lang`, skip link, `aria-label`led regions, `:focus-visible`, text status badges (not color alone)
- [x] Server-rendered dashboard - `GET /`, real data (career / QA / hardware / perf), no framework
- [x] Report display page - the four evidence cards render the actual renderers' data
- [x] Route + render tests (`tests/test_dashboard.py`, 12 cases incl. escaping + honest-failure)
- [ ] Browser/E2E tests (Playwright) - deferred to phase 2 with the React front end

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

- Dashboard: **built** (phase 1) - server-rendered, real data, tested; see `docs/dashboard.md`.
- Next.js/TS front end: **planned** (separate repo, phase 2, the full-stack-developer target).
- FastAPI admin: **working** (backend); public API contract now **surfaced** (`/api/status`, `/docs`).
- Browser/E2E (Playwright): **planned** (phase 2, alongside the React front end).
