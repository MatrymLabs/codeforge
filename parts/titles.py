"""CARD: titles -- the game adapter for the sanitizer: set a clean player title.

`title <text>` sets a personal title, sanitized first: control characters dropped, whitespace
folded, and capped, so no one can smuggle escape codes or a wall of text into a title.
The SAME `sanitize` core cleans a stored field in a practical app (`parts/field_sanitizer`); only
the adapter and the rule differ.
"""

from __future__ import annotations

from parts.shelf.sanitizer import SanitizeRule, sanitize
from parts.world.session import Session

_RULE = SanitizeRule(max_length=24)
_TITLES: dict[str, str] = {}


def title(session: Session, arg: str = "") -> str:
    """The `title` verb: show your title, or set a sanitized new one."""
    if not arg.strip():
        current = _TITLES.get(session.player_id)
        return f"Your title: {current}" if current else "You have no title. Set one: title <text>"
    clean = sanitize(arg, _RULE)
    if not clean:
        return "That title is empty once cleaned. Pick something with visible characters."
    _TITLES[session.player_id] = clean
    return f"Your title is now: {clean}"


def reset_titles() -> None:
    """Test hook: clear every player's title."""
    _TITLES.clear()
