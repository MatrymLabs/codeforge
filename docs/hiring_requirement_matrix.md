# Hiring Requirement Matrix (CodeForge)

*Maps 2026 hiring requirements (`docs/research/`) to concrete repo evidence. Status:
proven / partial / missing / planned. VeritasGate: "proven" requires a cited artifact that
exists. Last audited: 2026-07-16. Primary target: full-stack developer.*

| Requirement | Level | Role relevance | Repo evidence | Status | Next task | Priority |
|---|---|---|---|---|---|---|
| Maintainable, readable Python | entry | all | `parts/`, ruff, forge voice | proven | keep | - |
| Type hints + static analysis | entry-mid | Python dev, SWE | mypy gated in `make check` | proven | keep | - |
| Write and run tests | entry | all, QA | `tests/` (435), pytest, 91.5% | proven | keep | - |
| Integration/E2E testing | mid | SWE, QA | `scripts/e2e_smoke.py`, `make smoke`, `e2e/` Playwright (CI) | proven | keep | - |
| Git/GitHub team workflow | mid | all | branch protection, PR flow, PRs #17-24 | proven | keep | - |
| CI/CD pipelines | mid | DevOps, SWE | GH Actions (check/docker/CodeQL required) | proven | keep | - |
| Docker + deploy | mid | DevOps, SWE | Dockerfile, CI smoke, Render live demo | proven | keep | - |
| Security + supply chain | mid-sr | SWE, DevOps | Scorecard, SBOM, CodeQL, bandit, secrets | proven | keep | - |
| Reusable tooling | mid | tools, SWE | Hardware Store, `make deps`, forge-audit | proven | keep | - |
| Diagnostics/observability | mid | DevOps, QA | `doctor`, `inspect`, `bench`, reports | proven | keep | - |
| Explain trade-offs | mid-sr | SWE | ADRs, `tooling_strategy.md`, pioneer docs | proven | keep | - |
| REST API design + docs | mid | backend, full-stack | FastAPI + `/api/status` + `/docs` OpenAPI (`parts/dashboard.py`) | proven | keep | - |
| Frontend (HTML/CSS/JS) | mid | full-stack | server-rendered dashboard (`parts/dashboard.py`, HTMX, e2e) | proven | keep | - |
| **React/Next.js + TypeScript** | mid | full-stack | none | **planned** | separate `codeforge-web` flagship | P2 |
| Relational DB (PostgreSQL) | mid | backend, full-stack | SQLite default; Postgres seam shipped (`DATABASE_URL`, `psycopg`, Alembic) | proven | keep | - |
| Accessibility (a11y) | mid | full-stack | dashboard a11y: skip link, aria labels, focus-visible, `lang` (`parts/dashboard.py`) | proven | keep | - |
| Cloud beyond a demo | mid-sr | DevOps | Render demo only | partial | deferred by design (see DEVELOPMENT_PLAN) | P3 |
| Mentorship/teaching artifacts | sr | lead | Classroom, `assessment`, docs | partial | more tutorial content | P3 |
| Collaboration signal (issue->PR->merge) | mid | all | PR flow live; templates added | partial | one linked issue -> PR -> merge | P1 |

## Reading this matrix

- **codeforge's spine is proven** for Python developer / SWE / QA-automation / DevOps-tools
  targets. Those roles are well-served today.
- The **full-stack developer** target (the chosen priority) has its **frontend proof** shipped:
  the server-rendered FastAPI dashboard (`parts/dashboard.py`, HTMX, a11y, e2e) with a visible
  **API contract** (`/api/status`, `/docs` OpenAPI). The remaining full-stack lever is the
  **React/TS second flagship** (P2, a separate `codeforge-web` repo).
- Nothing here is marked proven without a real artifact; `partial`/`planned`/`missing` are
  used honestly so the board names its own gaps.
