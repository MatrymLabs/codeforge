"""Test twin for parts/weighted_table.py -- weighted selection with an injected RNG.

Acceptance: a seeded RNG makes the draw reproducible; the distribution honours the weights.
Refusal: an empty table or a non-positive weight fails loud.
"""

from random import Random

import pytest

from parts.weighted_table import WeightedTable, WeightedTableError


def test_pick_is_reproducible_under_a_seed():
    table = WeightedTable([("sword", 1), ("gold", 4), (None, 5)])
    a = [table.pick(Random(0)) for _ in range(5)]
    b = [table.pick(Random(0)) for _ in range(5)]
    assert a == b  # same seed -> same draws (combat stays deterministic in tests)


def test_total_is_the_sum_of_weights():
    assert WeightedTable([("a", 1), ("b", 4), ("c", 5)]).total == 10


def test_the_draw_honours_the_weights():
    # over many draws, a weight-9 outcome dominates a weight-1 one (loose bound, seeded so stable)
    table = WeightedTable([("common", 9), ("rare", 1)])
    rng = Random(1234)
    picks = [table.pick(rng) for _ in range(1000)]
    assert picks.count("common") > picks.count("rare") * 3


def test_a_single_outcome_table_always_returns_it():
    table = WeightedTable([("only", 3)])
    assert table.pick(Random(7)) == "only"


def test_none_is_a_valid_outcome():
    # "nothing drops" is modelled as a None outcome with its own weight
    table = WeightedTable([(None, 1)])
    assert table.pick(Random(0)) is None


def test_an_empty_table_is_refused():
    with pytest.raises(WeightedTableError, match="at least one outcome"):
        WeightedTable([])


@pytest.mark.parametrize("bad", [0, -2, 1.5, True])
def test_a_non_positive_or_non_integer_weight_is_refused(bad):
    with pytest.raises(WeightedTableError, match="positive integer"):
        WeightedTable([("x", bad)])
