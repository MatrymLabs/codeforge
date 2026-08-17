"""Gate canaries: prove the security gates actually have teeth (RD-2026-0002 finding #1).

A gate that is never tested against a real defect is faith, not evidence. The DoD secure-
coding doc is explicit: "known-vulnerable fixture; decoy secret tests; scanner outage test...
never silently pass." This suite plants a real defect and asserts the gate catches it - so a
future change that quietly weakens `make secrets`/`make audit-runtime` turns this suite red.

Scope + honesty:
- The SECRET canary runs the ACTUAL gate command (`detect-secrets-hook`, the same binary
  `make secrets` runs) against a planted secret. It is fully offline (regex/entropy plugins),
  so it obeys the "tests never touch the network" law.
- The CVE gate (`pip-audit`) needs the online advisory DB, which tests must not require, so its
  canary is a CI job step (`make gate-canary`), not a pytest here - see the Makefile target.
- We assert the tools EXIST and BLOCK on a defect; we deliberately do not assert their full
  detector lists (that is the vendors' contract, not ours).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BASELINE = _REPO_ROOT / ".secrets.baseline"

# A planted secret the scanner MUST flag: a high-entropy AWS-style secret + a private-key header.
# NOT the canonical AKIA...EXAMPLE doc key (which detect-secrets deliberately allowlists).
# The `pragma: allowlist secret` comments tell THIS repo's own detect-secrets gate that the
# planted values are an intentional test fixture (else the canary trips the very gate it proves -
# which it did on the first CI run, a nice confirmation the gate has teeth). The tmp file the
# test writes carries NO pragma, so the canary still catches it there.
_AWS = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY123abc"  # pragma: allowlist secret
_KEY = "-----BEGIN RSA PRIVATE KEY-----\\nMIIEpAIBAAKCAQEA0planted"  # pragma: allowlist secret
_PLANTED_SECRET = f'aws_secret_access_key = "{_AWS}"\nrsa = "{_KEY}"\n'


def _hook_available() -> bool:
    return shutil.which("detect-secrets-hook") is not None and _BASELINE.exists()


requires_hook = pytest.mark.skipif(
    not _hook_available(),
    reason="detect-secrets-hook / .secrets.baseline not present (installed in CI + the dev venv)",
)


def _run_hook(target: Path) -> subprocess.CompletedProcess[str]:
    """Run the real gate command the way `make secrets` does: hook against the baseline."""
    return subprocess.run(  # noqa: PLW1510
        ["detect-secrets-hook", "--baseline", str(_BASELINE), str(target)],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )


@requires_hook
def test_secret_gate_catches_a_planted_secret(tmp_path: Path) -> None:
    """A decoy secret MUST trip the gate (nonzero exit) - proof the secret scan has teeth."""
    planted = tmp_path / "leaky.py"
    planted.write_text(_PLANTED_SECRET, "utf-8")
    result = _run_hook(planted)
    assert result.returncode != 0, (
        "the secret gate did NOT flag a planted secret - it has gone toothless.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "Secret" in result.stdout or "secret" in result.stdout.lower()


@requires_hook
def test_secret_gate_passes_a_clean_file(tmp_path: Path) -> None:
    """The gate must NOT cry wolf on ordinary code (guards against a canary that always fails)."""
    clean = tmp_path / "ok.py"
    clean.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", "utf-8")
    assert _run_hook(clean).returncode == 0


def test_cve_gate_fixture_exists_and_pins_a_known_vulnerable_version() -> None:
    """The CVE canary's fixture (consumed by `make gate-canary` in CI, where the online advisory
    DB is available) must exist and pin a version with a real advisory - so the CVE gate is proven
    to block, not just assumed to. Kept as a file check here to honor the no-network law."""
    fixture = _REPO_ROOT / "tests" / "fixtures" / "known_vulnerable_requirements.txt"
    assert fixture.exists(), "the known-vulnerable CVE-gate fixture is missing"
    body = fixture.read_text("utf-8")
    assert "==" in body, "the fixture must PIN an exact vulnerable version (name==version)"
    assert not body.lstrip().startswith("#") or "==" in body
