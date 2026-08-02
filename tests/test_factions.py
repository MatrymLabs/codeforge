"""Test twin for kernel/world/factions.py -- the standing between the Orders (faction conflicts).

Acceptance: two Orders stand self/allied/rival/neutral, symmetrically; each Order reports its allies
and rivals; the politics render for a sworn hero. Composes with the real Orders, never a second set.
"""

from __future__ import annotations

from kernel.world.factions import relations_of, render_factions, stance
from kernel.world.orders import ORDERS


def test_stance_is_self_allied_rival_or_neutral_and_symmetric():
    assert stance("making", "making") == "self"
    assert stance("making", "gathering") == "allied"
    assert stance("making", "knowing") == "rival"
    assert stance("gathering", "knowing") == "neutral"
    # symmetric
    for a in ORDERS:
        for b in ORDERS:
            assert stance(a, b) == stance(b, a)


def test_an_unknown_order_is_neutral_to_all():
    assert stance("no_such_order", "making") == "neutral"
    assert relations_of("no_such_order") == ([], [])


def test_relations_split_into_allies_and_rivals_without_self():
    allies, rivals = relations_of("warcraft")
    assert "knowing" in allies and "gathering" in rivals
    assert "warcraft" not in allies and "warcraft" not in rivals


def test_every_order_has_a_consistent_web():
    # a's ally lists a back; a rival lists a back -- the model is coherent across all Orders
    for a in ORDERS:
        allies, rivals = relations_of(a)
        for ally in allies:
            assert a in relations_of(ally)[0]
        for rival in rivals:
            assert a in relations_of(rival)[1]


def test_render_shows_the_politics_and_marks_the_readers_order():
    out = render_factions(sworn="making")
    assert "The politics of the Row:" in out
    assert all(ORDERS[label]["name"] in out for label in ORDERS)
    assert "(yours)" in out, "the sworn reader's own Order is marked"
