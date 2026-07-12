"""CARD: name_check -- the game adapter for validation: preview whether a character name is valid.

A player runs `namecheck <name>` to see, before registering, whether a name is allowed and, if not,
exactly why. The rules (required, the name pattern, not a reserved word) live in a `Validator`
(parts/validation). The SAME validation core checks a signup payload in a practical app
(parts/payload_check); only the adapter and the rule set differ.
"""

from __future__ import annotations

from parts.session import Session
from parts.validation import Data, Issue, Validator, matches, required

_RESERVED = ("admin", "system", "root", "null", "owner", "wizard")
_NAME_PATTERN = (
    "must be 2-16 characters: lowercase letters, digits, or underscores, starting with a letter"
)


def _not_reserved(data: Data) -> Issue | None:
    name = data.get("name")
    if isinstance(name, str) and name.strip().lower() in _RESERVED:
        return Issue("name", "is a reserved name")
    return None


_VALIDATOR = Validator(
    required("name"),
    matches("name", r"[a-z][a-z0-9_]{1,15}", _NAME_PATTERN),
    _not_reserved,
)


def name_check(session: Session, arg: str = "") -> str:
    """The `namecheck` verb: report whether a proposed name is valid, and why not if it isn't."""
    name = arg.strip().lower()
    result = _VALIDATOR.check({"name": name})
    if result.is_valid:
        return f"'{name}' is a valid character name."
    reasons = "\n".join(f"  - {issue.message}" for issue in result.issues)
    return f"That name won't work:\n{reasons}"
