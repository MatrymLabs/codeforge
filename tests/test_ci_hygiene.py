"""Real consumer of kernel/shelf/workflow_linter (MOD-05.017): guard codeforge's OWN CI hygiene.

The Workflow Linter is not just a Hardware Store part - it watches this repo. This test lints every
one of codeforge's GitHub Actions workflows and fails on any HIGH finding (a `write-all` permission
or an action pinned to a moving tag instead of a commit SHA), so a supply-chain regression in our
own CI is caught in CI. Medium/low findings (job-appropriate top-level writes like codeql's
security-events) are informational and do not fail the build.
"""

from __future__ import annotations

import glob
from pathlib import Path

import yaml

from kernel.shelf.workflow_linter import lint_workflow

_WORKFLOWS = str(Path(__file__).resolve().parent.parent / ".github" / "workflows" / "*.yml")


def test_our_workflows_have_no_high_findings():
    highs = []
    for path in sorted(glob.glob(_WORKFLOWS)):  # noqa: PTH207
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        for finding in lint_workflow(doc, name=Path(path).name):
            if finding.severity == "high":
                highs.append((Path(path).name, finding.rule, finding.where))
    assert highs == [], (
        f"CI supply-chain regressions (pin actions to SHAs / drop write-all): {highs}"
    )


def test_the_linter_actually_scanned_workflows():
    # guard against the test passing vacuously if the glob ever breaks
    assert glob.glob(_WORKFLOWS), "no workflows found to lint"  # noqa: PTH207


def test_every_job_is_bounded_by_a_timeout():
    """No job may run unbounded. A required check that hangs blocks EVERY merge.

    On 2026-08-18 the `e2e` job hung inside `playwright install` and held a one-line .gitignore
    PR at BLOCKED. `e2e` is a required status check, so nothing could merge past it, and with no
    `timeout-minutes` the job would have sat there until GitHub's six-hour default killed it.
    Twenty jobs across every workflow were unbounded; the same hang in any of them would have
    done the same thing.

    A timeout does not make a slow job fast. It converts an indefinite stall into a fast, legible
    failure, which is the difference between a gate that reports and a gate that hangs. The budget
    on each job is generous against its observed runtime so a slow runner never false-fails.
    """
    unbounded = []
    for path in sorted(glob.glob(_WORKFLOWS)):  # noqa: PTH207
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        for job_name, job in (doc.get("jobs") or {}).items():
            if isinstance(job, dict) and "timeout-minutes" not in job:
                unbounded.append(f"{Path(path).name}:{job_name}")
    assert unbounded == [], (
        "these CI jobs can hang indefinitely and deadlock the merge queue; "
        f"give each a timeout-minutes: {unbounded}"
    )
