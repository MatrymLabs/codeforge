.PHONY: hooks env fix lint typecheck test property fuzz coverage audit audit-runtime security sast secrets deps sbom bench trend ai-eval retention doctor patch daily check readiness arc-verdicts truth forge cast-plan cast cast-selective cast-install-check coupling shelf-pour shelf-build smoke repo-integrity ship run world store hardware clean serve backup db-up db-down db-migrate docs-serve docs-build demo-gif e2e evolution ritual-fast ritual ritual-down unskew loop

# --- Environment: create/validate the .venv, fail loud on version mismatch.
# Uses uv when present (a Rust resolver; measured ~20x faster than pip on this host:
# 85s -> 4s) and falls back to plain venv+pip, so bootstrap never hard-requires uv.
# With uv, `sync` installs the exact pinned graph from uv.lock (reproducible builds);
# the pip fallback still resolves fresh -- best-effort without the resolver. ---
env: hooks
	@if command -v uv >/dev/null 2>&1; then \
		echo "→ uv found - fast env build (pinned from uv.lock)"; \
		uv sync --extra dev --python 3.13; \
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
	pytest -m "not property and not fuzz"

property:
	pytest -m property

# Fuzz the trust-boundary gates (hostile input: seed/catalog/manifest YAML). The law:
# a gate refuses with its own error type, never crashes. Hypothesis-driven, no new deps.
fuzz:
	pytest -m fuzz

# Mutation testing (cosmic-ray) - the "Mutate" rung. On-demand ONLY: one test run per mutant is
# slow, so this is never a PR/CI gate. cosmic-ray is not in the default dev deps (its aiohttp/git
# tree would burden every CI install for a tool CI never runs), so it is installed just-in-time.
# Scoped by cosmic-ray.toml (hashchain by default). Prints the surviving-mutant rate; a survivor is
# a mutation the tests did not catch -- investigate it (a real gap) or confirm it is equivalent.
mutation:
	@command -v cosmic-ray >/dev/null 2>&1 || { echo "cosmic-ray not installed -- run: pip install cosmic-ray"; exit 1; }
	cosmic-ray init cosmic-ray.toml .cosmic-ray-session.sqlite
	cosmic-ray exec cosmic-ray.toml .cosmic-ray-session.sqlite
	cr-rate .cosmic-ray-session.sqlite

# Offline SAST for the pre-commit gate: bandit + the secret scan (both local, no network).
# This is the local/CI parity fix: SRI hashes once passed `make check` locally and then failed
# CI's secret-scan step, because check did not run it. pip-audit stays out (needs network; CI's
# blocking audit-runtime gate and `make doctor` cover it).
sast:
	bandit -c pyproject.toml -r parts forge.py -q
	bandit -c pyproject.toml -r . -q --severity-level medium --exclude ./.venv,./.git
	@git ls-files | grep -vFx 'chronicle/ledger.jsonl' | xargs detect-secrets-hook --baseline .secrets.baseline

# The full gate. `coverage` runs the WHOLE suite (property included) once, WITH
# instrumentation and the threshold -- so `check` covers, tests, and gates in a single
# suite run instead of two. `sast` mirrors CI's offline security steps so a green local
# check cannot fail CI's bandit/secret scan. `test`/`property` remain as fast, focused,
# no-coverage targets for the inner dev loop; `make ritual-fast` is the ~1s preflight.
check: lint typecheck coverage sast

# --- Readiness: the global self-audit -- registry validates (gates), then the
# project dashboard, computed from the registry + QualityGate. Read-only. ---
readiness:
	@python3 -c "import sys; from parts.registry import load_collective, validate, unfiled_modules, untwinned_modules; from parts.coverage import unexercised_capabilities; from parts.pm import pm_status; r=load_collective(); p=validate(r)+['unfiled module (not in the registry): '+m for m in unfiled_modules(r)]+['untested module (no test twin or aggregate): '+m for m in untwinned_modules()]; c=unexercised_capabilities(); print('Registry: CLEAN (no duplicates, no orphans, every module filed and tested)' if not p else 'Registry PROBLEMS:\n  '+'\n  '.join(p)); print('Coverage: CLEAN (every engine capability witnessed by shipped content)' if not c else 'Coverage PROBLEMS:\n  '+'\n  '.join(c)); print(); print(pm_status()); sys.exit(1 if (p or c) else 0)"

