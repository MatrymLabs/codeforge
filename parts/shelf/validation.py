"""CARD: validation -- collect validation issues into a result: valid, or a list of clear errors.

Validate a mapping (a payload, a config, a form) against a set of composable rules, and get back a
`ValidationResult`: either valid, or every issue at once, each tagged with its field and a readable
message. Rules are small callables; a library of builders (`required`, `matches`, `in_range`, ...)
covers the common cases. This is the standard "accumulate all errors, fail loud" validation pattern,
reimplemented from the concept -- no code copied.

Framework-free and side-effect-free: rules never mutate the input; `raise_if_invalid` is the one
loud exit. One core, two lives: it checks a proposed character name in the game (`parts/name_check`)
and a signup payload in a practical app (`parts/payload_check`).

Provenance: independently_implemented_pattern (input/schema validation). No code copied.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

Data = Mapping[str, object]


@dataclass(frozen=True)
class Issue:
    """One validation problem: which field, and what is wrong."""

    field: str
    message: str

    def __str__(self) -> str:
        return f"{self.field}: {self.message}"


@dataclass(frozen=True)
class ValidationResult:
    """The outcome of validating a value: valid, or a tuple of issues (all of them, at once)."""

    issues: tuple[Issue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.issues

    @property
    def errors(self) -> tuple[str, ...]:
        return tuple(str(i) for i in self.issues)

    def merge(self, other: ValidationResult) -> ValidationResult:
        """Combine two results into one (issues concatenated)."""
        return ValidationResult(self.issues + other.issues)

    def raise_if_invalid(self) -> None:
        """The one loud exit: raise ValidationFailed if there are any issues."""
        if self.issues:
            raise ValidationFailed(self)


class ValidationFailed(ValueError):
    """Raised by `raise_if_invalid` when a value did not validate; carries the result."""

    def __init__(self, result: ValidationResult) -> None:
        self.result = result
        super().__init__("; ".join(result.errors))


Rule = Callable[[Data], Issue | None]


class Validator:
    """A bundle of rules. `check` runs them all and returns every issue at once."""

    def __init__(self, *rules: Rule) -> None:
        self._rules = rules

    def check(self, data: Data) -> ValidationResult:
        return ValidationResult(tuple(i for rule in self._rules if (i := rule(data)) is not None))


# --- Rule builders (the common cases) ---------------------------------------
# `required` catches missing/empty; the others fire only when a field is present and non-empty,
# so a required-and-malformed field reports "is required" once, not twice.


def required(field: str) -> Rule:
    def rule(data: Data) -> Issue | None:
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            return Issue(field, "is required")
        return None

    return rule


def of_type(field: str, typ: type, label: str | None = None) -> Rule:
    def rule(data: Data) -> Issue | None:
        if field in data and not isinstance(data[field], typ):
            return Issue(field, f"must be a {label or typ.__name__}")
        return None

    return rule


def matches(field: str, pattern: str, description: str) -> Rule:
    regex = re.compile(pattern)

    def rule(data: Data) -> Issue | None:
        value = data.get(field)
        if isinstance(value, str) and value.strip() and not regex.fullmatch(value):
            return Issue(field, description)
        return None

    return rule


def in_range(field: str, low: float, high: float) -> Rule:
    def rule(data: Data) -> Issue | None:
        value = data.get(field)
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and not low <= value <= high
        ):
            return Issue(field, f"must be between {low} and {high}")
        return None

    return rule


def one_of(field: str, choices: Iterable[object]) -> Rule:
    allowed = tuple(choices)

    def rule(data: Data) -> Issue | None:
        if field in data and data[field] not in allowed:
            return Issue(field, f"must be one of: {', '.join(map(str, allowed))}")
        return None

    return rule


def max_length(field: str, limit: int) -> Rule:
    def rule(data: Data) -> Issue | None:
        value = data.get(field)
        if isinstance(value, str) and len(value) > limit:
            return Issue(field, f"must be at most {limit} characters")
        return None

    return rule
