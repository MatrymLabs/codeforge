"""Small, explicit model transformations used by Seed target generators.

This module intentionally contains a family of typed transformation records rather than a
universal intermediate representation.  The first proof transforms the existing ``ProjectModel``
into the CLI generator's narrower ``CliTargetModel``.  The result is deterministic, versioned, and
safe to persist alongside generated-artifact evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass

from kernel.seedlab.project_model import ProjectModel, Provenance

_SLUG = re.compile(r"[^a-z0-9]+")


class TransformationError(ValueError):
    """The source model cannot satisfy a transformation's preconditions."""


@dataclass(frozen=True)
class TransformationSpec:
    """Versioned metadata and declared boundaries for one model transformation."""

    transformation_id: str
    version: str
    source_model_type: str
    source_model_version: str
    target_model_type: str
    target_model_version: str
    implementation: str
    preconditions: tuple[str, ...]
    postconditions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CliTargetModel:
    """The deliberately narrow target model consumed by the CLI generator."""

    identity: str
    commands: tuple[str, ...]
    provenance: Provenance

    def to_dict(self) -> dict[str, object]:
        return {
            "model_type": "CliTargetModel",
            "model_version": "1",
            "identity": self.identity,
            "commands": list(self.commands),
            "provenance": asdict(self.provenance),
        }


@dataclass(frozen=True)
class TransformationResult:
    """The output and evidence of one deterministic transformation invocation."""

    spec: TransformationSpec
    source_model_digest: str
    target_model_digest: str
    target: CliTargetModel
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "transformation": self.spec.to_dict(),
            "source_model_digest": self.source_model_digest,
            "target_model_digest": self.target_model_digest,
            "target": self.target.to_dict(),
            "diagnostics": list(self.diagnostics),
        }


CLI_PROJECT_TO_TARGET = TransformationSpec(
    transformation_id="codeforge.project-model-to-cli-target",
    version="1.0",
    source_model_type="ProjectModel",
    source_model_version="1",
    target_model_type="CliTargetModel",
    target_model_version="1",
    implementation="kernel.seedlab.transformation:transform_project_to_cli",
    preconditions=(
        "identity is a non-empty string",
        "actions contains only strings",
        "provenance has a stable source identity",
    ),
    postconditions=(
        "target identity is non-empty",
        "target commands are normalized and non-empty",
        "source and target digests are recorded",
    ),
)


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _command_slug(value: str) -> str:
    return _SLUG.sub("_", value.lower()).strip("_")


def transform_project_to_cli(model: ProjectModel) -> TransformationResult:
    """Transform one validated project model into the CLI target model.

    The transformation deliberately carries only CLI concerns.  It does not pretend that a CLI
    target is a universal representation of the source model, and it does not execute code.
    """

    if not isinstance(model, ProjectModel):
        raise TransformationError("source must be a ProjectModel")
    if not isinstance(model.identity, str) or not model.identity.strip():
        raise TransformationError("ProjectModel identity must be a non-empty string")
    if not isinstance(model.provenance, Provenance):
        raise TransformationError("ProjectModel provenance is required")
    if any(not isinstance(action, str) for action in model.actions):
        raise TransformationError("ProjectModel actions must contain only strings")

    source_digest = _digest(model.to_dict())
    commands = tuple(_command_slug(action) for action in model.actions if _command_slug(action))
    diagnostics: list[str] = []
    if not commands:
        commands = ("info",)
        diagnostics.append("no usable actions were modeled; generated the default info command")
    if model.unknowns:
        diagnostics.append(f"source model carries {len(model.unknowns)} unresolved unknown(s)")

    target = CliTargetModel(
        identity=model.identity.strip(),
        commands=commands,
        provenance=model.provenance,
    )
    return TransformationResult(
        spec=CLI_PROJECT_TO_TARGET,
        source_model_digest=source_digest,
        target_model_digest=_digest(target.to_dict()),
        target=target,
        diagnostics=tuple(diagnostics),
    )
