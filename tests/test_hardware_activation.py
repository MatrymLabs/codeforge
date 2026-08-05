from kernel.hardware_activation import activate_hardware_component, disable_hardware_component
from kernel.hardware_lifecycle import HardwareRegistry
from kernel.shelf.plugin_registry import PluginInfo, PluginRegistry


def _installed(registry: HardwareRegistry) -> None:
    registry.discover("validator")
    for state in ("validated", "approved", "installed"):
        registry.transition("validator", state)


def test_explicit_activation_registers_the_trusted_object(tmp_path):
    hardware = HardwareRegistry(tmp_path / "hardware.json")
    _installed(hardware)
    runtime: PluginRegistry[object] = PluginRegistry()
    plugin = object()
    activate_hardware_component(
        hardware, "validator", runtime, PluginInfo("validator", capabilities=frozenset()), plugin
    )
    assert hardware.get("validator").state == "active"
    assert runtime.get("validator") is plugin


def test_discovery_and_install_never_activate_a_runtime_plugin(tmp_path):
    hardware = HardwareRegistry(tmp_path / "hardware.json")
    _installed(hardware)
    runtime: PluginRegistry[object] = PluginRegistry()
    # Reaching the installed state is not activation; no object is registered implicitly.
    assert hardware.get("validator").state == "installed"
    assert runtime.names() == []


def test_disable_disconnects_runtime_plugin_and_updates_governed_state(tmp_path):
    hardware = HardwareRegistry(tmp_path / "hardware.json")
    _installed(hardware)
    runtime: PluginRegistry[object] = PluginRegistry()
    activate_hardware_component(hardware, "validator", runtime, PluginInfo("validator"), object())
    disable_hardware_component(hardware, "validator", runtime)
    assert hardware.get("validator").state == "disabled"
    assert runtime.get("validator") is None
