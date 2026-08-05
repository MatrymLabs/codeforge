"""Machine-checkable promotion packets for Hardware Store components.

Promotion is a governance transition, not a scanner result. The packet requires provenance,
license, SBOM, security, accessibility, test, ownership, and consumer evidence, plus an explicit
human decision before a validated component can become approved.
"""

from __future__ import annotations

import fcntl
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any

from kernel.hardware_lifecycle import HardwareLifecycleError, HardwareRecord, HardwareRegistry
from kernel.permission_policy import PermissionContext, PermissionPolicy
from kernel.shelf import hashchain
from kernel.shelf.atomic_write import atomic_write_text


class HardwarePromotionError(HardwareLifecycleError):
    """A promotion packet is incomplete, inconsistent, or not authorized."""


@dataclass(frozen=True)
class PromotionPacket:
    """Evidence required to promote one exact Hardware component version."""

    packet_id: str
    component_id: str
    version: str
    artifact_digest: str
    provenance_id: str
    license_decision: str
    sbom_reference: str
    security_evidence: str
    accessibility_evidence: str
    test_evidence: str
    owner: str
    consumers: tuple[str, ...]
    human_reviewer: str
    operator_decision: str
    automated_only: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "packet_id",
            "component_id",
            "version",
            "artifact_digest",
            "provenance_id",
            "license_decision",
            "sbom_reference",
            "security_evidence",
            "accessibility_evidence",
            "test_evidence",
            "owner",
            "human_reviewer",
            "operator_decision",
        ):
            if not getattr(self, field_name).strip():
                raise HardwarePromotionError(f"promotion packet {field_name} must not be empty")
        if not self.consumers or any(not consumer.strip() for consumer in self.consumers):
            raise HardwarePromotionError("promotion packet needs at least one named consumer")

    def validate(self, record: HardwareRecord) -> None:
        """Reject a packet unless every required evidence claim is machine-checkable."""
        if (self.component_id, self.version) != (record.component_id, record.version):
            raise HardwarePromotionError("promotion packet does not match installed component")
        if self.license_decision != "approved":
            raise HardwarePromotionError("license decision is not approved")
        for field_name in (
            "provenance_id",
            "artifact_digest",
            "sbom_reference",
            "security_evidence",
            "accessibility_evidence",
            "test_evidence",
            "human_reviewer",
        ):
            if not getattr(self, field_name).strip():
                raise HardwarePromotionError(f"promotion packet lacks {field_name}")
        if self.operator_decision != "approved":
            raise HardwarePromotionError("operator decision is not approved")
        if self.automated_only:
            raise HardwarePromotionError("automated evidence cannot promote a component alone")

    def to_dict(self) -> dict[str, object]:
        return {
            "packet_id": self.packet_id,
            "component_id": self.component_id,
            "version": self.version,
            "artifact_digest": self.artifact_digest,
            "provenance_id": self.provenance_id,
            "license_decision": self.license_decision,
            "sbom_reference": self.sbom_reference,
            "security_evidence": self.security_evidence,
            "accessibility_evidence": self.accessibility_evidence,
            "test_evidence": self.test_evidence,
            "owner": self.owner,
            "consumers": list(self.consumers),
            "human_reviewer": self.human_reviewer,
            "operator_decision": self.operator_decision,
            "automated_only": self.automated_only,
        }


