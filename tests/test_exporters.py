"""Test twin for parts/exporters.py -- the practical adapter + the one-core proof."""

import json

import pytest

from parts.exporters import CsvExporter, ExporterHub, default_hub
from parts.plugin_registry import PluginError, PluginRegistry


def test_the_default_hub_exports_json_and_csv():
    hub = default_hub()
    rows = [{"id": 1, "name": "Ada"}]
    assert json.loads(hub.export("json", rows)) == rows
    assert hub.export("csv", rows) == "id,name\n1,Ada"
    assert set(hub.formats()) == {"json", "csv"}


def test_an_unknown_format_fails_loud():
    with pytest.raises(PluginError):
        default_hub().export("xml", [])


def test_a_new_exporter_can_be_registered():
    hub = ExporterHub()
    hub.add("csv", CsvExporter())
    assert "col" in hub.export("csv", [{"col": "v"}])


def test_one_core_powers_both_the_game_heralds_and_the_practical_exporters():
    import parts.heralds as game

    hub = ExporterHub()
    assert isinstance(hub._registry, PluginRegistry)  # the exporter hub uses the core
    assert isinstance(game._REGISTRY, PluginRegistry)  # the game heralds, same core
