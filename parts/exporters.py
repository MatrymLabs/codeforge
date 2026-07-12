"""CARD: exporters -- the practical adapter for the plugin registry: pluggable export providers.

The reverse of parts/heralds: the SAME `PluginRegistry` core holds export providers (json, csv, ...)
keyed by name, each an object with an `export(rows) -> str` method. New formats are added by
explicit registration, validated against a required capability, never by loading code. Its cousins
are notification providers, storage backends, and any swappable integration.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from parts.plugin_registry import PluginError, PluginInfo, PluginRegistry

Row = dict[str, object]


@runtime_checkable
class Exporter(Protocol):
    """The export boundary: turn rows into a formatted string."""

    def export(self, rows: Sequence[Row]) -> str: ...


class JsonExporter:
    def export(self, rows: Sequence[Row]) -> str:
        return json.dumps(list(rows))


class CsvExporter:
    def export(self, rows: Sequence[Row]) -> str:
        if not rows:
            return ""
        header = list(rows[0].keys())
        lines = [",".join(header)]
        lines.extend(",".join(str(row.get(col, "")) for col in header) for row in rows)
        return "\n".join(lines)


class ExporterHub:
    """Register export providers and dispatch by format; every provider is serialize-capable."""

    def __init__(self) -> None:
        self._registry: PluginRegistry[Exporter] = PluginRegistry(requires=["serialize"])

    def add(self, name: str, exporter: Exporter) -> None:
        self._registry.register(PluginInfo(name, capabilities=frozenset({"serialize"})), exporter)

    def export(self, name: str, rows: Sequence[Row]) -> str:
        exporter = self._registry.get(name)
        if exporter is None:
            raise PluginError(f"no enabled exporter named {name!r}")
        return exporter.export(rows)

    def formats(self) -> list[str]:
        return self._registry.names()


def default_hub() -> ExporterHub:
    """A hub with the built-in json and csv exporters registered."""
    hub = ExporterHub()
    hub.add("json", JsonExporter())
    hub.add("csv", CsvExporter())
    return hub
