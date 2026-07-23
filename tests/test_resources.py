"""Test twin for parts/world/resources.py -- ported from mk1 test_kernel."""

import pytest

from parts.world.resources import Resource


def test_valid_resource_constructs():
    hp = Resource(name="HP", current=100, maximum=142)
    assert (hp.current, hp.maximum) == (100, 142)


def test_damage_floors_at_zero():
    hp = Resource(name="HP", current=10, maximum=100)
    assert hp.damage(50).current == 0


def test_heal_caps_at_maximum():
    hp = Resource(name="HP", current=95, maximum=100)
    assert hp.heal(50).current == 100


def test_current_above_maximum_rejected():
    with pytest.raises(ValueError):
        Resource(name="HP", current=150, maximum=100)


def test_negative_amount_rejected():
    hp = Resource(name="HP", current=50, maximum=100)
    with pytest.raises(ValueError):
        hp.damage(-5)


def test_depletion_and_fullness_flags():
    hp = Resource(name="HP", current=100, maximum=100)
    assert hp.is_full and not hp.is_depleted
    assert hp.damage(100).is_depleted


def test_bool_amount_rejected():
    hp = Resource(name="HP", current=50, maximum=100)
    with pytest.raises(ValueError):
        hp.heal(True)
