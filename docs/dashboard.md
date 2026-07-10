# The readiness dashboard (the Lens)

`parts/dashboard.py` is CodeForge's first full-stack proof: a read-only web page that
projects the forge's own evidence, the career board, the QualityGate audit, the hardware
store, and the latest performance run, onto a server-rendered HTML dashboard, with a JSON
twin at `/api/status`. It is the portfolio-facing answer to the 2026 full-stack expectation
(see `docs/research/full_stack_python_requirements.md`).

## What it shows

Four cards, each computed live from real repo state (never hardcoded):

| Card | Source | Headline |
|---|---|---|
| Career evidence | `parts/career.load_board` + `unproven_claims` (VeritasGate) | proven / total skills |
| QualityGate audit | `parts/qualitygate.gate_all` | pass / total filed objects |
| Hardware store | `parts/hardware.load_catalog` | reusable part count |
| Performance | latest `reports/performance/*.md` (from `make bench`) | engine-tick throughput |

## How to run it

```bash
codeforge api          # serves the FastAPI app on :8000
# then open http://localhost:8000/           (the dashboard)
#            http://localhost:8000/api/status (the JSON twin)
#            http://localhost:8000/docs       (OpenAPI, auto-generated)
```

## Design decisions

- **Frameless, on purpose.** The page is rendered with stdlib `html.escape` and f-strings,
  no template engine (no Jinja, no new dependency). This keeps the frameless-Python identity
  (`docs/frameless_python.md`) intact while still proving semantic HTML5 + responsive,
  accessible CSS. The dependency ledger stays unchanged; `make deps` needs nothing new.
- **State is canonical; text is a projection** (architecture law 1). The dashboard only
  reads; it never mutates world state. One `Snapshot` feeds both the HTML page and the JSON,
  so the two surfaces can never disagree.
- **Fails honest, never fatal** (VeritasGate). If a source will not load, its card renders a
  red `fail` badge carrying the error, instead of returning a 500 or hiding the gap. A
  dashboard that lies by omission is worse than one that shows a broken card.
- **The JSON twin is a seam.** `/api/status` is the read-only contract a future
  Next.js/React/TypeScript front end (the planned second flagship, see
  `docs/full_stack_readiness_checklist.md`) would consume, matching the research's separated
  front/back architecture.
- **Accessibility basics:** `lang="en"`, a skip link, semantic `header/nav/main/section/
  footer`, `aria-label`led regions, `:focus-visible` outlines, and status conveyed by a text
  badge (`OK/WATCH/FAIL/INFO`), never color alone.

## What it does NOT do (scope discipline)

It is read-only, unauthenticated, and additive: it mounts on the existing admin API
(`parts/api.py`) and touches no MUD-engine core. Mutations still live behind the
owner-authenticated `@`-verbs and `POST /admin/*`. A browser/E2E test layer and the
React/TypeScript front end are the next phase, tracked in the full-stack readiness checklist.
