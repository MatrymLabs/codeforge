"""CARD: contract -- pin the shape a consumer depends on so a breaking provider change fails a test.

Clean-room reconstruction of consumer-driven contract testing (the Pact concept)
and the tolerant-reader pattern. Standard library only.

A CONSUMER (a client) declares a Contract: the fields and types it reads from a
provider's response for one interaction. A registry collects contracts. The
PROVIDER's own test verifies its actual response satisfies every registered
consumer contract, so dropping or retyping a field a client needs fails a test on
the provider side, with a precise path (hero.stats.level: expected int, got str).

Tolerant reader: extra provider fields are fine; missing or retyped required
fields are not. This is a test fixture, not a runtime part; it has no network.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

_SCALARS = (str, int, float, bool)


class ContractError(ValueError):
    """Raised when a contract or field is declared malformed."""


class ContractViolation(AssertionError):
    """Raised by check() when a sample does not satisfy a contract (test-facing)."""


@dataclass(frozen=True)
class ListOf:
    """Marks a field as an array of a scalar type or a nested Contract."""

    element: Any  # a scalar type or a Contract


@dataclass(frozen=True)
class Field:
    """One field a consumer depends on: a scalar type, a nested Contract, or a ListOf."""

    name: str
    type: Any
    required: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or self.name.strip() == "":
            raise ContractError("field name must be a non-empty string")
        if not _is_field_type(self.type):
            raise ContractError(f"field {self.name!r} has an invalid type spec: {self.type!r}")


def _is_field_type(spec: Any) -> bool:
    if isinstance(spec, ListOf):
        return _is_field_type(spec.element)
    if isinstance(spec, Contract):
        return True
    return isinstance(spec, type) and issubclass(spec, _SCALARS)


@dataclass(frozen=True)
class Contract:
    """The shape one consumer depends on for one named interaction."""

    name: str
    consumer: str
    fields: tuple[Field, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or self.name.strip() == "":
            raise ContractError("contract name must be a non-empty string")
        if not isinstance(self.consumer, str) or self.consumer.strip() == "":
            raise ContractError("contract consumer must be a non-empty string")
        if not self.fields:
            raise ContractError(f"contract {self.name!r} declares no fields")


def _scalar_ok(expected: type, value: Any) -> bool:
    if expected is bool:
        return isinstance(value, bool)
    if expected is int:  # a bool is an int subclass but a distinct wire type
        return isinstance(value, int) and not isinstance(value, bool)
    if expected is float:  # a JSON number may arrive as int
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, expected)


def _check_value(expected: Any, value: Any, path: str) -> list[str]:
    if isinstance(expected, Contract):
        return verify(expected, value, path=path + ".")
    if isinstance(expected, ListOf):
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            return [f"{path}: expected a list, got {type(value).__name__}"]
        out: list[str] = []
        for i, item in enumerate(value):
            out += _check_value(expected.element, item, f"{path}[{i}]")
        return out
    if not _scalar_ok(expected, value):
        return [f"{path}: expected {expected.__name__}, got {type(value).__name__}"]
    return []


def verify(contract: Contract, sample: Any, *, path: str = "") -> list[str]:
    """Return the list of violations (empty = the sample satisfies the contract)."""
    if not isinstance(sample, Mapping):
        where = path.rstrip(".") or contract.name
        return [f"{where}: expected an object, got {type(sample).__name__}"]
    violations: list[str] = []
    for spec in contract.fields:
        fpath = f"{path}{spec.name}"
        if spec.name not in sample:
            if spec.required:
                violations.append(f"{fpath}: required field missing")
            continue
        violations += _check_value(spec.type, sample[spec.name], fpath)
    return violations


def check(contract: Contract, sample: Any) -> None:
    """Raise ContractViolation if the sample does not satisfy the contract."""
    violations = verify(contract, sample)
    if violations:
        raise ContractViolation(
            f"contract {contract.name!r} (consumer {contract.consumer!r}) violated:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


class ContractRegistry:
    """Collects consumer contracts, keyed by interaction name."""

    def __init__(self) -> None:
        self._by_interaction: dict[str, list[Contract]] = {}

    def register(self, contract: Contract) -> None:
        if not isinstance(contract, Contract):
            raise ContractError("register expects a Contract")
        self._by_interaction.setdefault(contract.name, []).append(contract)

    def for_interaction(self, name: str) -> list[Contract]:
        return list(self._by_interaction.get(name, []))

    def interactions(self) -> list[str]:
        return sorted(self._by_interaction)


def verify_all(registry: ContractRegistry, name: str, sample: Any) -> list[str]:
    """Verify a provider sample against EVERY registered consumer contract for an interaction."""
    violations: list[str] = []
    for contract in registry.for_interaction(name):
        violations += [f"[{contract.consumer}] {v}" for v in verify(contract, sample)]
    return violations
