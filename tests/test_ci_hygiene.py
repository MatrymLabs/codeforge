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
    for path in sorted(glob.glob(_WORKFLOWS)):
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        for finding in lint_workflow(doc, name=Path(path).name):
            if finding.severity == "high":
                highs.append((Path(path).name, finding.rule, finding.where))
    assert highs == [], (
        f"CI supply-chain regressions (pin actions to SHAs / drop write-all): {highs}"
    )


def test_the_linter_actually_scanned_workflows():
    # guard against the test passing vacuously if the glob ever breaks
    assert glob.glob(_WORKFLOWS), "no workflows found to lint"
