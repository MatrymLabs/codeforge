# Template: Full-stack (Python backend + JS/TS front end)

**Use when:** a Python service grows a browser front end that is more than a single served HTML
page. **Status for CodeForge:** planned, not present. CodeForge today serves one page from the
browser gate (`parts/web/*.html`, shipped inside the wheel); that does not warrant a `frontend/`
tree. This template is the starting point if a real React/TS client is ever built.

## Layout

```text
README.md                     # overview, stack, how to run both halves
LICENSE
backend/
  pyproject.toml              # backend build + tool config
  src/ or app/                # FastAPI/Flask app code
  tests/                      # backend tests (pytest)
  Dockerfile                  # backend container
frontend/
  package.json                # name, scripts, deps
  tsconfig.json               # target, outDir, include ["src/**/*"]
  src/                        # React/TS source
  public/                     # static assets (index.html, images)
  tests/                      # component tests (Jest / RTL)
docker-compose.yml            # multi-service: db + backend + frontend
.github/workflows/ci.yml      # one pipeline, jobs for BOTH halves
```

## Boundaries

- **Two manifests, two toolchains.** `backend/pyproject.toml` and `frontend/package.json` each
  own their half; neither reaches across. The root holds only what spans both (compose, CI,
  README, LICENSE).
- **CI runs both.** A single `.github/workflows/ci.yml` with separate jobs: Python lint + mypy +
  pytest, and JS lint (eslint/prettier) + type-check (tsc) + test (jest). Both gate the merge.
- **The seam is HTTP.** The front end talks to the backend only over the API; no shared imports.
  Tests on each side mock the other (consistent with the ship's "boundaries are seams" rule).

## How this maps onto CodeForge if adopted

- The existing FastAPI admin surface + browser gate becomes `backend/` (or stays `parts/` and a
  thin `frontend/` is added beside it - decided in the adopting ADR).
- The **World Package** could gain a web viewer here; today it renders in-MUD only.
- Adopting this is a critical juncture: new toolchain (Node), new dependency class, new CI jobs -
  it earns an ADR, a dependency-ledger entry, and Josh's approval before a single folder lands.
