.PHONY: env fix lint typecheck test property coverage audit security doctor patch daily check readiness ship run world store hardware clean serve ritual ritual-down unskew

# --- Environment: create/validate the .venv, fail loud on version mismatch ---
env:
	python3 -m venv .venv
	.venv/bin/pip install -q --upgrade pip
	.venv/bin/pip install -q -e ".[dev]"
	@.venv/bin/python -c "import sys; assert sys.version_info[:2] >= (3, 13), 'need Python >= 3.13'"
	@echo "✓ .venv ready — activate with: source .venv/bin/activate"

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

check: lint typecheck test property

# --- Readiness: the global self-audit -- registry validates (gates), then the
# project dashboard, computed from the registry + QualityGate. Read-only. ---
readiness:
	@python3 -c "import sys; from parts.registry import load_collective, validate; from parts.pm import pm_status; p=validate(load_collective()); print('Registry: CLEAN (no duplicates, no orphans)' if not p else 'Registry PROBLEMS:\n  '+'\n  '.join(p)); print(); print(pm_status()); sys.exit(1 if p else 0)"

# --- Extra inspections (One-Button Rule) ---
coverage:
	pytest --cov=parts --cov=forge --cov-report=term-missing --cov-report=xml --cov-fail-under=85

audit:
	pip-audit --skip-editable

# SAST + dependency CVEs. bandit gates; audit is informational (see doctor).
security:
	bandit -c pyproject.toml -r parts forge.py -q
	pip-audit --skip-editable

# --- Doctor: run the gates read-only, stop at the first failure, prescribe the fix ---
doctor:
	python3 scripts/doctor.py

# --- Security patches: scan deps for CVEs, apply available fixes, then RE-VERIFY.
# Files a dated audit under security-evidence/. Detect + fix are best-effort
# (need network); the re-run of `make check` is the hard safety net — if a patch
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
		echo "  library not runnable at $(FGL_HOME) — run 'make env' there to enable the daily reg check"; \
	fi
	@echo "✓ daily ritual complete"

# --- Ship: gates, then push. Refuses dirty trees and red gates ---
ship: check
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo ""; \
		echo "✗ Uncommitted changes detected. Commit first, then ship:"; \
		git status --short; \
		exit 1; \
	fi
	git push
	@echo "✓ Shipped to GitHub."

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

# --- The Ritual: one command lights the whole workshop -- gates run, GitHub
# mirrors, the forge lights, the MUD window opens at the front desk. Bound to
# the phrase "start the ritual" via a shell function (see docs/RUNNING.md). ---
ritual:
	@bash scripts/ritual.sh

# --- The Ritual, Closed: secure the workshop at day's end -- bank any forge on
# :4000, stop containers, muster uncommitted/unpushed work. Bound to the phrase
# "complete the ritual". ---
ritual-down:
	@bash scripts/ritual_down.sh

unskew:
	git ls-files | xargs touch