# --- ARC verdicts: run the release checks and FILE the runtime dimensions' verdicts as dated
# evidence under arc-evidence/ (git-ignored, reproducible from the recorded commit), so ARC can
# compose release + evidence from real outcomes. Human-run, not on the inner loop; ARC only READS
# what this files (`arc status`). change/patch have no store yet and stay honestly MISSING. ---
arc-verdicts:
	@python3 -m parts.arc_ledger emit $$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
	@echo "✓ ARC verdicts filed -> arc-evidence/ (see: arc status)"

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

# --- Cast (Phase 2): POUR a standalone project to DEST (engine vendored + seed pack + scaffold).
# Assembles a package; it is not yet detached/proven to boot independently (manifest: generated).
# Usage: make cast TEMPLATE=blank_mud NAME=Demo DEST=../codeforge-cast-demo ---
cast:
	@python3 -m parts.cast generate $(or $(TEMPLATE),blank_mud) $(or $(NAME),Demo) $(or $(DEST),../codeforge-cast-demo) $$(git rev-parse --short HEAD 2>/dev/null || echo unknown)

# --- Forge: the manufacturing capstone. ONE command forges a standalone game - plan, selectively
# vendor the surfaces' closure, prove it with the broad harness - and prints the summary.
# Usage: make forge NAME=SlimGame SURFACES=solo,save DEST=../my-game ---
forge:
	@python3 -m parts.cast forge $(or $(TEMPLATE),blank_mud) $(or $(NAME),Demo) $(or $(DEST),../codeforge-forged-game) $(or $(SURFACES),solo,save) $$(git rev-parse --short HEAD 2>/dev/null || echo unknown)

# --- Cast (Phase D2): pour a SELECTIVE cast - vendor ONLY the target surfaces' module closure,
# then validate by running every surface command against it. Falls back honestly (not_validated)
# if the closure is insufficient. Usage: make cast-selective SURFACES=solo,save NAME=Demo DEST=.. ---
cast-selective:
	@python3 -m parts.cast generate-selective $(or $(TEMPLATE),blank_mud) $(or $(NAME),Demo) $(or $(DEST),../codeforge-cast-selective) $(or $(SURFACES),solo,save) $$(git rev-parse --short HEAD 2>/dev/null || echo unknown)

# --- Cast diff (package-update U1): read-only drift report between a poured cast's vendored engine
# and this checkout (the target source). Names changed / upstream-only / cast-only engine files, the
# commit delta, local edits vs the pin, and the dependency delta. Changes nothing; applying an update
# is a separate step. AUDIT=1 adds a pip-audit CVE scan (needs network). Usage:
# make cast-diff DIR=../codeforge-forged-game SOURCE=. [AUDIT=1] ---
cast-diff:
	@python3 -m parts.cast diff $(or $(DIR),../codeforge-forged-game) $(or $(SOURCE),.) $(if $(AUDIT),--audit)

# --- Coupling: read-only engine coupling report (detachment D1). Traces the runtime module
# closure per surface and lists what a runtime cast could shed. Changes nothing. ---
coupling:
	@python3 -m parts.coupling

# --- Shelf-pour: pour the Hardware Store shelf as a standalone installable package (renamed off
# `parts`, deps auto-declared) and PROVE it imports every core with zero engine present. Changes
# nothing in the repo; writes into DEST (git-ignored). Usage: make shelf-pour DEST=../codeforge-shelf ---
shelf-pour:
	@python3 -m parts.shelf_pour $(or $(DEST),workspace/shelf-pour)

# --- Shelf-build: the release-grade proof. Pour, then build the wheel and install it into a FRESH
# venv -- proving `pip install codeforge-shelf` works for a stranger. Needs network (pip). Then
# `twine upload` (your PyPI trigger). Usage: make shelf-build DEST=.. WORK=.. ---
shelf-build:
	@python3 -m parts.shelf_pour build $(or $(DEST),workspace/shelf-pour) $(or $(WORK),workspace/shelf-build)

# --- Cast install-check: the FRESH-INSTALL proof. Creates a clean venv, installs ONLY the cast's
# declared deps, and boots it there - so the cast runs with zero dependency on CodeForge's env.
# Needs network (pip). Usage: make cast-install-check DIR=../codeforge-cast-demo WORK=/tmp/ci ---
cast-install-check:
	@python3 -m parts.cast install-check $(or $(DIR),../codeforge-cast-demo) $(or $(WORK),/tmp/cast-install-check)

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

