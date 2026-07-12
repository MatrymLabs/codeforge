.PHONY: env fix lint typecheck test property coverage audit security secrets deps sbom bench doctor patch daily check readiness truth cast-plan smoke repo-integrity ship run world store hardware clean serve db-up db-down db-migrate docs-serve docs-build e2e evolution ritual-fast ritual ritual-down unskew

# --- Environment: create/validate the .venv, fail loud on version mismatch.
# Uses uv when present (a Rust resolver; measured ~20x faster than pip on this host:
# 85s -> 4s) and falls back to plain venv+pip, so bootstrap never hard-requires uv. ---
env:
	@if command -v uv >/dev/null 2>&1; then \
		echo "→ uv found - fast env build"; \
		uv venv .venv --clear --python 3.13; \
		uv pip install --python .venv/bin/python -q -e ".[dev]"; \
	else \
		echo "→ uv not found (using pip). Install uv for a ~20x faster env: https://docs.astral.sh/uv/"; \
		python3 -m venv .venv; \
		.venv/bin/pip install -q --upgrade pip; \
		.venv/bin/pip install -q -e ".[dev]"; \
	fi
	@.venv/bin/python -c "import sys; assert sys.version_info[:2] >= (3, 13), 'need Python >= 3.13'"
	@echo "✓ .venv ready - activate with: source .venv/bin/activate"

# --- Mutators: run these while working ---
fix:
	ruff format .
	ruff check . --fix

# --- Gates: pure checks, cheapest first, nothing is modified ---
lint:
	ruff format --check .
	ruff check .

typecheck:
	mypy parts tests forge.py

test:
	pytest -m "not property"

property:
	pytest -m property

# The full gate. `coverage` runs the WHOLE suite (property included) once, WITH
# instrumentation and the threshold -- so `check` covers, tests, and gates in a single
# suite run instead of two. `test`/`property` remain as fast, focused, no-coverage
# targets for the inner dev loop; `make ritual-fast` is the ~1s preflight.
check: lint typecheck coverage

# --- Readiness: the global self-audit -- registry validates (gates), then the
# project dashboard, computed from the registry + QualityGate. Read-only. ---
readiness:
	@python3 -c "import sys; from parts.registry import load_collective, validate, unfiled_modules; from parts.pm import pm_status; r=load_collective(); p=validate(r)+['unfiled module (not in the registry): '+m for m in unfiled_modules(r)]; print('Registry: CLEAN (no duplicates, no orphans, every module filed)' if not p else 'Registry PROBLEMS:\n  '+'\n  '.join(p)); print(); print(pm_status()); sys.exit(1 if p else 0)"

# --- Repo integrity: one honest repo-health report (code quality + security +
# provenance + registry + docs + truth), composed from checks we already own.
# Detects tools; a missing one is reported not_configured, never faked. ---
repo-integrity:
	@python3 -m parts.integrity

# --- Cast: plan a standalone game project ("cast") poured from a seed pack + the engine.
# Dry run -- lists what it WOULD copy and the manifest it WOULD write; writes nothing.
# Usage: make cast-plan TEMPLATE=fantasy_mud NAME=Aethris (see docs/seed_architecture.md). ---
cast-plan:
	@python3 -m parts.cast $(or $(TEMPLATE),blank_mud) $(or $(NAME),Demo) $$(git rev-parse --short HEAD 2>/dev/null || echo unknown)

# --- Truth: VeritasGate -- check the project's claims correspond to reality
# (overclaims, drift-prone counts, docs, registry, QA board). Exit 1 on any
# FLAGGED claim, so the ritual and CI fail loud on drift. Same as the in-MUD
# `truth check`, reachable from a script. ---
truth:
	@python3 -m parts.veritas

# --- Smoke: the whole engine end-to-end over a live socket -- start -> log in
# -> look -> check -> do -> log out -> bank the forge. Isolated (own port + temp
# DB) and timed. Exit 0 == every live step passed. ---
smoke:
	@python3 scripts/e2e_smoke.py

# Blueprint Evolution Lab: run the demo bake-off and file evidence to reports/evolution/.
# The authorized execution path (the MUD `evolution` command is read-only). Nothing is promoted.
evolution:
	@python3 scripts/evolution_demo.py

# --- Extra inspections (One-Button Rule) ---
# `-n auto` fans the suite across cores (pytest-xdist); pytest-cov combines the per-worker
# data. The suite is ~95% of check's runtime, so this is the one real speed lever. The
# inner-loop `test`/`property` targets stay serial for readable, debuggable output.
coverage:
	pytest -n auto --cov=parts --cov=forge --cov-branch --cov-report=term-missing --cov-report=xml --cov-fail-under=85

audit:
	pip-audit --skip-editable

# --- SBOM: a CycloneDX software bill of materials (SSDF supply-chain evidence).
# Generated from the installed environment; the output is git-ignored (reproducible
# from the recorded commit), the README/CI advertise that it is produced. ---
sbom:
	@mkdir -p reports/security
	cyclonedx-py environment -o reports/security/sbom.cdx.json
	@echo "✓ SBOM -> reports/security/sbom.cdx.json"

# SAST + dependency CVEs. bandit gates; audit is informational (see doctor).
security:
	bandit -c pyproject.toml -r parts forge.py -q
	pip-audit --skip-editable
	@git ls-files | xargs detect-secrets-hook --baseline .secrets.baseline

