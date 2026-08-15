"""Test twin for kernel/world/engine.py -- the game's position contract."""

from kernel.world.engine import Engine, Engine0D, NodePosition


def test_engine_0d_places_and_recovers_a_node_position() -> None:
    engine = Engine0D()
    position = engine.place("forge")

    assert isinstance(position, NodePosition)
    assert engine.room_of(position) == "forge"


def test_engine_0d_satisfies_the_world_engine_contract() -> None:
    assert isinstance(Engine0D(), Engine)
    assert Engine0D().carry_limit() == 10
