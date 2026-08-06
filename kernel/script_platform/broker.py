"""Deny-by-default capability broker for isolated script workers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any


class BrokerError(PermissionError):
    """A script requested an operation outside its manifest or quota."""


@dataclass(frozen=True)
class CapabilityRequest:
    script_id: str
    source_revision: int
    seed_id: str
    operation: str
    resource: str = ""
    target_id: str | None = None
    arguments: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", dict(self.arguments))


@dataclass(frozen=True)
class CapabilityResult:
    value: Any


def _matches(grant: str, operation: str, resource: str) -> bool:
    granted_operation, separator, granted_resource = grant.partition(":")
    if granted_operation != operation:
        return False
    if not separator:
        return not resource
    if granted_resource.endswith("*"):
        return resource.startswith(granted_resource[:-1])
    return granted_resource == resource


class CapabilityBroker:
    """Route requests to explicit handlers without exposing host objects to scripts."""

    def __init__(
        self, *, capabilities: set[str] | frozenset[str], seed_id: str, host_call_limit: int = 64
    ):
        if not seed_id.strip():
            raise ValueError("seed_id must not be empty")
        if host_call_limit < 1:
            raise ValueError("host_call_limit must be positive")
        self._capabilities = frozenset(capabilities)
        self.seed_id = seed_id
        self._remaining = host_call_limit
        self._handlers: dict[str, Callable[[CapabilityRequest], Any]] = {}
        self.requests: list[CapabilityRequest] = []

    def register(self, operation: str, handler: Callable[[CapabilityRequest], Any]) -> None:
        if not operation.strip() or operation in self._handlers:
            raise ValueError(f"invalid or duplicate operation: {operation!r}")
        self._handlers[operation] = handler

    def call(self, request: CapabilityRequest) -> CapabilityResult:
        if request.seed_id != self.seed_id:
            raise BrokerError("cross-seed capability request denied")
        if self._remaining == 0:
            raise BrokerError("host-call quota exceeded")
        if not any(
            _matches(grant, request.operation, request.resource) for grant in self._capabilities
        ):
            raise BrokerError(f"capability denied: {request.operation}:{request.resource}")
        try:
            handler = self._handlers[request.operation]
        except KeyError as exc:
            raise BrokerError(f"no handler registered for {request.operation}") from exc
        self._remaining -= 1
        self.requests.append(request)
        return CapabilityResult(handler(request))
