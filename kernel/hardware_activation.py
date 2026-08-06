"""Explicit bridge from Hardware Store lifecycle state to runtime plugins.

The bridge accepts an already-constructed trusted object and a PluginRegistry. It never imports
component source, evaluates manifests, or activates anything during discovery/startup.
"""

from __future__ import annotations

import fcntl
import json
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from kernel.hardware_lifecycle import HardwareLifecycleError, HardwareRegistry
from kernel.permission_policy import PermissionContext, PermissionPolicy
from kernel.shelf import hashchain
from kernel.shelf.atomic_write import atomic_write_text
from kernel.shelf.plugin_registry import PluginInfo, PluginRegistry


class ActivationApprovalError(HardwareLifecycleError):
    """An activation approval is expired, mismatched, malformed, or already consumed."""


@dataclass(frozen=True)
class ActivationApproval:
    """One-time authority to activate an exact component version in one Seed scope."""

    approval_id: str
    component_id: str
    version: str
    seed_id: str
    approved_by: str
    expires_at: str
    artifact_digest: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "approval_id",
            "component_id",
            "version",
            "seed_id",
            "approved_by",
            "expires_at",
        ):
            if not getattr(self, field_name).strip():
                raise ActivationApprovalError(f"approval {field_name} must not be empty")

    def assert_valid(
        self,
        *,
        component_id: str,
        version: str,
        seed_id: str,
        now: datetime,
        artifact_digest: str = "",
    ) -> None:
        if (self.component_id, self.version, self.seed_id) != (component_id, version, seed_id):
            raise ActivationApprovalError(
                "approval does not match the component version and Seed scope"
            )
        try:
            expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ActivationApprovalError("approval expiry must be ISO-8601") from exc
        if expires.tzinfo is None or now.astimezone(UTC) >= expires.astimezone(UTC):
            raise ActivationApprovalError("activation approval is expired")
        if self.artifact_digest and self.artifact_digest != artifact_digest:
            raise ActivationApprovalError("approval does not match the exact artifact digest")

    def to_dict(self) -> dict[str, str]:
        return {
            "approval_id": self.approval_id,
            "component_id": self.component_id,
            "version": self.version,
            "seed_id": self.seed_id,
            "approved_by": self.approved_by,
            "expires_at": self.expires_at,
            "artifact_digest": self.artifact_digest,
        }


