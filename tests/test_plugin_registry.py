"""Test twin for parts/plugin_registry.py -- explicit registration, capabilities, disable."""

import pytest

from parts.plugin_registry import PluginError, PluginInfo, PluginRegistry


def test_register_and_get_a_plugin():
    reg: PluginRegistry[str] = PluginRegistry()
    reg.register(PluginInfo("greeter"), "hello")
    assert reg.get("greeter") == "hello"
    assert reg.names() == ["greeter"]


def test_a_duplicate_name_is_refused():
    reg: PluginRegistry[int] = PluginRegistry()
    reg.register(PluginInfo("a"), 1)
    with pytest.raises(PluginError):
        reg.register(PluginInfo("a"), 2)


def test_a_plugin_missing_a_required_capability_is_refused():
    reg: PluginRegistry[str] = PluginRegistry(requires=["serialize"])
    with pytest.raises(PluginError):
        reg.register(PluginInfo("x", capabilities=frozenset()), "nope")
    reg.register(PluginInfo("y", capabilities=frozenset({"serialize"})), "ok")  # has it
    assert reg.get("y") == "ok"


def test_a_disabled_plugin_is_not_returned():
    reg: PluginRegistry[str] = PluginRegistry()
    reg.register(PluginInfo("a"), "one")
    reg.register(PluginInfo("b"), "two")
    reg.disable("a")
    assert reg.get("a") is None
    assert reg.active() == ["two"]
    reg.enable("a")
    assert reg.get("a") == "one"


def test_unknown_plugin_operations_fail_loud():
    reg: PluginRegistry[str] = PluginRegistry()
    with pytest.raises(PluginError):
        reg.disable("ghost")
    assert reg.get("ghost") is None  # get is lenient (None), mutations are loud


def test_info_carries_version_and_capabilities():
    reg: PluginRegistry[str] = PluginRegistry()
    reg.register(PluginInfo("a", "2.1", frozenset({"x"})), "ok")
    info = reg.info("a")
    assert info is not None and info.version == "2.1" and "x" in info.capabilities
