# GitHub Portfolio Requirements (2026 research)

*Source: owner research "Current Python Developer Hiring Requirements and GitHub Portfolio
Design" (ChatGPT, dated 2026-07-10), captured per the First Rule. Faithful synthesis (Tier-4).*

## The core principle

A GitHub portfolio works when it **reduces evaluator effort**. The hiring signal is not repo
count; it is **how fast a reviewer can understand, run, trust, and discuss your work.** A
repo should prove three things quickly: you can build something real, explain it, and
maintain it with professional workflow habits.

## The ideal-repo checklist (from the research)

| Item | Ideal standard |
|---|---|
| Clear README | Title, one-paragraph value prop, architecture sketch, setup, run/test commands, screenshots/demo, roadmap, contact/help links |
| Fast setup path | A reviewer can clone and run in minutes with copied commands |
| Strong project selection | 4-6 polished repos over volume (GitHub pins max 6); each a deliberate signal |
| Production-style layout | Separate `src/` (or package), `tests/`, `docs/`, `.github/`, `pyproject.toml`; not everything dumped in root |
| Tests | Unit minimum; integration for APIs/data pipelines; pytest common |
| Linters/formatting | ruff/black, pre-commit; fail CI on style breakage |
| Type hints + static analysis | Type hints in nontrivial code; mypy/pyright |
| CI badge + workflow | GitHub Actions for tests/lint; status badge near the top |
| Descriptive commits | Coherent narrative, one concept per branch; avoid WIP/fix/"misc changes" |
| PR hygiene | Even solo: sample PRs stating purpose, approach, screenshots/logs |
| Issue tracking | At least a bug + feature-request template on serious repos |
| License | A standard OSI license (a public repo without one is not truly open source) |
| Contribution guidance | CONTRIBUTING.md: setup, branch naming, test/lint commands, expectations |
| Topics/discoverability | Language, framework, domain, deployment topics (python, fastapi, docker, postgresql) |
| Profile presentation | Profile README, pinned best work, short outcome-focused repo descriptions |
| Interview/demo artifacts | Demo GIF/video, architecture diagram, sample API calls, benchmark, test evidence, short trade-offs section |

## The six-question README (recommended order)

1. What is this? 2. Why does it matter? 3. How do I run it? 4. How do I test it?
5. What design choices did I make? 6. What should I look at in an interview/demo?

## Curation over volume

A stronger portfolio tells a coherent story about the kind of engineer you are becoming.
Every pinned repo should be a deliberate signal, not a half-finished experiment. Exemplary
models (for *reviewer experience*, not scale): FastAPI, Flask, Requests, Pydantic,
scikit-learn, strong README, visible tests/docs/workflow/contributor-guidance/quality signals.

## Badges must be truthful

One passing badge for tests and one for lint is more persuasive than a wall of decorative
badges. Never show a CI/coverage badge a repo has not earned.

## Implications for CodeForge

See `docs/github_portfolio_checklist.md` for the honest checked/unchecked pass. Short version:
codeforge already meets most items after the tooling-hardening work; the open items are
**issue templates** (now added) and the **frontend/demo-artifact depth**.
