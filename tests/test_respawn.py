"""Test twin for kernel/world/respawn.py -- the respawn-policy catalog and dynamic-spawn primitive.

Acceptance: pick_room draws a site from a pool (uniform or weighted), seedably and safely on an
empty pool. Governance: the catalog is well-formed and every policy still points at a real behavior,
so no respawn policy drifts loose from the code that implements it.
"""

from __future__ import annotations

import importlib
import random

import pytest

from kernel.world.respawn import CATALOG, pick_room, policy, render_policies


def test_pick_room_draws_a_candidate_seedably():
    rooms = ["a", "b", "c", "d"]
    r1 = random.Random(7)
    r2 = random.Random(7)
    draws1 = [pick_room(rooms, rng=r1) for _ in range(20)]
    draws2 = [pick_room(rooms, rng=r2) for _ in range(20)]
    assert draws1 == draws2, "same seed, same sites"
    assert set(draws1) <= set(rooms)


def test_weights_bias_the_draw():
    rng = random.Random(1)
    # room 'b' is overwhelmingly weighted; over many draws it should dominate
    draws = [pick_room(["a", "b"], weights=[1, 99], rng=rng) for _ in range(200)]
    assert draws.count("b") > draws.count("a") * 5


def test_an_empty_pool_spawns_nothing_not_a_crash():
    assert pick_room([]) == ""


def test_mismatched_weights_fail_loud():
    with pytest.raises(ValueError):
        pick_room(["a", "b"], weights=[1])


def test_the_catalog_is_well_formed():
    keys = [p.key for p in CATALOG]
    assert len(keys) == len(set(keys)), "policy keys are unique"
    for p in CATALOG:
        assert p.what and p.trigger and p.cadence and p.reason, f"{p.key} missing a field"
        assert policy(p.key) is p
    text = render_policies()
    assert all(p.key in text for p in CATALOG)


def test_every_policy_points_at_a_real_behavior():
    # the governance gate: a policy must name a callable that still exists, so the philosophy
    # can never drift loose from the code that implements it.
    for p in CATALOG:
        module_name, attr = p.lives_in
        module = importlib.import_module(module_name)
        assert hasattr(module, attr), f"policy {p.key} points at missing {module_name}.{attr}"
