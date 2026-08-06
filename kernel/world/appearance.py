"""Character presentation choices: small, explicit, and persisted as player-owned data."""

from __future__ import annotations

SKIN_COLORS = ("porcelain", "fair", "golden", "copper", "umber", "deep")
DEFAULT_APPEARANCE = {"skin_color": ""}


def normalize_skin_color(value: str) -> str | None:
    """Return a canonical palette value, or None for an invalid choice."""
    candidate = value.strip().lower().replace("-", "_")
    return candidate if candidate in SKIN_COLORS else None


def serialize(appearance: dict[str, str]) -> str:
    import json

    skin = normalize_skin_color(appearance.get("skin_color", "")) or ""
    return json.dumps({"skin_color": skin}, sort_keys=True) if skin else ""


def deserialize(raw: str) -> dict[str, str]:
    import json

    if not raw:
        return dict(DEFAULT_APPEARANCE)
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return dict(DEFAULT_APPEARANCE)
    if not isinstance(value, dict):
        return dict(DEFAULT_APPEARANCE)
    skin = normalize_skin_color(str(value.get("skin_color", ""))) or ""
    return {"skin_color": skin}

