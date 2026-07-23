"""CARD: heralds -- the game adapter for the plugin registry: pluggable in-world heralds.

Heralds are small plugins that each proclaim a line. The world registers a couple by explicit
registration (never by loading code), and `heralds` shows the active proclamations. A herald can be
disabled without touching the others. The SAME `PluginRegistry` core drives export providers in a
practical app (`parts/exporters`); only the plugin type differs.
"""

from __future__ import annotations

from collections.abc import Callable

from parts.shelf.plugin_registry import PluginInfo, PluginRegistry
from parts.world.session import Session

Herald = Callable[[], str]

_REGISTRY: PluginRegistry[Herald] = PluginRegistry()
_REGISTRY.register(PluginInfo("crier", "1.0"), lambda: "Hear ye! The forge is lit.")
_REGISTRY.register(PluginInfo("bard", "1.0"), lambda: "A song drifts from the courtyard.")


def heralds(session: Session, arg: str = "") -> str:
    """The `heralds` verb: every active herald's proclamation."""
    lines = [herald() for herald in _REGISTRY.active()]
    if not lines:
        return "The heralds are silent."
    return "\n".join(f"  {line}" for line in lines)


def reset_heralds() -> None:
    """Test hook: re-enable every herald."""
    for name in _REGISTRY.names():
        _REGISTRY.enable(name)
