"""CARD: payload_check -- the practical adapter for validation: validate a signup payload.

The reverse of parts/name_check: the SAME `Validator` core with a different rule set, checking a
business payload (an API request body or a form) instead of a game name. It returns every problem at
once so a caller can show them all, and never touches the input. Its cousins are form validation,
data-import checks, and business-rule enforcement.
"""

from __future__ import annotations

from parts.validation import (
    Data,
    ValidationResult,
    Validator,
    in_range,
    matches,
    of_type,
    required,
)

SIGNUP = Validator(
    required("username"),
    matches(
        "username", r"[a-z0-9_]{3,20}", "must be 3-20 lowercase letters, digits, or underscores"
    ),
    required("email"),
    matches("email", r"[^@\s]+@[^@\s]+\.[^@\s]+", "must be a valid email address"),
    of_type("age", int),
    in_range("age", 13, 120),
)


def validate_signup(payload: Data) -> ValidationResult:
    """Validate a signup payload against the signup rules; returns every issue at once."""
    return SIGNUP.check(payload)
