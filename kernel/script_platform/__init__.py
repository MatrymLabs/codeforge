"""Governed execution contracts for creator and Hardware Store scripts.

This package deliberately contains no language interpreter.  Source is described by a
validated :class:`ScriptManifest`, access is mediated by :class:`CapabilityBroker`,
state is portable JSON data, and execution is delegated to an external worker by
:class:`ScriptRunnerSupervisor`.
"""

from .audit import AuditLedger, ScriptAuditRecord
from .broker import BrokerError, CapabilityBroker, CapabilityRequest
from .models import (
    Attachment,
    LifecycleError,
    LifecycleManager,
    LifecycleStatus,
    ResourcePolicy,
    ScriptManifest,
    ScriptSandbox,
)
from .state import FileStateStore, InMemoryStateStore, StateConflict, StateStoreError
from .supervisor import (
    ScriptRunnerSupervisor,
    WorkerError,
    WorkerPolicy,
    WorkerResult,
)
from .validator import ManifestValidator, ValidationIssue, ValidationReport

__all__ = [
    "Attachment",
    "AuditLedger",
    "BrokerError",
    "CapabilityBroker",
    "CapabilityRequest",
    "FileStateStore",
    "InMemoryStateStore",
    "LifecycleError",
    "LifecycleManager",
    "LifecycleStatus",
    "ManifestValidator",
    "ResourcePolicy",
    "ScriptAuditRecord",
    "ScriptManifest",
    "ScriptRunnerSupervisor",
    "ScriptSandbox",
    "StateConflict",
    "StateStoreError",
    "ValidationIssue",
    "ValidationReport",
    "WorkerError",
    "WorkerPolicy",
    "WorkerResult",
]
