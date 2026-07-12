"""CARD: field_sanitizer -- the practical adapter for the sanitizer: clean fields for storage/logs.

The reverse of parts/titles: the SAME `sanitize` core cleans business input before it is stored or
logged. `clean_field` normalizes a single-line value (bounded, no control chars) and `clean_record`
sanitizes each string in a record. This keeps control characters and log-injection newlines out of
logs and records; it is normalization, not a substitute for escaping or parameterized queries.
"""

from __future__ import annotations

from collections.abc import Mapping

from parts.sanitizer import SanitizeRule, sanitize

_FIELD_RULE = SanitizeRule(max_length=200)


def clean_field(value: str, max_length: int = 200) -> str:
    """Normalize one field: strip controls, collapse whitespace, trim, cap. Idempotent."""
    return sanitize(value, SanitizeRule(max_length=max_length))


def clean_record(record: Mapping[str, object]) -> dict[str, object]:
    """Return a copy of `record` with every string value sanitized; non-strings pass through."""
    return {
        key: sanitize(value, _FIELD_RULE) if isinstance(value, str) else value
        for key, value in record.items()
    }
