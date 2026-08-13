.PHONY: hooks env env-parity fix lint typecheck test property fuzz coverage audit audit-runtime security sast secrets deps intake sbom bench trend slo loadtest artifact ai-eval retention doctor patch daily check readiness arc-verdicts truth forge cast-plan cast cast-selective cast-install-check cast-diff cast-update deploy-proof plugins coupling shelf-pour shelf-build smoke repo-integrity ship run world world-check exit-integrity zone-density economy-audit store hardware clean serve backup restore db-up db-down db-migrate docs-serve docs-build demo-gif e2e evolution ritual-fast ritual ritual-down unskew loop proto contracts


# --- Gate caches: explicit, writable anywhere, identical for both benches.
# ruff and mypy default to .ruff_cache/.mypy_cache in the working directory. On CX-021 that
# location was not writable for one bench, which had to run the gate with environment prefixes and
# record them in its return. An order naming `make check` while one bench decorates it has two
# commands wearing one name, so the location is declared here instead. `?=`, never `=`: a caller
# that still needs to redirect must be able to, and must be able to tell if it failed to.
RUFF_CACHE_DIR ?= /tmp/matrymlabs-codeforge-ruff-cache
MYPY_CACHE_DIR ?= /tmp/matrymlabs-codeforge-mypy-cache
export RUFF_CACHE_DIR MYPY_CACHE_DIR

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
lint: lint-python lint-rust lint-go lint-shell  ## Every language present in the tree, not only Python.

# One target per language, so a language with no code says so instead of passing silently.
# Rust and Go code has existed here since the nav kernel and the edge/spine organs landed, and
# neither was ever linted: `lint` ran ruff and nothing else. The first run found formatting drift
# in lib.rs and 12 unchecked errors in edge/. A gate that inspects one of three languages is not
# green, it is uninformed.
lint-python:
	ruff format --check .
	ruff check .

lint-rust:
	@if [ -z "$$(git ls-files '*.rs')" ]; then \
		echo "lint-rust: no .rs files in this tree, nothing to inspect"; \
	else \
		for m in $$(git ls-files '*/Cargo.toml' | xargs -r -n1 dirname); do \
			echo "lint-rust: $$m"; \
			( cd $$m && cargo fmt --check && cargo clippy --all-targets -- -D warnings ) || exit 1; \
		done; \
	fi

# -x follows sourced files so real cross-file issues are caught. SC1091 is then excluded, and
# the distinction matters: SC1091 reports that the LINTER could not open a sourced file, never
# that the script is wrong. `.venv/bin/activate` exists on a developer box and not in CI, where
# uv installs --system, so leaving it enabled makes the gate depend on which machine ran it. That
# is the fourth time in one day a green local run rested on an artifact CI does not have.
lint-shell:
	@if [ -z "$$(git ls-files '*.sh')" ]; then \
		echo "lint-shell: no .sh files in this tree, nothing to inspect"; \
	else \
		shellcheck -x -e SC1091 $$(git ls-files '*.sh'); \
	fi

lint-go:
	@if [ -z "$$(git ls-files '*.go')" ]; then \
		echo "lint-go: no .go files in this tree, nothing to inspect"; \
	else \
		for m in $$(git ls-files '*/go.mod' | xargs -r -n1 dirname); do \
			if ! ( cd $$m && go build ./... >/dev/null 2>&1 ); then \
				echo "lint-go: $$m UNVERIFIED - it does not build. Generated code absent?"; \
				echo "          run \`make proto\` (ADR-0012: the bindings are git-ignored)."; \
				exit 1; \
			fi; \
			echo "lint-go: $$m"; \
			( cd $$m && test -z "$$(gofmt -l .)" && go vet ./... && golangci-lint run ./... ) || exit 1; \
		done; \
	fi

imports:  ## Enforce the style-guide section-2 dependency direction (import-linter).
	lint-imports

typecheck: typecheck-python typecheck-native  ## Python via mypy; Rust and Go via their compilers.

typecheck-python:
	mypy kernel adapters content tests forge.py

