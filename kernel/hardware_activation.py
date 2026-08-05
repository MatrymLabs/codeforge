"""Explicit bridge from Hardware Store lifecycle state to runtime plugins.

The bridge accepts an already-constructed trusted object and a PluginRegistry. It never imports
component source, evaluates manifests, or activates anything during discovery/startup.
"""

from __future__ import annotations

from kernel.hardware_lifecycle import HardwareLifecycleError, HardwareRegistry
from kernel.shelf.plugin_registry import PluginInfo, PluginRegistry


def activate_hardware_component[T](
    hardware: HardwareRegistry,
    component_id: str,
    runtime: PluginRegistry[T],
    info: PluginInfo,
    plugin: T,
) -> None:
    """Register one approved/installed component in the runtime registry.

    Activation is a deliberate operator action. The object is supplied by trusted platform code;
    this function does not resolve ``source`` from the Hardware Card.
    """
    record = hardware.get(component_id)
    if record is None:
        raise HardwareLifecycleError(f"component {component_id!r} is not discovered")
    if record.state != "installed":
        raise HardwareLifecycleError(
            f"component {component_id!r} must be installed before runtime activation"
        )
    if info.name != component_id:
        raise HardwareLifecycleError(
            f"runtime plugin name {info.name!r} does not match {component_id!r}"
        )
    active = hardware.transition(component_id, "active")
    try:
        runtime.register(info, plugin)
    except Exception:
        hardware.transition(component_id, "installed")
        raise
    assert active.state == "active"


def disable_hardware_component[T](
    hardware: HardwareRegistry,
    component_id: str,
    runtime: PluginRegistry[T],
) -> None:
    """Disable a live plugin and retain the governed lifecycle evidence."""
    record = hardware.get(component_id)
    if record is None or record.state != "active":
        raise HardwareLifecycleError(f"component {component_id!r} is not active")
    runtime.disable(component_id)
    try:
        hardware.transition(component_id, "disabled")
    except Exception:
        runtime.enable(component_id)
        raise
