"""Governed Hardware Store lifecycle: explicit, auditable, and non-executing."""

import pytest

from kernel.hardware_lifecycle import HardwareLifecycleError, HardwareRegistry


def test_component_requires_catalog_and_hardware_card(tmp_path):
    registry = HardwareRegistry(tmp_path / "hardware.json")
    record = registry.discover("validator")
    assert record.state == "discovered"
    assert record.source == "kernel/shelf/validation.py"
    assert record.license == "MIT"

    with pytest.raises(HardwareLifecycleError, match="not in catalog"):
        registry.discover("not-a-component")


def test_component_lifecycle_requires_explicit_approval_and_supports_rollback(tmp_path):
    registry = HardwareRegistry(tmp_path / "hardware.json")
    registry.discover("validator")
    with pytest.raises(HardwareLifecycleError, match="cannot move"):
        registry.transition("validator", "active")
    for state in ("validated", "approved", "installed", "active"):
        record = registry.transition("validator", state)
        assert record.state == state
    record = registry.register_consumer("validator", "creator-workshop")
    assert record.consumers == ("creator-workshop",)
    disabled = registry.transition("validator", "disabled")
    assert disabled.state == "disabled"
    restored = registry.rollback("validator")
    assert restored.state == "active"
    assert registry.get("validator").consumers == ("creator-workshop",)


def test_unactivated_component_has_no_consumer_and_registry_survives_reload(tmp_path):
    path = tmp_path / "hardware.json"
    registry = HardwareRegistry(path)
    registry.discover("validator")
    reloaded = HardwareRegistry(path)
    assert reloaded.get("validator").state == "discovered"
    with pytest.raises(HardwareLifecycleError, match="only active"):
        reloaded.register_consumer("validator", "engine")
