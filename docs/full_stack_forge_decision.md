# Full-Stack Forge: framework decision (filed)

*Decision report, 2026-07-10. Frames how CodeForge evolves into a full-stack development
forge without becoming dependency soup. Companion: `docs/framework_decision_matrix.md`
(the scored matrix) and `docs/blueprint_renderer.md` (the first build).*

## The reframe

"Frameless Python" was never "never use frameworks." The working doctrine is
**architecture-first Python: frameworks are professional tools that must earn their place.**
The question is not "should CodeForge use no frameworks?" but "which framework belongs in
which layer, for what purpose, with what proof, and with what career value?" That gate is
the Dependency Approval Rule (`docs/tooling_strategy.md`).

## Ground truth (what already exists)

CodeForge is already on the hybrid path, not starting from zero:

- **Custom Python core** (the `handle_command` tick) is the one door. Four thin drivers:
  solo terminal, stdlib TCP gateway, asyncio WebSocket browser gate, and HTTP.
- **FastAPI is already integrated and ledger-justified** across three surfaces:
  `parts/api.py` (admin API), `parts/web_gateway.py` (WebSocket play), and
  `parts/dashboard.py` (the readiness dashboard: `GET /` + `GET /api/status` + `/docs`).
- **Persistence:** SQLAlchemy 2.0 / SQLite. **Content:** YAML seeds. Five runtime deps,
  each justified in `dependency_ledger.toml`. No LLM SDK, no template engine.
- **Gaps:** there was no Blueprint model and no Blueprint renderer (both aspirational
  "coming" markers). The Architect NPC is a **scripted, advisory-only** `LocalArchitect`
  (a swappable seam for a future Claude brain, not an LLM today). The real LLM lives in the
  sibling `ai-log-triage` repo, behind a mockable boundary.

## The decision

- **Best short-term path:** the **Professional Hiring Path** - build the Blueprint ->
  static-HTML renderer as **custom Python**, surfaced through the FastAPI dashboard already
  shipped. Zero new dependencies.
- **Best long-term path:** the **Hybrid** - custom core + FastAPI service/API layer +
  custom renderers + (later, only if justified) HTMX for interactivity and a *separate*
  React/TypeScript flagship.

## Tool verdicts (VeritasGate-honest labels)

| Tool | Verdict | Why |
|---|---|---|
| Custom Python core | `use_now` | The identity; the tick is the differentiator. |
| FastAPI | `use_now` | Already integrated, justified, tested (API + WS + dashboard). |
| Static Blueprint HTML/CSS renderer | `prototype_now` -> built | The missing spine; frameless, testable, portfolio-visible. |
| WebSockets | `use_now` | Already in the browser gate. |
| HTMX | `integrate_later` | Phase-3 interactivity without a JS build. |
| Jinja templates | `research_more` | Stdlib rendering suffices; adopt only if template complexity grows. |
| Django / Django admin | `research_more` | No data/admin/auth need SQLAlchemy doesn't already meet. |
| Flask | `do_not_use_yet` | A second web framework is bloat when FastAPI fills the niche. |
| Evennia / Twisted | `study_only` | Would replace the custom tick; learn from, don't clone. |
| React / TypeScript | `do_not_use_yet` in-repo | Planned as a separate second flagship (full-stack-developer target). |
| Live LLM brain in codeforge | `research_more` | Keep the LLM in `ai-log-triage`; wire the Architect seam only when justified. |

## What stays custom / what uses a framework

- **Custom:** the tick, command spine, world state, seeds, rituals, QA gates, Classification
  Registry, the Blueprint model/validator/renderer, and text rendering. These *are* the thesis.
- **Framework:** FastAPI, for API/WS/dashboard. That is the entire framework story for now.

## Recommended demo (under 60 seconds)

`play` -> `talk architect` -> describe a feature -> `blueprint show <id>` ->
`blueprint render <id>` -> open the dashboard. One clip proves Python architecture, HTML/CSS,
automation, testing, and AI-assisted-but-honest ownership.

## Honesty notes

- The Architect NPC is **prototype** (scripted advisory), not "GPT-powered." Blueprints are
  authored from the operator's words, not generated - so no autonomous-coding claim is made.
- Rendered Blueprint HTML is **regenerable evidence** under `reports/blueprints/`
  (git-ignored); the JSON record is the single source of truth.
- Django, Evennia, and React are **research_only / planned** here, never presented as built.
