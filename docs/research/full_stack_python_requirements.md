# Full-Stack Python Requirements (2026 research)

*Source: owner research "Python Full-Stack Implementation and GitHub Repository Design for
Job-Oriented Developers" + "Python Full-Stack Implementation Research" (ChatGPT, dated
2026-07-10), captured per the First Rule. Faithful synthesis (Tier-4).*

## The key finding

**"Python full-stack" does not mean Python everywhere.** Python runs on the server; the
browser uses **HTML, CSS, JavaScript, and (increasingly) TypeScript**. Python-only browser
frameworks exist (Reflex, PyScript, Streamlit) but are specialized accelerators, not a
replacement for learning mainstream web technologies.

## Recommended stacks (by scenario)

| Best-fit scenario | Recommended stack | Why |
|---|---|---|
| Traditional business web app, admin/CRUD | **Django + PostgreSQL + HTMX** | Fastest path to a real product; batteries-included auth/forms/admin/security |
| Modern product UI, separated front/back | **Next.js + React + TypeScript ↔ FastAPI + Pydantic + SQLAlchemy + PostgreSQL** | Best match for mainstream employer expectations; clean front/back separation |
| Small internal service / focused API | Flask + SQLAlchemy + Alembic | Lean and explicit; more architecture decisions on you |
| Data / AI demo | Streamlit | Fastest interactive data app |
| Pure-Python browser experiment | PyScript / Reflex | Niche; not a replacement for web fundamentals |

Primary job-facing recommendation: **Next.js/React/TypeScript front end + FastAPI/Pydantic/
SQLAlchemy/Alembic/PostgreSQL back end.** Fastest-to-product alternative: Django + HTMX.

## What each side owns

- **Front end** (a software subsystem, not "make it pretty"): layout/navigation, forms,
  tables, dashboards, responsive behavior, validation + helpful errors, application state,
  auth screens, **accessibility**, loading/empty/success/failure states, calling the API,
  browser tests.
- **Back end** (authoritative): business rules, accounts, authN/authZ, DB access, input
  validation, API endpoints, background processing, audit logs, security controls,
  WebSockets/real-time, logging/monitoring, migrations.
- **Both validate**, for different reasons: front-end for usability/feedback, back-end for
  security/correctness/integrity. Hiding a button does not secure the endpoint.

## The layering rule (design discipline)

Do not scatter API calls through every visual component. Layer them:

```
Page -> Feature component -> Service / API client -> Python API
```

Back end mirror: `Route -> input-schema validation -> authorization -> service ->
domain rules -> repository/ORM -> PostgreSQL -> response schema -> JSON`. The route stays
thin (receive, validate, call service, return).

## Five deliverable categories employers judge

1. Ship browser-visible features + server logic together.
2. Produce and document APIs (contracts, models, validation, errors).
3. Write tests and quality gates.
4. Deploy or at least containerize and configure.
5. Explain trade-offs clearly (Django vs FastAPI vs Flask vs HTMX vs Streamlit).

## Baseline toolchain (already in CodeForge)

pytest, Ruff, mypy, coverage, pre-commit/CI, Docker, GitHub Actions, structured logging,
environment-based config. PostgreSQL recommended for a production-style portfolio (codeforge
uses SQLite via SQLAlchemy, a deliberate embedded choice, see the readiness checklist).

## CodeForge decision (from the pioneer questions, 2026-07-10)

- **First full-stack proof:** a **read-only web dashboard served by the existing FastAPI**,
  rendering real codeforge data (career board, QA board, hardware store, perf report) with
  semantic HTML + responsive, accessible CSS. Proves HTML/CSS + backend/frontend separation
  without a JS build system or abandoning frameless Python.
- **Placement:** an in-repo add-on module (portfolio-facing surface), not MUD-engine core.
- **Data:** real, wired to the actual renderers (truthful, VeritasGate-consistent).
- **Hiring target:** **full-stack developer**, so a **Next.js/React/TypeScript second
  flagship** (a separate repo consuming a codeforge JSON API) is the planned next phase.