@dataclass
class ActivationApprovalLedger:
    """Durable one-time-use ledger for activation approvals.

    The in-process mutex is supplemented by an advisory lock file so separate Seed workers cannot
    both read the same unused approval before either persists the consumption. A separate
    hash-chained audit ledger records each successful consumption without changing the legacy used
    ID file format.
    """

    path: Path
    audit_path: Path | None = None
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.audit_path = self.audit_path or self.path.with_suffix(".audit.jsonl")

    def _audit_file(self) -> Path:
        path = self.audit_path
        if path is None:  # defensive for callers mutating a non-frozen dataclass after init
            raise ActivationApprovalError("approval audit path is not configured")
        return Path(path)

    @contextmanager
    def _exclusive(self) -> Iterator[None]:
        """Serialize consumption across threads and OS processes."""
        lock_path = self.path.with_suffix(f"{self.path.suffix}.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _used(self) -> set[str]:
        if not self.path.is_file():
            return set()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ActivationApprovalError(f"cannot read approval ledger: {exc}") from exc
        if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
            raise ActivationApprovalError("approval ledger must be a list of IDs")
        return set(raw)

    def consume(
        self,
        approval_id: str,
        *,
        actor_id: str = "",
        seed_id: str = "",
        component_id: str = "",
        version: str = "",
        artifact_digest: str = "",
    ) -> None:
        """Atomically record one approval use; replay is refused."""
        with self._lock, self._exclusive():
            used = self._used()
            if approval_id in used:
                raise ActivationApprovalError(
                    f"activation approval {approval_id!r} was already used"
                )
            used.add(approval_id)
            atomic_write_text(self.path, json.dumps(sorted(used), indent=2) + "\n", fsync=True)
            try:
                hashchain.append(
                    self._audit_file(),
                    {
                        "action": "activation_approval_consumed",
                        "approval_id": approval_id,
                        "actor_id": actor_id,
                        "seed_id": seed_id,
                        "component_id": component_id,
                        "version": version,
                        "artifact_digest": artifact_digest,
                        "recorded_at": datetime.now(UTC).isoformat(),
                    },
                )
            except Exception as exc:
                raise ActivationApprovalError(
                    f"activation approval audit could not be persisted: {exc}"
                ) from exc

    def audit_records(self) -> tuple[dict[str, object], ...]:
        """Read and verify the durable consumption audit chain."""
        try:
            return tuple(link.payload for link in hashchain.read(self._audit_file()))
        except (OSError, UnicodeDecodeError, hashchain.HashChainError) as exc:
            raise ActivationApprovalError(f"cannot read approval audit: {exc}") from exc


def new_approval_id() -> str:
    """Mint an opaque approval identifier for a caller's approval record."""
    return f"approval-{secrets.token_hex(8)}"


def activate_hardware_component[T](
    hardware: HardwareRegistry,
    component_id: str,
    runtime: PluginRegistry[T],
    info: PluginInfo,
    plugin: T,
) -> None:
    """Register one approved/installed component in the runtime registry.

    Activation is a deliberate operator action. The object is supplied by trusted platform code;
    this function does not resolve ``source`` from the Hardware Card.
    """
    record = hardware.get(component_id)
    if record is None:
        raise HardwareLifecycleError(f"component {component_id!r} is not discovered")
    if record.state != "installed":
        raise HardwareLifecycleError(
            f"component {component_id!r} must be installed before runtime activation"
        )
    if info.name != component_id:
        raise HardwareLifecycleError(
            f"runtime plugin name {info.name!r} does not match {component_id!r}"
        )
    active = hardware.transition(component_id, "active")
    try:
        runtime.register(info, plugin)
    except Exception:
        hardware.transition(component_id, "installed")
        raise
    assert active.state == "active"


def activate_hardware_component_with_approval[T](
    hardware: HardwareRegistry,
    component_id: str,
    runtime: PluginRegistry[T],
    info: PluginInfo,
    plugin: T,
    *,
    approval: ActivationApproval,
    ledger: ActivationApprovalLedger,
    seed_id: str,
    now: datetime | None = None,
    artifact_digest: str = "",
    promotion_packet: object | None = None,
    promotion_packets: object | None = None,
    policy: PermissionPolicy | None = None,
    permission: PermissionContext | None = None,
) -> None:
    """Activate only after promotion evidence and a one-time exact-scope approval.

    Already-installed records remain compatible with the lower-level lifecycle API. When a caller
    supplies a promotion packet, this boundary validates and persists it before moving a validated
    component through approval and installation; activation itself still consumes the separate
    one-time approval.
    """
    record = hardware.get(component_id)
    if record is None:
        raise ActivationApprovalError(f"component {component_id!r} is not discovered")
    if record.state != "installed" and promotion_packet is None:
        raise ActivationApprovalError(
            f"component {component_id!r} must be installed before runtime activation"
        )
    if promotion_packet is not None:
        if promotion_packets is None:
            raise ActivationApprovalError("promotion packet storage is required")
        try:
            promotion_packet.validate(record)
            promotion_packets.save(promotion_packet)
        except Exception as exc:
            if isinstance(exc, ActivationApprovalError):
                raise
            raise ActivationApprovalError(f"promotion evidence was refused: {exc}") from exc
        if record.state == "validated":
            record = hardware.transition(component_id, "approved")
        if record.state == "approved":
            record = hardware.transition(component_id, "installed")
        if record.state != "installed":
            raise ActivationApprovalError("promotion packet did not produce an installed component")
    if info.name != component_id:
        raise ActivationApprovalError(f"runtime plugin name {info.name!r} does not match component")
    if (policy is None) != (permission is None):
        raise ActivationApprovalError("policy and permission must be supplied together")
    if policy is not None and permission is not None:
        if approval.approved_by == permission.actor_id:
            raise ActivationApprovalError(
                "component activation requires separate approval and operation"
            )
        try:
            policy.require(
                permission,
                capability="component.activate",
                scope=seed_id,
            )
        except Exception as exc:
            raise ActivationApprovalError(f"activation authorization refused: {exc}") from exc
    approval.assert_valid(
        component_id=component_id,
        version=record.version,
        seed_id=seed_id,
        artifact_digest=artifact_digest,
        now=now or datetime.now(UTC),
    )
    ledger.consume(
        approval.approval_id,
        actor_id=permission.actor_id if permission is not None else "",
        seed_id=seed_id,
        component_id=component_id,
        version=record.version,
        artifact_digest=artifact_digest,
    )
    activate_hardware_component(hardware, component_id, runtime, info, plugin)


def restore_active_hardware_component[T](
    hardware: HardwareRegistry,
    component_id: str,
    runtime: PluginRegistry[T],
    info: PluginInfo,
    plugin: T,
) -> None:
    """Rebind a trusted runtime object to an already-active component after a Seed restart."""
    record = hardware.get(component_id)
    if record is None or record.state != "active":
        raise HardwareLifecycleError(f"component {component_id!r} is not active")
    if info.name != component_id:
        raise HardwareLifecycleError(
            f"runtime plugin name {info.name!r} does not match {component_id!r}"
        )
    runtime.register(info, plugin)


def disable_hardware_component[T](
    hardware: HardwareRegistry,
    component_id: str,
    runtime: PluginRegistry[T],
) -> None:
    """Disable a live plugin and retain the governed lifecycle evidence."""
    record = hardware.get(component_id)
    if record is None or record.state != "active":
        raise HardwareLifecycleError(f"component {component_id!r} is not active")
    runtime.disable(component_id)
    try:
        hardware.transition(component_id, "disabled")
    except Exception:
        runtime.enable(component_id)
        raise


def remove_hardware_component[T](
    hardware: HardwareRegistry,
    component_id: str,
    runtime: PluginRegistry[T],
    *,
    consumer: str,
) -> None:
    """Remove one Seed's runtime binding and consumer claim without deleting the component.

    Active components are disabled first. The runtime binding is removed only after the durable
    lifecycle transition succeeds; if the consumer record cannot be removed, the runtime binding
    is restored so the failure remains recoverable and explicit.
    """
    record = hardware.get(component_id)
    if record is None:
        raise HardwareLifecycleError(f"component {component_id!r} is not discovered")
    if record.state == "active":
        disable_hardware_component(hardware, component_id, runtime)
    elif record.state != "disabled":
        raise HardwareLifecycleError("component removal requires an active or disabled component")
    binding = runtime.remove(component_id)
    try:
        hardware.unregister_consumer(component_id, consumer)
    except Exception:
        runtime.register(*binding)
        runtime.disable(component_id)
        raise
