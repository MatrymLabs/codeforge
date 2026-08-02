"""CARD: sanitizer -- normalize untrusted text: strip controls, fold whitespace, cap length.

Turn messy or hostile input into a clean, bounded string: drop control characters, fold every run of
whitespace to a single space, trim, optionally lowercase, and cap the length. It is DETERMINISTIC
and IDEMPOTENT (sanitizing twice equals sanitizing once), the load-bearing property. This is
input normalization, reimplemented from the concept -- no code copied.

Framework-free and side-effect-free. It normalizes; it is NOT a security control (not escaping, not
crypto) -- pair it with proper output-encoding and parameterized queries at each boundary. One core,
two lives: a player's title in the game (`parts/titles`) and a stored field in a practical app
(`parts/field_sanitizer`).

Provenance: independently_implemented_pattern (input normalization). No code copied.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_WHITESPACE = re.compile(r"\s+")


class SanitizeError(ValueError):
    """A sanitize rule was built with invalid settings, or a non-string was passed. Fails loud."""


@dataclass(frozen=True)
class SanitizeRule:
    """How to normalize: which transforms to apply and the optional length cap."""

    strip_controls: bool = True
    collapse_whitespace: bool = True
    trim: bool = True
    lowercase: bool = False
    max_length: int | None = None

    def __post_init__(self) -> None:
        if self.max_length is not None and (
            not isinstance(self.max_length, int) or self.max_length < 0
        ):
            raise SanitizeError(f"max_length must be a non-negative int, got {self.max_length!r}")


DEFAULT = SanitizeRule()


def sanitize(text: str, rule: SanitizeRule = DEFAULT) -> str:
    """Normalize `text` per `rule`. Deterministic and idempotent."""
    if not isinstance(text, str):
        raise SanitizeError(f"sanitize expects a string, got {type(text).__name__}")
    out = text
    if rule.strip_controls:
        out = out.replace("\t", " ").replace("\n", " ").replace("\r", " ")
        out = "".join(c for c in out if ord(c) >= 32 and ord(c) != 127)
    if rule.collapse_whitespace:
        out = _WHITESPACE.sub(" ", out)
    if rule.lowercase:
        out = out.lower()
    if rule.max_length is not None:
        out = out[: rule.max_length]
    if rule.trim:
        out = out.strip()  # last, so a cap that ends on a space can't strand trailing whitespace
    return out