@dataclass
class PromotionPacketStore:
    """Durable, idempotent storage for promotion packets and their audit trail."""

    root: Path
    audit_path: Path | None = None
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.audit_path = self.audit_path or self.root / "promotion-audit.jsonl"

    def _audit_file(self) -> Path:
        path = self.audit_path
        if path is None:
            raise HardwarePromotionError("promotion audit path is not configured")
        return Path(path)

    @contextmanager
    def _exclusive(self) -> Iterator[None]:
        lock_path = self.root / ".promotion.lock"
        with lock_path.open("a", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def save(self, packet: PromotionPacket) -> None:
        target = self.root / f"{packet.packet_id}.json"
        encoded = json.dumps(packet.to_dict(), indent=2, sort_keys=True) + "\n"
        with self._lock, self._exclusive():
            if target.is_file() and target.read_text(encoding="utf-8") != encoded:
                raise HardwarePromotionError(
                    f"promotion packet {packet.packet_id!r} already has different evidence"
                )
            if target.is_file():
                return
            atomic_write_text(target, encoded, fsync=True)
            self._append_audit(
                {
                    "action": "promotion_packet_stored",
                    "packet_id": packet.packet_id,
                    "component_id": packet.component_id,
                    "version": packet.version,
                }
            )

    def record_authorization(self, packet: PromotionPacket, actor_id: str) -> None:
        """Persist the human/policy authorization before applying the registry transition."""
        if not actor_id.strip():
            raise HardwarePromotionError("promotion authorization actor must not be empty")
        with self._lock, self._exclusive():
            self._append_audit(
                {
                    "action": "promotion_authorized",
                    "packet_id": packet.packet_id,
                    "component_id": packet.component_id,
                    "version": packet.version,
                    "actor_id": actor_id,
                }
            )

    def audit_records(self) -> tuple[dict[str, Any], ...]:
        """Read and verify the append-only promotion audit chain."""
        try:
            return tuple(link.payload for link in hashchain.read(self._audit_file()))
        except (OSError, UnicodeDecodeError, hashchain.HashChainError) as exc:
            raise HardwarePromotionError(f"cannot read promotion audit: {exc}") from exc

    def _append_audit(self, payload: dict[str, Any]) -> None:
        try:
            hashchain.append(self._audit_file(), payload)
        except Exception as exc:
            raise HardwarePromotionError(f"promotion audit could not be persisted: {exc}") from exc

    def load(self, packet_id: str) -> PromotionPacket:
        target = self.root / f"{packet_id}.json"
        if not target.is_file():
            raise HardwarePromotionError(f"unknown promotion packet: {packet_id!r}")
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise TypeError("packet must be an object")
            consumers = raw["consumers"]
            if not isinstance(consumers, list):
                raise TypeError("consumers must be a list")
            return PromotionPacket(
                packet_id=str(raw["packet_id"]),
                component_id=str(raw["component_id"]),
                version=str(raw["version"]),
                artifact_digest=str(raw["artifact_digest"]),
                provenance_id=str(raw["provenance_id"]),
                license_decision=str(raw["license_decision"]),
                sbom_reference=str(raw["sbom_reference"]),
                security_evidence=str(raw["security_evidence"]),
                accessibility_evidence=str(raw["accessibility_evidence"]),
                test_evidence=str(raw["test_evidence"]),
                owner=str(raw["owner"]),
                consumers=tuple(str(item) for item in consumers),
                human_reviewer=str(raw["human_reviewer"]),
                operator_decision=str(raw["operator_decision"]),
                automated_only=bool(raw.get("automated_only", False)),
            )
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise HardwarePromotionError(
                f"malformed promotion packet {packet_id!r}: {exc}"
            ) from exc


def promote_hardware_component(
    registry: HardwareRegistry,
    packets: PromotionPacketStore,
    packet: PromotionPacket,
    policy: PermissionPolicy | None = None,
    permission: PermissionContext | None = None,
) -> HardwareRecord:
    """Persist and apply a complete human-reviewed, policy-authorized promotion packet."""
    record = registry.get(packet.component_id)
    if record is None:
        raise HardwarePromotionError(f"component {packet.component_id!r} is not discovered")
    if record.state != "validated":
        raise HardwarePromotionError("only validated components may be promoted")
    if (policy is None) != (permission is None):
        raise HardwarePromotionError("policy and permission must be supplied together")
    if policy is not None and permission is not None:
        try:
            policy.require(
                permission,
                capability="hardware.promote",
                scope=f"component:{packet.component_id}",
            )
        except Exception as exc:
            raise HardwarePromotionError(f"promotion authorization refused: {exc}") from exc
    packet.validate(record)
    packets.save(packet)
    actor_id = permission.actor_id if permission is not None else packet.human_reviewer
    packets.record_authorization(packet, actor_id)
    return registry.transition(packet.component_id, "approved")