# Per the practices reference section 15: for Rust and Go the COMPILER is the type gate.
typecheck-native:
	@for m in $$(git ls-files '*/Cargo.toml' | xargs -r -n1 dirname); do \
		echo "typecheck-rust: $$m"; ( cd $$m && cargo build ) || exit 1; \
	done
	@for m in $$(git ls-files '*/go.mod' | xargs -r -n1 dirname); do \
		echo "typecheck-go: $$m"; ( cd $$m && go build ./... ) || exit 1; \
	done

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
# The final step RECORDS the run to security-evidence/mutation-latest.json so kernel/posture.py can
# read it as the mutation_kill_rate KPI (MEASURED, or NOT_COMPUTABLE + stale past its freshness
# window). This keeps mutation off the PR path while still turning its number into tracked evidence.
mutation:
	@command -v cosmic-ray >/dev/null 2>&1 || { echo "cosmic-ray not installed -- installing it for this on-demand run"; python -m pip install cosmic-ray; }
	cosmic-ray init cosmic-ray.toml .cosmic-ray-session.sqlite
	cosmic-ray exec cosmic-ray.toml .cosmic-ray-session.sqlite
	cr-rate .cosmic-ray-session.sqlite
	cr-report .cosmic-ray-session.sqlite | python -m kernel.mutation_recorder

# Offline SAST for the pre-commit gate: bandit + the secret scan (both local, no network).
# This is the local/CI parity fix: SRI hashes once passed `make check` locally and then failed
# CI's secret-scan step, because check did not run it. pip-audit stays out (needs network; CI's
# blocking audit-runtime gate and `make doctor` cover it).
sast:
	bandit -c pyproject.toml -r kernel adapters content forge.py -q
	bandit -c pyproject.toml -r . -q --severity-level medium --exclude ./.venv,./.git
	@git ls-files | grep -vFx 'chronicle/ledger.jsonl' | xargs detect-secrets-hook --baseline .secrets.baseline

# The full gate. `coverage` runs the WHOLE suite (property included) once, WITH
# instrumentation and the threshold -- so `check` covers, tests, and gates in a single
# suite run instead of two. `sast` mirrors CI's offline security steps so a green local
# check cannot fail CI's bandit/secret scan. `test`/`property` remain as fast, focused,
# no-coverage targets for the inner dev loop; `make ritual-fast` is the ~1s preflight.
check: lint imports typecheck exit-integrity coverage sast

# --- Readiness: the global self-audit -- registry validates (gates), then the
# project dashboard, computed from the registry + QualityGate. Read-only. ---
readiness:
	@python3 -c "import sys; from kernel.registry import load_collective, validate, unfiled_modules, untwinned_modules; from kernel.coverage import unexercised_capabilities; from kernel.pm import pm_status; r=load_collective(); p=validate(r)+['unfiled module (not in the registry): '+m for m in unfiled_modules(r)]+['untested module (no test twin or aggregate): '+m for m in untwinned_modules()]; c=unexercised_capabilities(); print('Registry: CLEAN (no duplicates, no orphans, every module filed and tested)' if not p else 'Registry PROBLEMS:\n  '+'\n  '.join(p)); print('Coverage: CLEAN (every engine capability witnessed by shipped content)' if not c else 'Coverage PROBLEMS:\n  '+'\n  '.join(c)); print(); print(pm_status()); sys.exit(1 if (p or c) else 0)"

# --- ARC verdicts: run the release checks and FILE the runtime dimensions' verdicts as dated
# evidence under arc-evidence/ (git-ignored, reproducible from the recorded commit), so ARC can
# compose release + evidence from real outcomes. Human-run, not on the inner loop; ARC only READS
# what this files (`arc status`). change/patch have no store yet and stay honestly MISSING. ---
arc-verdicts:
	@python3 -m kernel.arc_ledger emit $$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
	@echo "✓ ARC verdicts filed -> arc-evidence/ (see: arc status)"

# --- Repo integrity: one honest repo-health report (code quality + security +
# provenance + registry + docs + truth), composed from checks we already own.
# Detects tools; a missing one is reported not_configured, never faked. ---
repo-integrity:
	@python3 -m kernel.integrity

# --- Cast: plan a standalone game project ("cast") poured from a seed pack + the engine.
# Dry run -- lists what it WOULD copy and the manifest it WOULD write; writes nothing.
# Usage: make cast-plan TEMPLATE=fantasy_mud NAME=Aethris (see docs/seed_architecture.md). ---
cast-plan:
	@python3 -m kernel.cast $(or $(TEMPLATE),blank_mud) $(or $(NAME),Demo) $$(git rev-parse --short HEAD 2>/dev/null || echo unknown)

# --- Cast (Phase 2): POUR a standalone project to DEST (engine vendored + seed pack + scaffold).
# Assembles a package; it is not yet detached/proven to boot independently (manifest: generated).
# Usage: make cast TEMPLATE=blank_mud NAME=Demo DEST=../codeforge-cast-demo ---
cast:
	@python3 -m kernel.cast generate $(or $(TEMPLATE),blank_mud) $(or $(NAME),Demo) $(or $(DEST),../codeforge-cast-demo) $$(git rev-parse --short HEAD 2>/dev/null || echo unknown)

