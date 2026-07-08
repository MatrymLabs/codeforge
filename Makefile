.PHONY: fix lint typecheck test coverage audit check ship run world store clean

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
	pytest

check: lint typecheck test

# --- Extra inspections (One-Button Rule) ---
coverage:
	pytest --cov=parts --cov=forge --cov-report=term-missing

audit:
	pip-audit --skip-editable

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

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage __pycache__ parts/__pycache__ tests/__pycache__

serve:
	codeforge serve
