"""Test twin for kernel.world.gearsets: set bonuses when a whole gear set is worn.

Acceptance (a full set grants its bonus; two sets stack) AND refusal (a partial set earns nothing;
an empty registry earns nothing). Pure: the tests inject their own sets, never the loaded registry.
"""

from kernel.world.gearsets import active_set_bonuses
from kernel.world.seed import GearSet

_SETS: dict[str, GearSet] = {
    "storm": GearSet(
        name="Storm", pieces=["helm", "cuirass", "greaves"], bonus={"DEF": 8, "EVA": 5}
    ),
    "ember": GearSet(name="Ember", pieces=["hood", "vest"], bonus={"EVA": 3}),
}


def test_a_full_set_grants_its_bonus():
    worn = {"helm", "cuirass", "greaves"}
    assert active_set_bonuses(worn, _SETS) == {"DEF": 8, "EVA": 5}


def test_a_partial_set_earns_nothing():
    """Two of three pieces is not a set: the bonus is all-or-nothing, so a set is worth earning."""
    assert active_set_bonuses({"helm", "cuirass"}, _SETS) == {}


def test_two_complete_sets_stack_per_stat():
    worn = {"helm", "cuirass", "greaves", "hood", "vest"}  # both sets complete
    assert active_set_bonuses(worn, _SETS) == {"DEF": 8, "EVA": 8}  # 5 + 3 on EVA


def test_extra_pieces_do_not_break_a_completed_set():
    worn = {"helm", "cuirass", "greaves", "unrelated_trinket"}
    assert active_set_bonuses(worn, _SETS) == {"DEF": 8, "EVA": 5}


def test_no_sets_means_no_bonus():
    assert active_set_bonuses({"helm", "cuirass", "greaves"}, {}) == {}