# --- Deploy-proof: pour the REAL Aethryn game Seed (whole engine + world), boot it in a fresh
# subprocess, and prove it serves play commands over its own world - the honest proof the game
# Seed's deployment is real, at the scale the platform is capable of creating. Heavy (whole-engine
# vendor), so it is a standalone proof, not a unit gate. Usage: make deploy-proof ---
deploy-proof:
	@python3 scripts/deploy_aethryn_seed.py

# --- Forge: the manufacturing capstone. ONE command forges a standalone game - plan, selectively
# vendor the surfaces' closure, prove it with the broad harness - and prints the summary.
# Usage: make forge NAME=SlimGame SURFACES=solo,save DEST=../my-game ---
forge:
	@python3 -m kernel.cast forge $(or $(TEMPLATE),blank_mud) $(or $(NAME),Demo) $(or $(DEST),../codeforge-forged-game) $(or $(SURFACES),solo,save) $$(git rev-parse --short HEAD 2>/dev/null || echo unknown)

# --- Cast (Phase D2): pour a SELECTIVE cast - vendor ONLY the target surfaces' module closure,
# then validate by running every surface command against it. Falls back honestly (not_validated)
# if the closure is insufficient. Usage: make cast-selective SURFACES=solo,save NAME=Demo DEST=.. ---
cast-selective:
	@python3 -m kernel.cast generate-selective $(or $(TEMPLATE),blank_mud) $(or $(NAME),Demo) $(or $(DEST),../codeforge-cast-selective) $(or $(SURFACES),solo,save) $$(git rev-parse --short HEAD 2>/dev/null || echo unknown)

# --- Cast diff (package-update U1): read-only drift report between a poured cast's vendored engine
# and this checkout (the target source). Names changed / upstream-only / cast-only engine files, the
# commit delta, local edits vs the pin, and the dependency delta. Changes nothing; applying an update
# is a separate step. AUDIT=1 adds a pip-audit CVE scan (needs network). Usage:
# make cast-diff DIR=../codeforge-forged-game SOURCE=. [AUDIT=1] ---
cast-diff:
	@python3 -m kernel.cast diff $(or $(DIR),../codeforge-forged-game) $(or $(SOURCE),.) $(if $(AUDIT),--audit)

# --- Cast update (package-update U2): APPLY an engine update to a poured cast, guarded by the broad
# harness. Backs up, re-vendors from this checkout, re-validates, rolls back on failure; never
# commits (the owner commits). Refuses local edits / selective casts unless FORCE=1. Usage:
# make cast-update DIR=../codeforge-forged-game SOURCE=. [FORCE=1] ---
cast-update:
	@python3 -m kernel.cast update $(or $(DIR),../codeforge-forged-game) $(or $(SOURCE),.) $(if $(FORCE),--force)

# --- Plugins: list the third-party command plugins loaded from plugins/ at boot, and any that were
# rejected (loud, never silent). The plugin boundary (D3): SEED verbs only, no collision. ---
plugins:
	@python3 -c "import forge; from kernel.plugins import render_plugins; print(render_plugins(forge.PLUGIN_LOAD))"

# --- Coupling: read-only engine coupling report (detachment D1). Traces the runtime module
# closure per surface and lists what a runtime cast could shed. Changes nothing. ---
coupling:
	@python3 -m kernel.coupling

# --- Shelf-pour: pour the Hardware Store shelf as a standalone installable package (renamed off
# `parts`, deps auto-declared) and PROVE it imports every core with zero engine present. Changes
# nothing in the repo; writes into DEST (git-ignored). Usage: make shelf-pour DEST=../codeforge-shelf ---
shelf-pour:
	@python3 -m kernel.shelf_pour $(or $(DEST),workspace/shelf-pour)

# --- Shelf-build: the release-grade proof. Pour, then build the wheel and install it into a FRESH
# venv -- proving `pip install codeforge-shelf` works for a stranger. Needs network (pip). Then
# `twine upload` (your PyPI trigger). Usage: make shelf-build DEST=.. WORK=.. ---
shelf-build:
	@python3 -m kernel.shelf_pour build $(or $(DEST),workspace/shelf-pour) $(or $(WORK),workspace/shelf-build)

# --- Cast install-check: the FRESH-INSTALL proof. Creates a clean venv, installs ONLY the cast's
# declared deps, and boots it there - so the cast runs with zero dependency on CodeForge's env.
# Needs network (pip). Usage: make cast-install-check DIR=../codeforge-cast-demo WORK=/tmp/ci ---
cast-install-check:
	@python3 -m kernel.cast install-check $(or $(DIR),../codeforge-cast-demo) $(or $(WORK),/tmp/cast-install-check)

