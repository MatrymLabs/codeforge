# Template: Standalone library package

**Use when:** a `parts/` subsystem becomes genuinely reused outside CodeForge and earns its own
release cadence, so it is extracted into an installable, independently versioned package.
**Status for CodeForge:** not yet. No part is currently reused outside the flagship; extraction
is premature (ADR-0007, question 15). This template is the destination if that changes.

## Layout

```text
README.md                     # what it is, install, usage example, links
LICENSE
pyproject.toml                # [project] name/version, [build-system]
src/<pkg>/__init__.py         # HERE src/ is correct - a published lib should
src/<pkg>/module.py           #   import only the installed copy, never a stray cwd one
tests/test_module.py          # twin tests (pytest)
CHANGELOG.md                  # version history
.github/workflows/ci.yml      # lint + type + test, and publish on tag
```

## Why `src/` here but NOT in CodeForge

A **published** library is the one case where `src/` genuinely earns its place: it forces tests
to import the *installed* package, catching "works on my machine because of the cwd" packaging
bugs before a release reaches users. CodeForge is an application/flagship, not a distributed
library, and is already installed editable - so it takes the flat layout (ADR-0007). The rule is
consistent: `src/` for what you publish, flat for what you run in place.

## Extraction checklist (before spinning a part out)

1. The part is imported by something outside CodeForge (real, not hypothetical).
2. It is stable - its public interface has not churned recently.
3. It has its own tests that pass in isolation (no hidden coupling to the engine).
4. A dependency-ledger entry and an ADR record the split, with a migration plan and rollback.
5. Josh approves - a repo split is a critical juncture.

Until all five hold, the part stays in `parts/` and this template stays a plan.
