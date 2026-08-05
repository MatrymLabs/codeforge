"""Governed runtime binding for approved Hardware Store components.

The Hardware Store owns lifecycle evidence and the plugin registry owns live objects.  This module
is the production seam between them: it requires an authenticated Seed-scoped operator, a
one-time approval, and an explicitly registered trusted provider.  Providers are ordinary Python
callables registered by trusted platform code; this module never imports component source or
evaluates a manifest.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from kernel.hardware_activation import (
    ActivationApproval,
    ActivationApprovalLedger,
    activate_hardware_component_with_approval,
    disable_hardware_component,
    remove_hardware_component,
    restore_active_hardware_component,
)
from kernel.hardware_lifecycle import HardwareLifecycleError, HardwareRegistry
from kernel.permission_policy import PermissionDenied, PermissionPolicy
from kernel.session_identity import SessionIdentity, SessionIdentityError
from kernel.shelf.plugin_registry import PluginInfo, PluginRegistry


class HardwareRuntimeError(HardwareLifecycleError):
    """A trusted provider or runtime operation was not valid for the selected Seed."""


@dataclass(frozen=True)
class TrustedHardwareProvider[T]:
    """A pre-constructed-code factory registered by trusted platform code.

    The factory is deliberately not discovered from a Hardware Card.  Registration is the trust
    boundary and must happen in application code that already owns the component implementation.
    """

    info: PluginInfo
    factory: Callable[[], T]

    def __post_init__(self) -> None:
        if not self.info.name.strip():
            raise HardwareRuntimeError("trusted provider name must not be empty")


@dataclass
class HardwareRuntimeController[T]:
    """Coordinate durable Hardware lifecycle state with one Seed's live plugin registry."""

    hardware: HardwareRegistry
    runtime: PluginRegistry[T]
    seed_id: str
    consumer: str
    providers: dict[str, TrustedHardwareProvider[T]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.seed_id.strip():
            raise HardwareRuntimeError("seed_id must not be empty")
        if not self.consumer.strip():
            raise HardwareRuntimeError("consumer must not be empty")

    def register_provider(
        self, info: PluginInfo, factory: Callable[[], T]
    ) -> TrustedHardwareProvider[T]:
        """Register one explicit trusted implementation, refusing duplicate bindings."""
        provider = TrustedHardwareProvider(info, factory)
        if info.name in self.providers:
            raise HardwareRuntimeError(f"provider {info.name!r} is already registered")
        self.providers[info.name] = provider
        return provider

    def _provider(self, component_id: str) -> TrustedHardwareProvider[T]:
        try:
            return self.providers[component_id]
        except KeyError as exc:
            raise HardwareRuntimeError(
                f"no trusted runtime provider is registered for {component_id!r}"
            ) from exc

    def _authorize(
        self,
        identity: SessionIdentity,
        policy: PermissionPolicy,
        *,
        capability: str,
        now: datetime | None = None,
    ) -> None:
        try:
            identity.require_seed(self.seed_id)
        except SessionIdentityError as exc:
            raise PermissionDenied(str(exc)) from exc
        if not identity.is_active(now):
            raise PermissionDenied(f"session {identity.session_id!r} is expired")
        policy.require(identity.permission_context(), capability=capability, scope=self.seed_id)

    def activate(
        self,
        component_id: str,
        *,
        approval: ActivationApproval,
        ledger: ActivationApprovalLedger,
        identity: SessionIdentity,
        policy: PermissionPolicy,
        now: datetime | None = None,
        artifact_digest: str = "",
    ) -> None:
        """Activate an installed component through its explicit trusted provider."""
        effective_now = now or datetime.now(UTC)
        self._authorize(identity, policy, capability="component.activate", now=effective_now)
        if approval.approved_by == identity.principal_id:
            raise PermissionDenied("component activation requires separate approval and operation")
        provider = self._provider(component_id)
        plugin = provider.factory()
        activate_hardware_component_with_approval(
            self.hardware,
            component_id,
            self.runtime,
            provider.info,
            plugin,
            approval=approval,
            ledger=ledger,
            seed_id=self.seed_id,
            now=effective_now,
            artifact_digest=artifact_digest,
        )
        try:
            self.hardware.register_consumer(component_id, self.consumer)
        except Exception:
            # Keep the durable and live states safe if consumer evidence cannot be recorded.
            disable_hardware_component(self.hardware, component_id, self.runtime)
            raise

    def restore_active(
        self,
        component_id: str,
        *,
        identity: SessionIdentity,
        policy: PermissionPolicy,
        now: datetime | None = None,
    ) -> None:
        """Rebind a durable active component after restart using a trusted provider."""
        self._authorize(identity, policy, capability="component.restore", now=now)
        provider = self._provider(component_id)
        restore_active_hardware_component(
            self.hardware,
            component_id,
            self.runtime,
            provider.info,
            provider.factory(),
        )

    def disable(
        self,
        component_id: str,
        *,
        identity: SessionIdentity,
        policy: PermissionPolicy,
        now: datetime | None = None,
    ) -> None:
        """Disable a live component without deleting its durable Hardware evidence."""
        self._authorize(identity, policy, capability="component.disable", now=now)
        disable_hardware_component(self.hardware, component_id, self.runtime)

    def remove(
        self,
        component_id: str,
        *,
        identity: SessionIdentity,
        policy: PermissionPolicy,
        now: datetime | None = None,
    ) -> None:
        """Remove this Seed's binding and consumer claim after governed disablement."""
        self._authorize(identity, policy, capability="component.disable", now=now)
        remove_hardware_component(self.hardware, component_id, self.runtime, consumer=self.consumer)

    def active_names(self) -> tuple[str, ...]:
        """Return live bindings, suitable for truthful startup and Console status."""
        return tuple(self.runtime.names())

    def provider_names(self) -> tuple[str, ...]:
        """Return explicitly registered providers, without implying activation."""
        return tuple(self.providers)

    def status(self) -> dict[str, object]:
        """Return a truthful read-only projection of durable and live runtime state.

        This is intentionally a projection, not a lifecycle operation: it never discovers,
        activates, restores, or mutates a component.  Gateway and Master Client boundaries can
        use it to report what this Seed actually has wired after startup or recovery.
        """
        records = self.hardware.all()
        return {
            "seed": self.seed_id,
            "consumer": self.consumer,
            "providers": list(self.provider_names()),
            "active_bindings": list(self.active_names()),
            "components": [
                {
                    "component_id": record.component_id,
                    "state": record.state,
                    "consumers": list(record.consumers),
                }
                for record in records
            ],
        }

    def publish_event(self, event: object, fallback: Callable[[object], None]) -> None:
        """Publish through the active Event Ledger, or use the existing safe fallback."""
        publisher = self.runtime.get("event-ledger")
        if publisher is None:
            fallback(event)
            return
        if not callable(publisher):
            raise HardwareRuntimeError("active event-ledger provider is not callable")
        publisher(event)


def register_builtin_providers(
    controller: HardwareRuntimeController[object],
) -> HardwareRuntimeController[object]:
    """Register built-in providers explicitly during trusted platform construction."""
    from kernel.seedlab.event_bridge import publish_seed_event

    controller.register_provider(
        PluginInfo(
            "event-ledger",
            version="0.2",
            capabilities=frozenset({"publish", "audit"}),
        ),
        publish_seed_event,
    )
    return controller
