# Framework decision matrix

*Companion to `docs/full_stack_forge_decision.md`. Scores the candidate architecture paths
on a 1-5 scale (1 weak, 5 excellent; complexity and bloat-risk scored so higher = safer),
composited across the fifteen decision criteria. Judgment, not measurement - a decision aid.*

## Architecture paths

| Path | Composite | Best use | Main risk | Career value | CodeForge value | Verdict |
|---|---|---|---|---|---|---|
| Custom core + FastAPI web | **4.3** | API + dashboard + WebSockets | async depth is real work | Backend, API, OpenAPI | Already load-bearing | **use_now** (extend) |
| Static Blueprint renderer | **4.3** | Blueprint -> HTML/CSS | none material | HTML/CSS, portfolio | The missing spine | **prototype_now** -> built |
| Hybrid | **4.5** | The whole forge | scope creep | Highest | Its actual identity | **use_now** (the frame) |
| Flask lightweight web | 2.9 | small dashboards | duplicates FastAPI | Low here | Redundant | **do_not_use_yet** |
| Django full web forge | 2.8 | data/admin app | replaces custom core | High (generic) | Premature | **research_more** |
| Twisted / Evennia MUD-first | 2.2 | persistent MUD net | erases the differentiator | Niche | Identity risk | **study_only** |

## The criteria (why the scores land where they do)

Architectural fit, hiring-market value, portfolio clarity, learning value, implementation
complexity, maintainability, MUD fit, full-stack fit, AI/GPT-NPC fit, blueprint/rendering
fit, testing friendliness, documentation friendliness, ritual integration, seed-generation
fit, risk of tool bloat.

- **Hybrid wins** because it keeps the custom tick (the portfolio thesis) while letting
  FastAPI carry the web layer it already carries - highest on fit, career value, and
  full-stack fit, only dinged on complexity and bloat-risk (managed by the approval gate).
- **Custom core + FastAPI** and **static renderer** tie just behind: the first is already
  real; the second is the cheapest, safest net-new proof. Together they *are* the hybrid,
  one rung further along.
- **Flask** scores mid but is redundant: adding a second web framework alongside FastAPI is
  pure bloat, so its verdict is `do_not_use_yet` regardless of composite.
- **Django** is marketable but premature - it would replace a custom core that already meets
  the data need via SQLAlchemy. Revisit when real admin/auth/forms/multi-user needs appear.
- **Twisted/Evennia** scores lowest on architectural fit: adopting them would replace the
  one thing that makes this repo the owner's. Study the patterns, keep the custom engine.

## Tool status labels

`use_now`: custom Python core, FastAPI, WebSockets, text + dashboard rendering.
`prototype_now`: static Blueprint HTML/CSS renderer, Markdown rendering (both built).
`research_more`: Django / Django-admin, plugin architecture, a live LLM brain inside codeforge.
`integrate_later`: HTMX, Jinja (only if template complexity grows).
`study_only`: Evennia, Twisted.
`do_not_use_yet`: Flask (redundant with FastAPI), React/TypeScript in-repo (planned as a
separate flagship).

## The adoption gate (every new framework must pass)

What problem does it solve? Why is custom Python not enough? What hiring skill does it prove?
How does it fit the architecture? How will it be tested and documented? How does it affect
the Ritual? Can it be removed later? What is the smallest safe experiment? A weak answer on
need, skill, or removability defaults the tool to `research_more` / `study_only`.
