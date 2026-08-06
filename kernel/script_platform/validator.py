"""Static validation for script manifests before a worker can be selected."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .models import ScriptManifest

Severity = Literal["error", "warning"]
_ID = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_LANGUAGES = {"dsl", "lua", "wasm", "python", "quickjs"}
_DANGEROUS = {"shell", "process", "filesystem", "network", "native", "ffi", "import"}


@dataclass(frozen=True)
class ValidationIssue:
    severity: Severity
    code: str
    message: str
    path: str


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")


class ManifestValidator:
    """Validate policy and shape; execution remains the supervisor's responsibility."""

    def validate(self, manifest: ScriptManifest) -> ValidationReport:
        issues: list[ValidationIssue] = []

        def error(code: str, message: str, path: str) -> None:
            issues.append(ValidationIssue("error", code, message, path))

        if not _ID.fullmatch(manifest.script_id):
            error("invalid_id", "script_id must be a stable lowercase identifier", "script_id")
        if manifest.language not in _LANGUAGES:
            error(
                "unsupported_language", "language is not an enabled platform language", "language"
            )
        if not _HASH.fullmatch(manifest.source_hash):
            error("invalid_hash", "source_hash must be a lowercase SHA-256 digest", "source.sha256")
        if not manifest.entrypoints:
            error("missing_entrypoint", "at least one event entrypoint is required", "entrypoints")
        for event, function in manifest.entrypoints.items():
            if not event.strip() or not function.strip():
                error("invalid_entrypoint", "event and function must not be empty", "entrypoints")
            if not _ID.fullmatch(event) and not event.startswith("timer."):
                error(
                    "invalid_event", "event must use a stable namespaced identifier", "entrypoints"
                )
        for seed_id in manifest.seed_ids:
            if not _ID.fullmatch(seed_id):
                error(
                    "invalid_scope",
                    "seed IDs must use stable lowercase identifiers",
                    "scope.seed_ids",
                )
        if not manifest.object_types:
            error(
                "missing_object_scope", "at least one object type is required", "scope.object_types"
            )
        if not manifest.provenance_id.strip():
            error("missing_provenance", "source provenance is required", "provenance.id")
        if not manifest.owner_id.strip():
            error("missing_owner", "an owner is required", "provenance.owner")
        if manifest.review_status not in {"draft", "approved"}:
            error("invalid_review", "review status must be draft or approved", "review.status")
        for capability in manifest.capabilities:
            operation, _, _resource = capability.partition(":")
            if operation in _DANGEROUS or operation.split(".", 1)[0] in _DANGEROUS:
                error(
                    "forbidden_capability",
                    "direct host capability is never grantable",
                    "capabilities",
                )
            if capability.strip() != capability or not operation:
                error(
                    "invalid_capability",
                    "capabilities must be non-empty operation tokens",
                    "capabilities",
                )
        if manifest.resource_policy.network != "deny":
            issues.append(
                ValidationIssue(
                    "warning",
                    "network_requires_review",
                    "network access requires an explicit connector review",
                    "resources.network",
                )
            )
        return ValidationReport(tuple(issues))
