"""Test twin for kernel/world/gather.py -- harvest crafting materials from the wilds.

Acceptance: a room with a node yields its material to `gather`, then the node renews after a
cooldown; a room without a node (and an unknown material) fail cleanly. Integration: the wildlands
generator seeds nodes yielding REAL crafting inputs, and a look shows the node.
"""

from __future__ import annotations

import pytest

import forge
from kernel.world import gather, items
from kernel.world.session import SESSIONS, Session
from kernel.world.world import WORLD


@pytest.fixture(autouse=True)
def fresh():
    SESSIONS.clear()
    # a probe room with a node, cleaned up so the shared world is untouched
    WORLD["probe_node_room"] = {
        "name": "Ore Seam",
        "desc": "a vein of ember",
        "exits": {},
        "node": "forge_wrench",
    }
    yield
    WORLD.pop("probe_node_room", None)
    for iid in [i for i in items.ITEMS if items.is_clone(i)]:
        del items.ITEMS[iid]
    SESSIONS.clear()


def _forager(location: str = "probe_node_room") -> Session:
    s = Session(player_id="forager", location=location)
    SESSIONS["forager"] = s
    return s


def test_gathering_mints_the_nodes_material_into_your_hands():
    s = _forager()
    out = forge.handle_command(s, "gather")
    assert "gather" in out.lower()
    assert any(
        items.prototype_of(i) == "forge_wrench" for i in items.items_in(items.carrier("forager"))
    )


def test_a_worked_node_is_spent_then_renews_after_the_cooldown():
    s = _forager()
    forge.handle_command(s, "gather")
    assert "worked this node bare" in forge.handle_command(s, "gather")  # on cooldown
    for _ in range(gather.GATHER_COOLDOWN):  # the world beat renews it
        forge.handle_command(s, "look")
    assert "gather" in forge.handle_command(s, "gather").lower()  # ready again


def test_a_room_with_no_node_has_nothing_to_gather():
    s = _forager(location="probe_node_room")
    del WORLD["probe_node_room"]["node"]
    assert "nothing to gather" in forge.handle_command(s, "gather")


def test_a_node_shows_on_look():
    assert "gather" in gather.gather_hint("probe_node_room").lower()
    WORLD["probe_node_room"]["node"] = "no_such_material"  # unknown material: no hint, no crash
    assert gather.gather_hint("probe_node_room") == ""


def test_the_wildlands_seed_nodes_that_feed_real_recipes():
    from pathlib import Path

    from kernel.world.seed import load_recipes
    from kernel.world.wildlands import _gather_node

    # every material the generator seeds must be a real crafting input, or the loop is dead.
    seeded = {_gather_node("wild-forest", i) for i in range(30)} | {
        _gather_node("volcanic-flats", i) for i in range(30)
    }
    seeded.discard(None)
    assert seeded  # some rooms carry a node
    recipes = load_recipes(
        Path(__file__).resolve().parent.parent / "seeds" / "aethryn" / "recipes.yaml"
    )
    inputs = {proto for r in recipes.values() for proto in r["inputs"]}
    assert seeded <= inputs, f"a gathered material feeds no recipe: {seeded - inputs}"
