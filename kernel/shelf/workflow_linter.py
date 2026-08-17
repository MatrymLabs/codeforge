"""CARD: workflow_linter -- lint a GitHub Actions workflow for permission, pinning, and secret risk.

Clean-room from the FWA + CI-hardening literature (least-privilege GitHub Actions,
"Hidden Costs of Automation", "On the GitHub Actions Language"). A complex, over-
privileged, or unpinned workflow is both WASTE (churn, hard to audit) and ABUSE
surface (a compromised or hallucinated action running with broad permissions).

The linter operates on the PARSED workflow (a Mapping), so the part itself is
dependency-free; the caller parses the YAML (yaml is ubiquitous, e.g. the
lint_yaml convenience below uses it only if available). Rules:

- unpinned-action : a `uses:` pinned to a tag/branch, not a full 40-hex commit SHA.
- broad-permissions : `permissions: write-all`, or a top-level write scope.
- no-permissions : no top-level `permissions:` (defaults to broad tokens).
- secret-sprawl : more distinct `secrets.*` references than the budget.
- job-complexity / step-complexity : more jobs/steps than the budget.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
_USES_REF = re.compile(r"\A(?P<name>[^@\s]+)@(?P<ref>.+)\Z")
_SECRET = re.compile(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)")
_WRITE_ALL = "write-all"


@dataclass(frozen=True)
class Finding:
    """One lint result: a rule id, a severity, where it is, and a message."""

    rule: str
    severity: str  # "high" | "medium" | "low"
    where: str
    message: str


@dataclass(frozen=True)
class Budget:
    """Tunable thresholds. Defaults are deliberately strict (least-privilege)."""

    max_jobs: int = 12
    max_steps_per_job: int = 25
    max_secrets: int = 8
    # local actions (./...) and reusable-workflow refs need no SHA pin
    require_sha_pins: bool = True


class WorkflowLintError(ValueError):
    """Raised when the workflow document is not a mapping."""


def _is_write(scope: object) -> bool:
    return isinstance(scope, str) and scope == "write"


def _check_permissions(doc: Mapping[str, object], findings: list[Finding]) -> None:
    perms = doc.get("permissions")
    if perms is None:
        findings.append(
            Finding(
                "no-permissions",
                "medium",
                "top-level",
                "no top-level permissions: the workflow token defaults to broad scopes; "
                "set least-privilege (e.g. permissions: contents: read).",
            )
        )
        return
    if perms == _WRITE_ALL:
        findings.append(
            Finding(
                "broad-permissions",
                "high",
                "top-level",
                "permissions: write-all grants every scope; scope it down.",
            )
        )
        return
    if isinstance(perms, Mapping):
        for scope, level in perms.items():
            if _is_write(level):
                findings.append(
                    Finding(
                        "broad-permissions",
                        "medium",
                        "top-level",
                        f"top-level '{scope}: write'; grant write per-job instead.",
                    )
                )


def _check_uses(where: str, uses: str, budget: Budget, findings: list[Finding]) -> None:
    if uses.startswith("./") or uses.startswith("."):  # noqa: PIE810
        return  # a local action, no SHA to pin
    m = _USES_REF.match(uses.strip())
    if not m:
        return
    ref = m.group("ref")
    if budget.require_sha_pins and not _SHA.match(ref):
        findings.append(
            Finding(
                "unpinned-action",
                "high",
                where,
                f"action '{uses}' is not SHA-pinned; a moved tag is a supply-chain risk.",
            )
        )


def _iter_jobs(doc: Mapping[str, object]) -> Iterator[tuple[str, Mapping[str, object]]]:
    jobs = doc.get("jobs")
    if isinstance(jobs, Mapping):
        for job_id, job in jobs.items():
            if isinstance(job, Mapping):
                yield str(job_id), job


def lint_workflow(
    doc: Mapping[str, object], *, name: str = "", budget: Budget | None = None
) -> list[Finding]:
    """Return the findings for one parsed workflow document (empty = clean)."""
    if not isinstance(doc, Mapping):
        raise WorkflowLintError("workflow document must be a mapping (parsed YAML)")  # noqa: TRY003
    budget = budget or Budget()
    findings: list[Finding] = []

    _check_permissions(doc, findings)

    jobs = list(_iter_jobs(doc))
    if len(jobs) > budget.max_jobs:
        findings.append(
            Finding(
                "job-complexity",
                "low",
                name or "workflow",
                f"{len(jobs)} jobs exceeds the budget of {budget.max_jobs}.",
            )
        )
    for job_id, job in jobs:
        steps = job.get("steps")
        step_list = steps if isinstance(steps, list) else []
        if len(step_list) > budget.max_steps_per_job:
            findings.append(
                Finding(
                    "step-complexity",
                    "low",
                    f"job:{job_id}",
                    f"{len(step_list)} steps exceeds the budget of {budget.max_steps_per_job}.",
                )
            )
        for i, step in enumerate(step_list):
            if isinstance(step, Mapping) and isinstance(step.get("uses"), str):
                _check_uses(f"job:{job_id} step:{i}", step["uses"], budget, findings)

    _check_secrets(doc, name, budget, findings)
    return findings


def _check_secrets(
    doc: Mapping[str, object], name: str, budget: Budget, findings: list[Finding]
) -> None:
    secrets = set(_SECRET.findall(_flatten(doc)))
    if len(secrets) > budget.max_secrets:
        findings.append(
            Finding(
                "secret-sprawl",
                "medium",
                name or "workflow",
                f"{len(secrets)} secrets referenced exceeds the budget of {budget.max_secrets}.",
            )
        )


def _flatten(value: object) -> str:
    """A flat string of every scalar in the document (for a coarse secret scan)."""
    if isinstance(value, Mapping):
        return " ".join(_flatten(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(v) for v in value)
    return str(value)


def worst_severity(findings: list[Finding]) -> str | None:
    """The most severe finding level present, or None when clean."""
    order = {"high": 3, "medium": 2, "low": 1}
    if not findings:
        return None
    return max(findings, key=lambda f: order.get(f.severity, 0)).severity


def lint_yaml(text: str, *, name: str = "", budget: Budget | None = None) -> list[Finding]:
    """Convenience: parse a workflow YAML string and lint it. Requires PyYAML."""
    try:
        import yaml  # optional; the core lint_workflow is dependency-free  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise WorkflowLintError(  # noqa: TRY003
            "lint_yaml needs PyYAML; use lint_workflow(parsed_dict) to stay stdlib"
        ) from exc
    doc = yaml.safe_load(text)
    return lint_workflow(doc, name=name, budget=budget)
