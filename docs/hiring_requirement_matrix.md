# Hiring Requirement Matrix (CodeForge)

*Maps 2026 hiring requirements (`docs/research/`) to concrete repo evidence. Status:
proven / partial / missing / planned. VeritasGate: "proven" requires a cited artifact that
exists. Last audited: 2026-07-10. Primary target: full-stack developer.*

| Requirement | Level | Role relevance | Repo evidence | Status | Next task | Priority |
|---|---|---|---|---|---|---|
| Maintainable, readable Python | entry | all | `parts/`, ruff, forge voice | proven | keep | - |
| Type hints + static analysis | entry-mid | Python dev, SWE | mypy gated in `make check` | proven | keep | - |
| Write and run tests | entry | all, QA | `tests/` (435), pytest, 91.5% | proven | keep | - |
| Integration/E2E testing | mid | SWE, QA | `scripts/e2e_smoke.py`, `make smoke` | proven | add dashboard E2E | P2 |
| Git/GitHub team workflow | mid | all | branch protection, PR flow, PRs #17-24 | proven | keep | - |
| CI/CD pipelines | mid | DevOps, SWE | GH Actions (check/docker/CodeQL required) | proven | keep | - |
| Docker + deploy | mid | DevOps, SWE | Dockerfile, CI smoke, Render live demo | proven | keep | - |
| Security + supply chain | mid-sr | SWE, DevOps | Scorecard, SBOM, CodeQL, bandit, secrets | proven | keep | - |
| Reusable tooling | mid | tools, SWE | Hardware Store, `make deps`, forge-audit | proven | keep | - |
| Diagnostics/observability | mid | DevOps, QA | `doctor`, `inspect`, `bench`, reports | proven | keep | - |
| Explain trade-offs | mid-sr | SWE | ADRs, `tooling_strategy.md`, pioneer docs | proven | keep | - |
| REST API design + docs | mid | backend, full-stack | FastAPI admin surface | partial | surface OpenAPI + `/api/status` | P1 |
| **Frontend (HTML/CSS/JS)** | mid | full-stack | one gateway HTML page | **missing** | build FastAPI dashboard | **P1** |
| **React/Next.js + TypeScript** | mid | full-stack | none | **planned** | separate `codeforge-web` flagship | P2 |
| Relational DB (PostgreSQL) | mid | backend, full-stack | SQLite via SQLAlchemy | partial | document seam; Postgres optional | P3 |
| Accessibility (a11y) | mid | full-stack | none yet | planned | in the dashboard (labels/focus/keyboard) | P1 |
| Cloud beyond a demo | mid-sr | DevOps | Render demo only | partial | deferred by design (see DEVELOPMENT_PLAN) | P3 |
| Mentorship/teaching artifacts | sr | lead | Classroom, `assessment`, docs | partial | more tutorial content | P3 |
| Collaboration signal (issue->PR->merge) | mid | all | PR flow live; templates added | partial | one linked issue -> PR -> merge | P1 |

## Reading this matrix

- **codeforge's spine is proven** for Python developer / SWE / QA-automation / DevOps-tools
  targets. Those roles are well-served today.
- The **full-stack developer** target (the chosen priority) has two P1 gaps: the **frontend
  proof** (FastAPI dashboard, in progress) and a **visible API contract**. The React/TS
  second flagship is the P2 that most moves the full-stack needle after the dashboard.
- Nothing here is marked proven without a real artifact; `partial`/`planned`/`missing` are
  used honestly so the board names its own gaps.
