from __future__ import annotations

from types import SimpleNamespace

from adapters.gateway import _GateHandler


class _Runtime:
    def status(self) -> dict[str, object]:
        return {
            "seed": "aethryn",
            "consumer": "aethryn",
            "providers": ["event-ledger"],
            "active_bindings": [],
            "components": [],
        }


def _handler() -> _GateHandler:
    handler = object.__new__(_GateHandler)
    handler.server = SimpleNamespace(hardware_runtime=_Runtime())
    handler._gmcp_enabled = True
    handler._hardware_status_announced = False
    return handler


def test_owner_hardware_status_push_uses_the_read_only_runtime_projection():
    handler = _handler()
    sent: list[tuple[str, object]] = []
    handler._send_gmcp = lambda package, data: sent.append((package, data))

    handler._push_hardware_runtime_status()

    assert sent == [("Hardware.Status", handler.server.hardware_runtime.status())]
    assert handler._hardware_status_announced is True


def test_hardware_runtime_payload_is_available_for_other_read_only_projections():
    handler = _handler()
    assert handler._hardware_runtime_payload() == handler.server.hardware_runtime.status()
