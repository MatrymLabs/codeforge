"""CARD: plugin_registry -- extend behavior by EXPLICIT registration: no dynamic code loading.

Register named plugins with metadata (version, capabilities), validated on the way in: a duplicate
name is refused, and a plugin missing a capability the registry requires is refused. Plugins can be
enabled or disabled; a disabled plugin is never returned. Crucially, this **never imports or runs
arbitrary code** -- the caller passes an already-constructed object, so the trust boundary is
explicit. This is the safe plugin/registry pattern, reimplemented from the concept: no code copied.

Framework-free and generic over the plugin type. One core, two lives: in-world heralds in the game
(`parts/heralds`) and export providers in a practical app (`parts/exporters`).

Provenance: independently_implemented_pattern (plugin registry, explicit registration only).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field


class PluginError(ValueError):
    """A plugin was registered badly (duplicate, or missing a required capability). Fails loud."""


@dataclass(frozen=True)
class PluginInfo:
    """A plugin's metadata: its name, version, and the capabilities it advertises."""

    name: str
    version: str = "1.0"
    capabilities: frozenset[str] = field(default_factory=frozenset)


class PluginRegistry[P]:
    """A registry of explicitly-registered plugins. It never loads code; the caller supplies it."""

    def __init__(self, *, requires: Iterable[str] = ()) -> None:
        self._requires = frozenset(requires)
        self._plugins: dict[str, tuple[PluginInfo, P]] = {}
        self._disabled: set[str] = set()

    def register(self, info: PluginInfo, plugin: P) -> None:
        """Register a plugin. Refuses a duplicate name or a missing required capability."""
        if info.name in self._plugins:
            raise PluginError(f"a plugin named {info.name!r} is already registered")
        missing = self._requires - info.capabilities
        if missing:
            raise PluginError(f"plugin {info.name!r} is missing capabilities: {sorted(missing)}")
        self._plugins[info.name] = (info, plugin)

    def _require(self, name: str) -> None:
        if name not in self._plugins:
            raise PluginError(f"unknown plugin {name!r}")

    def disable(self, name: str) -> None:
        self._require(name)
        self._disabled.add(name)

    def enable(self, name: str) -> None:
        self._require(name)
        self._disabled.discard(name)

    def get(self, name: str) -> P | None:
        """The plugin for `name`, or None if it is unknown or disabled."""
        if name in self._disabled or name not in self._plugins:
            return None
        return self._plugins[name][1]

    def info(self, name: str) -> PluginInfo | None:
        entry = self._plugins.get(name)
        return entry[0] if entry else None

    def active(self) -> list[P]:
        """Every enabled plugin, in registration order."""
        return [obj for name, (_info, obj) in self._plugins.items() if name not in self._disabled]

    def names(self) -> list[str]:
        return list(self._plugins)
