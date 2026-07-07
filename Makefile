.PHONY: lint format test check run

lint:
	ruff check .

format:
	ruff format .
	ruff check . --fix

test:
	pytest

check: format lint test

run:
	python3 forge.py

typecheck:
	mypy parts tests forge.py

check: format lint test typecheck