# --- Truth: EvidenceGate -- check the project's claims correspond to reality
# (overclaims, drift-prone counts, docs, registry, QA board). Exit 1 on any
# FLAGGED claim, so the ritual and CI fail loud on drift. Same as the in-MUD
# `truth check`, reachable from a script. ---
truth:
	@python3 -m kernel.evidence_gate

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
	pytest -n auto --cov=kernel --cov=adapters --cov=content --cov=forge --cov-branch --cov-report=term-missing --cov-report=xml --cov-fail-under=85

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

# --- Gate canary (RD-2026-0002 #1): prove the CVE gate BLOCKS on a real defect. A gate never
# tested against a known-vulnerable input is faith, not evidence. Feeds pip-audit a fixture that
# pins a package with real advisories and asserts a NON-ZERO exit; if the gate ever goes toothless
# (or pip-audit silently no-ops), this fails LOUD. Needs the online advisory DB, so it is a CI
# step, not a pytest (the secret-gate canary lives offline in tests/test_gate_canaries.py). ---
.PHONY: gate-canary
gate-canary:
	@echo "→ CVE gate canary: pip-audit must BLOCK on a known-vulnerable pin..."
	@if pip-audit -r tests/fixtures/known_vulnerable_requirements.txt >/dev/null 2>&1; then \
		echo "GATE CANARY FAILED: pip-audit did NOT flag a known-vulnerable package - the CVE gate is toothless"; \
		exit 1; \
	else \
		echo "  ok: the CVE gate flags the known-vulnerable fixture (has teeth)"; \
	fi

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
	bandit -c pyproject.toml -r kernel adapters content forge.py -q
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
	@python -m adapters.dependencies

# --- Intake: the Technology Intake Office (docs/technology_intake.md). Controlled adoption,
# Python-native: fails loud if any onboarding record is incomplete (an approved technology
# missing one of the ten requirements) or inconsistent. Stdlib only (tomllib). ---
intake:
	@python -m kernel.intake

# --- ADDIE: the continuous-improvement loop (docs/addie_loop.md). A systems-engineering self-check
# that fails loud if any filed MAJOR cycle skipped a phase (built without understanding, designed
# without evidence, implemented without integration, declared success without evaluation). It
# overrides no control; it is the loop the controls run inside. Stdlib only (tomllib). ---
addie:
	@python -m kernel.addie

# --- Bench: measure the engine tick (handle_command) throughput + latency and file a
# dated performance-evidence report under reports/performance/. Frameless (stdlib). ---
bench:
	@python -m kernel.bench

# --- Proto: regenerate the protocol-spine bindings from the ONE .proto (Python + Go). Needs protoc
# + protoc-gen-go on PATH; the generated code is git-ignored and rebuilt here (ADR-0012). The game
# runs on the JSON fallback with none of this. ---
proto:
	protoc --proto_path=proto --python_out=proto proto/telemetry.proto
	protoc --proto_path=proto --go_out=native/spine --go_opt=module=codeforge/spine proto/telemetry.proto
	@echo "regenerated proto/telemetry_pb2.py + native/spine/telemetrypb/telemetry.pb.go"

# --- Contracts: regenerate the published Fleet Core contract authorities from the Pydantic models
# (ship ADR 0003). The drift gate tests/test_contracts.py fails if the committed schema goes stale. ---
contracts:
	@python contracts/generate.py

# --- Trend: measure the engine tick, RECORD its median as a retained Chronicle metric point
# (chronicle/ledger.jsonl, git-tracked), then render the series over time. `make bench` stays pure. ---
trend:
	@python3 -m kernel.bench --record $$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
	@python3 -m kernel.chronicle trend engine_tick.median_us

# --- SLO: evaluate the recorded engine-tick SLI against its objective + error budget
# (docs/reports/slo/engine-tick-slo.md). Read-only over the Chronicle; exits 1 on a breach so a
# pipeline can act. NOT in `make check` (the SLI is host-relative and sparse). ---
slo:
	@python3 -m kernel.slo

# --- Loadtest: drive the tick from many concurrent sessions and file a latency-distribution
# artifact (p50/p95/p99). Read-only rotation; localhost/in-process only. NOT in make check. ---
loadtest:
	@python3 -m kernel.loadtest

# --- Artifact: stamp a portfolio-artifact repo skeleton (README/ADR/design-doc/api-spec/
# test-plan/CI/compose) into git-ignored workspace/artifacts/. Structure + boilerplate only. ---
artifact:
	@python3 -m kernel.artifact_forge "$(NAME)" "$(KIND)"