# --- Runtime CVE gate (BLOCKING): audit only the RUNTIME dependency set (what actually
# ships), so a known CVE in a shipped dependency fails the build and upholds the "zero
# unresolved high/critical vulns" law. Build-tooling CVEs stay in the informational
# whole-env `audit`, so an unfixable pip/setuptools advisory never reds the build.
# A documented exception uses `pip-audit --ignore-vuln <ID>` with a reason. Needs uv. ---
audit-runtime:
	@command -v uv >/dev/null 2>&1 || { echo "audit-runtime needs uv (see make env)"; exit 1; }
	@uv export --no-dev --no-emit-project --format requirements-txt > runtime-requirements.txt
	pip-audit -r runtime-requirements.txt

# --- SBOM: a CycloneDX software bill of materials (SSDF supply-chain evidence).
# Generated from the installed environment; the output is git-ignored (reproducible
# from the recorded commit), the README/CI advertise that it is produced. ---
sbom:
	@mkdir -p reports/security
	cyclonedx-py environment -o reports/security/sbom.cdx.json
	@echo "✓ SBOM -> reports/security/sbom.cdx.json"

# SAST + dependency CVEs. bandit gates; audit is informational (see doctor).
# Two bandit passes: core code (parts + forge.py) at ALL severities (keeps low-severity password
# findings like B105/B106), plus the WHOLE repo at medium+ (matches forge-audit's bar, so the
# flagship's own gate catches whole-repo medium issues -- e.g. a hardcoded /tmp in a test -- before
# the proof-tool does). Both must pass.
security:
	bandit -c pyproject.toml -r parts forge.py -q
	bandit -c pyproject.toml -r . -q --severity-level medium --exclude ./.venv,./.git
	pip-audit --skip-editable
	@git ls-files | grep -vFx 'chronicle/ledger.jsonl' | xargs detect-secrets-hook --baseline .secrets.baseline

# --- Secret scan: fail on any tracked secret not in the audited baseline.
# Regenerate the baseline after auditing: detect-secrets scan --exclude-files '\.venv/' > .secrets.baseline ---
secrets:
	@git ls-files | grep -vFx 'chronicle/ledger.jsonl' | xargs detect-secrets-hook --baseline .secrets.baseline

# --- Dependency gate: every declared dependency must have a justification row in
# dependency_ledger.toml (the Dependency Approval Rule, frameless Python). Fails loud
# on an unjustified dependency; warns on a stale ledger row. Stdlib only (tomllib). ---
deps:
	@python -m parts.dependencies

# --- Bench: measure the engine tick (handle_command) throughput + latency and file a
# dated performance-evidence report under reports/performance/. Frameless (stdlib). ---
bench:
	@python -m parts.bench

# --- Trend: measure the engine tick, RECORD its median as a retained Chronicle metric point
# (chronicle/ledger.jsonl, git-tracked), then render the series over time. `make bench` stays pure. ---
trend:
	@python3 -m parts.bench --record $$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
	@python3 -m parts.chronicle trend engine_tick.median_us

# --- AI eval: score the offline LocalArchitect against a rubric, RECORD it as a Chronicle
# ai-eval (eval-regression memory), then show the memory. Network-free; point it at the real
# ClaudeAdvisor through the same seam to evaluate the LLM. ---
ai-eval:
	@python3 -m parts.ai_eval $$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
	@python3 -m parts.chronicle evals

# --- Retention doctor (read-only, R1): show what the Chronicle keeps, what is eligible for
# review, and what a hold protects. Disposition is not deletion; R1 writes and removes nothing. ---
retention:
	@python3 -m parts.retention

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
daily: patch arc-verdicts
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

loop:
	@python3 -m parts.loop trace $(or $(PART),workflow-engine)

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage __pycache__ parts/__pycache__ tests/__pycache__

serve:
	codeforge serve

# --- PostgreSQL: the production-shaped backend. SQLite stays the zero-config default;
# these bring up a local Postgres and run the Alembic migrations against DATABASE_URL.
# See docs/database.md. ---
# --- Backup: file a consistent, timestamped snapshot of the SQLite DB under backups/
# (git-ignored). Safe to run while the server is up (online .backup). Restore: see
# docs/database.md. For PostgreSQL use pg_dump. ---
backup:
	@python3 -c "from parts.db import backup_db; print('backed up ->', backup_db())"

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

# --- Re-record the README demo GIF from real aethryn gameplay (needs `agg`; see the script). ---
demo-gif:
	FORGE_SEED=aethryn python scripts/record_demo.py demo.cast
	agg --theme dracula --font-size 15 --speed 1.2 --fps-cap 24 --last-frame-duration 4 demo.cast docs/demo.gif
	@rm -f demo.cast && echo "docs/demo.gif re-recorded."

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

hooks:
	git config core.hooksPath scripts/hooks
	@echo "✓ git hooks active (scripts/hooks) - commits on main are refused"