# --- Secret scan: fail on any tracked secret not in the audited baseline.
# Regenerate the baseline after auditing: detect-secrets scan --exclude-files '\.venv/' > .secrets.baseline ---
secrets:
	@git ls-files | xargs detect-secrets-hook --baseline .secrets.baseline

# --- Dependency gate: every declared dependency must have a justification row in
# dependency_ledger.toml (the Dependency Approval Rule, frameless Python). Fails loud
# on an unjustified dependency; warns on a stale ledger row. Stdlib only (tomllib). ---
deps:
	@python -m parts.dependencies

# --- Bench: measure the engine tick (handle_command) throughput + latency and file a
# dated performance-evidence report under reports/performance/. Frameless (stdlib). ---
bench:
	@python -m parts.bench

# --- Doctor: run the gates read-only, stop at the first failure, prescribe the fix ---
doctor:
	python3 scripts/doctor.py

# --- Security patches: scan deps for CVEs, apply available fixes, then RE-VERIFY.
# Files a dated audit under security-evidence/. Detect + fix are best-effort
# (need network); the re-run of `make check` is the hard safety net - if a patch
# breaks the build, the ritual fails loud (recover with `make env`). ---
patch:
	@mkdir -p security-evidence
	@echo "→ scanning Python dependencies for known CVEs..."
	-pip-audit --skip-editable -f json -o "security-evidence/$$(date -u +%Y-%m-%d)-pip-audit.json"
	@echo "→ applying available security fixes (pip-audit --fix)..."
	-pip-audit --fix --skip-editable
	@echo "→ re-verifying the patched environment..."
	$(MAKE) check
	@echo "✓ security patch cycle complete (evidence: security-evidence/)"

# --- Daily ritual: apply security patches (+re-verify), then check federal
# guidance for updates and file them in the library. Point FGL_HOME at it. ---
FGL_HOME ?= ../federal-guidance-library
daily: patch
	@echo "→ checking federal guidance for updates..."
	@if [ -x "$(FGL_HOME)/.venv/bin/library" ]; then \
		( cd "$(FGL_HOME)" && .venv/bin/library check ) || echo "  (reg check reported changes or was offline)"; \
	else \
		echo "  library not runnable at $(FGL_HOME) - run 'make env' there to enable the daily reg check"; \
	fi
	@echo "✓ daily ritual complete"

# --- Ship: gates, then open the PR. main is protected (require PR + CI), so shipping
# means pushing THIS branch and opening a pull request -- never a direct push to main.
# Refuses dirty trees, red gates, and shipping from main itself. ---
ship: check
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo ""; \
		echo "✗ Uncommitted changes detected. Commit first, then ship:"; \
		git status --short; \
		exit 1; \
	fi
	@branch="$$(git rev-parse --abbrev-ref HEAD)"; \
	if [ "$$branch" = "main" ]; then \
		echo "✗ You are on main, which is protected. Ship from a branch:"; \
		echo "    git checkout -b feat/your-change   # then commit and 'make ship'"; \
		exit 1; \
	fi; \
	echo "→ pushing '$$branch' and opening its PR..."; \
	git push -u origin "$$branch"; \
	if command -v gh >/dev/null 2>&1; then \
		gh pr view >/dev/null 2>&1 && gh pr view || gh pr create --fill; \
	else \
		echo "  gh not found -- open a PR for '$$branch' on GitHub."; \
	fi
	@echo "✓ Branch pushed + PR ready. Merge after CI is green (check · docker · CodeQL)."

# --- Conveniences ---
run:
	python3 forge.py

world:
	python3 -m parts.catalog

store:
	python3 -m parts.store

hardware:
	python3 -m parts.hardware

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage __pycache__ parts/__pycache__ tests/__pycache__

serve:
	codeforge serve

# --- PostgreSQL: the production-shaped backend. SQLite stays the zero-config default;
# these bring up a local Postgres and run the Alembic migrations against DATABASE_URL.
# See docs/database.md. ---
db-up:
	docker compose up -d db

db-down:
	docker compose down

db-migrate:
	@alembic upgrade head

# --- Docs site: build docs/ into the public GitHub Pages site (mkdocs-material). ---
docs-serve:
	mkdocs serve

docs-build:
	mkdocs build --strict

# --- E2E: drive the live dashboard with a real browser (isolated from `make check`). ---
e2e:
	@python -m playwright install chromium
	pytest e2e -q

# --- The Ritual: one command lights the whole workshop -- gates run, GitHub
# mirrors, the forge lights, the MUD window opens at the front desk. Bound to
# the phrase "start the ritual" via a shell function (see docs/RUNNING.md). ---
# --- Ritual, Fast: the ~1s preflight -- critical checks only (imports · registry ·
# truth), quality checks WARN, no suite/network/scans. Green/yellow/red gate to enter
# and code. Run `make ritual` (standard) or the deep battery before a push or demo. ---
ritual-fast:
	@bash scripts/ritual_fast.sh

ritual:
	@bash scripts/ritual.sh

# --- The Ritual, Closed: secure the workshop at day's end -- bank any forge on
# :4000, stop containers, muster uncommitted/unpushed work. Bound to the phrase
# "complete the ritual". ---
ritual-down:
	@bash scripts/ritual_down.sh

unskew:
	git ls-files | xargs touch
