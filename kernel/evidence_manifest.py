"""Versioned, machine-readable evidence for a proof run."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class EvidenceManifestError(ValueError):
    """Raised when an evidence record cannot make a complete, honest claim."""


class Result(StrEnum):
    PASS = "PASS"  # noqa: S105  # nosec B105 - this is the public verdict literal
    FAIL = "FAIL"
    UNMEASURABLE = "UNMEASURABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class ExceptionRecord:
    owner: str
    reason: str
    expiration: str

    def __post_init__(self) -> None:
        for field_name in ("owner", "reason", "expiration"):
            if not getattr(self, field_name).strip():
                raise EvidenceManifestError(f"exception {field_name} is required")

    def to_dict(self) -> dict[str, str]:
        return {
            "owner": self.owner,
            "reason": self.reason,
            "expiration": self.expiration,
        }


@dataclass(frozen=True)
class EvidenceManifest:
    blueprint_id: str
    blueprint_version: str
    work_order_id: str
    proof_run_id: str
    tool: str
    tool_version: str
    commit_sha: str
    exact_command: tuple[str, ...] | list[str]
    exit_code: int | None
    result: Result | str
    artifact_sha256: str
    producing_bench: str
    verifying_bench: str
    exceptions: tuple[ExceptionRecord | Mapping[str, str], ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "blueprint_id",
            "blueprint_version",
            "work_order_id",
            "proof_run_id",
            "tool",
            "tool_version",
            "commit_sha",
            "artifact_sha256",
            "producing_bench",
            "verifying_bench",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise EvidenceManifestError(f"{field_name} is required")

        command = tuple(self.exact_command)
        if not command or any(not part for part in command):
            raise EvidenceManifestError("exact_command must contain at least one non-empty part")
        object.__setattr__(self, "exact_command", command)

        try:
            result = self.result if isinstance(self.result, Result) else Result(self.result)
        except ValueError as exc:
            raise EvidenceManifestError(
                "result must be PASS, FAIL, UNMEASURABLE, or NOT_APPLICABLE"
            ) from exc
        object.__setattr__(self, "result", result)

        if not re.fullmatch(r"[0-9a-fA-F]{64}", self.artifact_sha256):
            raise EvidenceManifestError("artifact_sha256 must be a 64-character SHA-256 hex digest")
        if result is Result.PASS and self.exit_code != 0:
            raise EvidenceManifestError("a PASS result requires exit_code 0")

        normalized_exceptions: list[ExceptionRecord] = []
        for exception in self.exceptions:
            if isinstance(exception, ExceptionRecord):
                normalized_exceptions.append(exception)
            elif isinstance(exception, Mapping):
                try:
                    normalized_exceptions.append(ExceptionRecord(**exception))
                except TypeError as exc:
                    raise EvidenceManifestError(
                        "exceptions require owner, reason, and expiration"
                    ) from exc
            else:
                raise EvidenceManifestError(
                    "exceptions must be ExceptionRecord objects or mappings"
                )
        object.__setattr__(self, "exceptions", tuple(normalized_exceptions))

    def to_dict(self) -> dict[str, Any]:
        result = Result(self.result).value
        exceptions = [
            exception.to_dict() if isinstance(exception, ExceptionRecord) else dict(exception)
            for exception in self.exceptions
        ]
        return {
            "blueprint_id": self.blueprint_id,
            "blueprint_version": self.blueprint_version,
            "work_order_id": self.work_order_id,
            "proof_run_id": self.proof_run_id,
            "tool": self.tool,
            "tool_version": self.tool_version,
            "commit_sha": self.commit_sha,
            "exact_command": list(self.exact_command),
            "exit_code": self.exit_code,
            "result": result,
            "artifact_sha256": self.artifact_sha256,
            "producing_bench": self.producing_bench,
            "verifying_bench": self.verifying_bench,
            "exceptions": exceptions,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EvidenceManifest:
        return cls(
            blueprint_id=data["blueprint_id"],
            blueprint_version=data["blueprint_version"],
            work_order_id=data["work_order_id"],
            proof_run_id=data["proof_run_id"],
            tool=data["tool"],
            tool_version=data["tool_version"],
            commit_sha=data["commit_sha"],
            exact_command=tuple(data["exact_command"]),
            exit_code=data["exit_code"],
            result=data["result"],
            artifact_sha256=data["artifact_sha256"],
            producing_bench=data["producing_bench"],
            verifying_bench=data["verifying_bench"],
            exceptions=tuple(data.get("exceptions", ())),
        )

    def write(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return destination


def write_manifest(manifest: EvidenceManifest, path: str | Path) -> Path:
    """Write one manifest using the manifest's validated serialization."""
    return manifest.write(path)


def sha256_file(path: str | Path) -> str:
    """Return the artifact digest that belongs in a manifest."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
