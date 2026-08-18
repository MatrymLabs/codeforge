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

_REPO = Path(__file__).resolve().parent.parent
_WORKFLOWS = str(_REPO / ".github" / "workflows" / "*.yml")


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


def test_every_path_the_security_scan_names_still_exists():
    """A scanner aimed at a directory that no longer exists reports success, loudly and falsely.

    CI ran `bandit -c pyproject.toml -r parts forge.py -q` from the day `parts/` was retired
    (2026-08-02, the kernel/adapters restructure) until 2026-08-18. bandit EXITS 0 ON A PATH THAT
    DOES NOT EXIST. The step scanned exactly one file, `forge.py`, and reported a clean static
    security scan for the whole tree every single run.

    Nothing caught it because nothing was wrong in the way CI can see: no error, no red, no
    missing step. It was green for the same reason an unplugged smoke detector is silent.

    Real coverage survived only because `make sast` names the directories separately and runs
    inside `make check`. That is luck, not design, and this test is the design.
    """
    sast = _sast_recipe()
    assert sast, "could not find the sast target in the Makefile; this test proves nothing"

    named, missing = [], []
    for line in sast:
        if "bandit" not in line:
            continue
        # bandit's scan targets are the arguments to -r, up to the next flag. Reading only those
        # avoids mistaking a flag's VALUE (--severity-level medium) for a path.
        tokens = line.split()
        if "-r" not in tokens:
            continue
        for token in tokens[tokens.index("-r") + 1 :]:
            if token.startswith("-"):
                break
            named.append(token)
            if not (_REPO / token).exists():
                missing.append(token)

    assert named, "the sast target names no scan paths at all; that is the defect, not a pass"
    assert missing == [], (
        f"make sast points bandit at {missing}, which do not exist. bandit exits 0 on a missing "
        f"path, so this scan silently covers nothing. Paths named: {named}"
    )


def _sast_recipe() -> list[str]:
    """The recipe lines of the Makefile's `sast` target."""
    lines = (_REPO / "Makefile").read_text(encoding="utf-8").splitlines()
    recipe, collecting = [], False
    for line in lines:
        if line.startswith("sast:"):
            collecting = True
            continue
        if collecting:
            if line.startswith("\t"):
                recipe.append(line.strip())
            elif line.strip() and not line.startswith("#"):
                break
    return recipe


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
