"""CARD: features -- the game adapter for feature flags: an in-world feature panel.

The world registers a few flags (beta content, verbose combat, a cheat/debug mode). `features` shows
their state; `feature_on(name)` lets other game code gate behavior on a flag. Flags default off, so
nothing beta ships on by an accident. The SAME `FlagRegistry` core drives an environment kill switch
in a practical app (`parts/feature_control`); only the adapter differs.
"""

from __future__ import annotations

from parts.shelf.feature_flags import FlagRegistry
from parts.world.session import Session

_REGISTRY = FlagRegistry()
_REGISTRY.register("beta_quests", default=False, description="show experimental quests")
_REGISTRY.register("verbose_combat", default=False, description="extra combat detail lines")
_REGISTRY.register("debug_mode", default=False, description="developer diagnostics in-world")


def feature_on(name: str) -> bool:
    """Whether a world feature flag is on (other game code gates on this)."""
    return _REGISTRY.is_on(name)


def features(session: Session, arg: str = "") -> str:
    """The `features` verb: a panel of the world's feature flags and their state."""
    lines = ["World feature flags:"]
    for flag in _REGISTRY.all():
        mark = "on " if _REGISTRY.is_on(flag.name) else "off"
        lines.append(f"  [{mark}] {flag.name}  -- {flag.description}")
    return "\n".join(lines)


def reset_features() -> None:
    """Test hook: drop all overrides, back to registered defaults."""
    for flag in _REGISTRY.all():
        _REGISTRY.reset(flag.name)
