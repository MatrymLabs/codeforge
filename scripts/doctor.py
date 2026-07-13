"""Run each quality gate read-only, stop at the first failure, and prescribe the fix.

Reruns the gates (never parses stale logs) so it's always truthful about the
current state, and mirrors CI's blocking security surface locally: SAST (bandit),
the secret scan, and a runtime-dependency CVE gate all block, matching the CI jobs.
Assumes an activated .venv (run `make env` first if tools aren't on PATH).
"""

from __future__ import annotations

import subprocess
import sys

# (label, command, what a failure means, the repair, blocking)
GATES: list[tuple[str, list[str], str, str, bool]] = [
    (
        "format",
        ["ruff", "format", "--check", "."],
        "Code isn't in canonical format.",
        "make fix",
        True,
    ),
    (
        "lint",
        ["ruff", "check", "."],
        "Lint findings (style / bug patterns / unsorted imports).",
        "make fix",
        True,
    ),
    (
        "type",
        ["mypy", "parts", "tests", "forge.py"],
        "A type contract is violated -- a value can be the wrong type at runtime.",
        "Fix the annotation or code at the file:line above; no auto-fix is safe.",
        True,
    ),
    (
        "test",
        ["pytest", "-m", "not property"],
        "A test failed -- behavior regressed against a written expectation.",
        "Fix the code (or the test, if the expectation changed).",
        True,
    ),
    (
        "property",
        ["pytest", "-m", "property"],
        "A property/invariant broke on a Hypothesis-generated edge case.",
        "Reproduce with the minimal counterexample Hypothesis printed above.",
        True,
    ),
    (
        "coverage",
        [
            "pytest",
            "--cov=parts",
            "--cov=forge",
            "--cov-report=term-missing",
            "--cov-fail-under=85",
        ],
        "Coverage is below the 85% floor -- real code paths are untested.",
        "Add tests for the 'Missing' lines listed above.",
        True,
    ),
    (
        "security",
        ["bandit", "-c", "pyproject.toml", "-r", "parts", "forge.py", "-q"],
        "A risky code pattern was flagged (SAST).",
        "Fix it, or add a reviewed suppression in [tool.bandit] with a reason.",
        True,
    ),
    (
        "secrets",
        ["make", "secrets"],
        "A tracked file may contain a secret (detect-secrets matched, not in the baseline).",
        "Remove and rotate the secret; if a false positive, audit it into .secrets.baseline.",
        True,
    ),
    (
        "audit",
        ["make", "audit-runtime"],
        "A shipped runtime dependency has a known CVE (the blocking gate).",
        "Upgrade to the fixed version, or document an exception via pip-audit --ignore-vuln.",
        True,
    ),
]


def main() -> int:
    warnings: list[str] = []
    for label, cmd, meaning, fix, blocking in GATES:
        print(f"\n$ {' '.join(cmd)}")
        failed = subprocess.run(cmd).returncode != 0
        if not failed:
            continue
        if blocking:
            print("\n" + "-" * 64)
            print(f"X FAILED: {label}")
            print(f"  What it means : {meaning}")
            print(f"  Repair        : {fix}")
            print("-" * 64)
            return 1
        warnings.append(f"! {label}: {meaning}\n  Repair: {fix}")

    print("\n" + "=" * 64)
    print("OK: all blocking gates are green.")
    for w in warnings:
        print("\n" + w)
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
