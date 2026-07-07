.PHONY: fix lint typecheck test check run clean

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

# --- Conveniences ---
run:
	python3 forge.py

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache __pycache__ parts/__pycache__ tests/__pycache__

ship: check
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo ""; \
		echo "✗ Uncommitted changes detected. Commit first, then ship:"; \
		git status --short; \
		exit 1; \
	fi
	git push
	@echo "✓ Shipped to GitHub."