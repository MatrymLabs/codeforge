# Python Developer Hiring Requirements (2026 research)

*Source: owner research "Current Python Developer Hiring Requirements and GitHub Portfolio
Design" (ChatGPT, dated 2026-07-10), captured here per the repo's First Rule (use my
research). This is a faithful synthesis, not a claim of primary authority (Tier-4).*

## Market shape

- The market is **"Python plus an adjacent specialization,"** not a single canonical title.
  Roles span Python Developer, Backend Engineer, Software Engineer II, Platform Engineer,
  Full-Stack Engineer, and AI/ML Engineer.
- Title-based searches undercount the real market; the repeatable technical baseline is
  **Python + APIs + SQL/PostgreSQL + Git + automated testing + CI/CD + cloud familiarity**,
  with Docker/Kubernetes common at mid/senior levels.

## The recurring technical baseline

| Skill area | What postings ask | What it means for a candidate |
|---|---|---|
| Core programming | Strong Python; SQL + relational DBs (esp. PostgreSQL) | Data modeling, queries, debugging, production code structure, not just scripting |
| Web / API | REST recurring; GraphQL some; Django/Flask/FastAPI named | Design and explain API contracts, request/response models, validation, error handling |
| Full-stack adjacency | JS/TypeScript + React beside Python at mid/senior | Even backend roles: basic comfort with adjacent frontend improves marketability |
| Testing / quality | pytest, unittest, TDD, integration tests, review, gates | Testing is part of the definition of professional work, not "nice to have" |
| Delivery tooling | Git, CI/CD, GitHub Actions | Evidence you work inside team workflows, not just locally |
| Cloud / containers | AWS most; Azure/GCP; Docker/Kubernetes | Understand deployment and operational trade-offs |
| Data / AI | RAG, LLM APIs, ELT/ETL, vector retrieval | AI familiarity is a differentiator layered on engineering, not a replacement |
| Reliability / security | observability, SLIs/SLOs, authN/authZ, OWASP | Seniors judged on preventing operational/security problems |

## Seniority = scope and ownership (not years)

- **Junior (0-2y):** write/debug well-scoped code, use Git, follow testing, learn frameworks
  under guidance. Coursework/internships/capstones can substitute for full-time experience.
- **Mid (2-5y):** own features end-to-end, build APIs, design schemas, write automated tests,
  work with CI/CD + cloud + containers, less supervision.
- **Senior (5+y):** system design, distributed systems, observability, security, mentor,
  influence architecture and process.

## Soft skills are explicitly named

Communication across technical/non-technical audiences, cross-functional collaboration,
problem-solving, ownership, mentorship, tactful code review. Typed, documentable Python is
increasingly a professional expectation (type hints + static analysis as a stronger signal
than a few years ago).

## Implications for CodeForge

- The baseline (Python + tests + CI + Docker + typed code + Git workflow) is **already met**
  and hardened (see the hiring matrix). The differentiators to target are the **frontend/
  full-stack proof** and a visible **API contract**.
- "Ownership end-to-end" is provable here: seed -> spark -> world, plus the self-audit stack.