# --- AI eval: score the offline LocalArchitect against a rubric, RECORD it as a Chronicle
# ai-eval (eval-regression memory), then show the memory. Network-free; point it at the real
# ClaudeAdvisor through the same seam to evaluate the LLM. ---
ai-eval:
	@python3 -m adapters.ai_eval $$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
	@python3 -m kernel.chronicle evals

# --- Retention doctor (read-only, R1): show what the Chronicle keeps, what is eligible for
# review, and what a hold protects. Disposition is not deletion; R1 writes and removes nothing. ---
retention:
	@python3 -m kernel.retention

# --- Doctor: run the gates read-only, stop at the first failure, prescribe the fix ---
env-parity:
	@python3 -m kernel.env_parity

doctor: env-parity
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
	@# Evidence honesty (RD-2026-0002 #1/#3): the scan step is fail-open (best-effort, needs
	@# network), so DON'T let a silent scan failure pass as a clean day - the daily ritual must
	@# not quietly stop producing evidence. Fail loud if today's audit file is missing/empty.
	@test -s "security-evidence/$$(date -u +%Y-%m-%d)-pip-audit.json" || { \
		echo "PATCH RITUAL WARNING: no CVE evidence written today (scan failed or was offline)."; \
		echo "  the exposure window is now UNMEASURED - run 'make audit-runtime' before relying on it."; \
		exit 1; \
	}
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
	python3 -m kernel.catalog

# The Surveyor: read-only validation of the Aethryn world map (duplicate ids, broken region
# references, canon drift). Exit non-zero on any problem, so it can gate a script.
world-check:
	@python3 -m tools.world validate

exit-integrity:
	@python -m kernel.world.exit_integrity

# The Cartographer's tally: read-only per-zone content-density audit of the Aethryn world.
# Ranks zones by content score and flags any below the launch floor (settlements/dungeons/quests).
zone-density:
	@python3 tools/zone_density.py

# The Assayer: read-only audit of the DESIGNED coin economy (faucets vs sinks) over the
# assembled Aethryn world, so live-ops can read the balance without instrumenting the server.
economy-audit:
	@FORGE_SEED=aethryn python3 -c "import kernel.world.world; from kernel.world.npcs import NPCS; from kernel.coin_flow import render_audit; print(render_audit(NPCS))"

store:
	python3 -m kernel.store

hardware:
	python3 -m kernel.hardware

loop:
	@python3 -m kernel.loop trace $(or $(PART),workflow-engine)

clean:
	rm -rf $(RUFF_CACHE_DIR) $(MYPY_CACHE_DIR) .pytest_cache .ruff_cache .mypy_cache .coverage __pycache__ kernel/__pycache__ adapters/__pycache__ tests/__pycache__

serve:
	codeforge serve

# Boot aethryn at MMO scale (~1,000,000 rooms, ~1.9 GB / ~22 s boot). CODEFORGE_WILD_SCALE grows
# every wildlands region; SCALE overrides it (make serve-mmo SCALE=10 for a smaller MMO world). The
# demo and CI stay at the seed's shipped size (scale 1); this button is for capable hardware.
serve-mmo: SCALE ?= 19
serve-mmo:
	FORGE_SEED=aethryn CODEFORGE_WILD_SCALE=$(SCALE) codeforge serve

# --- PostgreSQL: the production-shaped backend. SQLite stays the zero-config default;
# these bring up a local Postgres and run the Alembic migrations against DATABASE_URL.
# See docs/database.md. ---
# --- Backup: file a consistent, timestamped snapshot of the SQLite DB under backups/
# (git-ignored). Safe to run while the server is up (online .backup). Restore: see
# docs/database.md. For PostgreSQL use pg_dump. ---
backup:
	@python3 -c "from kernel.world.db import backup_db; print('backed up ->', backup_db())"

# Restore a SQLite snapshot over the live database (recovery). Usage: make restore BACKUP=<path>.
# Disposes the cached engine so the server reopens the restored file. The restore is TESTED end to
# end in tests/test_db.py (untested backups are not backups). For PostgreSQL use pg_restore.
restore:
	@test -n "$(BACKUP)" || (echo "usage: make restore BACKUP=<path-to-.db>" && exit 2)
	@python3 -c "from pathlib import Path; from kernel.world.db import restore_db; print('restored ->', restore_db(Path('$(BACKUP)')))"

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
	agg --theme dracula --font-size 15 --speed 1.5 --fps-cap 24 --last-frame-duration 4 demo.cast docs/demo.gif
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
