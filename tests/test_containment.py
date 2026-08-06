from __future__ import annotations

import pytest

from kernel.containment import ContainmentError, ContainmentService


def _service() -> ContainmentService:
    service = ContainmentService()
    for entity in ("bag", "pouch", "coin"):
        service.register(entity, "alice")
    return service


def test_nested_containment_and_ancestors_are_stable():
    service = _service()
    service.move("pouch", "bag", actor_id="alice")
    service.move("coin", "pouch", actor_id="alice")
    assert service.ancestors("coin") == ("pouch", "bag")
    assert [record.entity_id for record in service.children("pouch")] == ["coin"]


def test_cycles_and_cross_owner_moves_are_rejected():
    service = _service()
    service.move("pouch", "bag", actor_id="alice")
    with pytest.raises(ContainmentError, match="cycle"):
        service.move("bag", "pouch", actor_id="alice")
    service.register("other-bag", "bob")
    with pytest.raises(ContainmentError, match="own"):
        service.move("coin", "other-bag", actor_id="alice")


def test_snapshot_restore_is_transactional_and_owner_scoped():
    service = _service()
    service.move("coin", "bag", actor_id="alice")
    snapshot = service.snapshot()
    service.move("coin", None, actor_id="alice")
    service.restore(snapshot, actor_id="alice")
    assert service.get("coin").parent_id == "bag"
    with pytest.raises(ContainmentError, match="another owner"):
        service.restore(snapshot, actor_id="bob")
