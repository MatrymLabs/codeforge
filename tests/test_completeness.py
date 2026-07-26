"""Test twin for parts.shelf.completeness: the category-coverage / gap-report instrument.

Acceptance (a complete collection reports no gaps; a partial one names exactly what is missing;
extras are surfaced, not hidden) AND refusal (an empty requirement fails loud, not a vacuous pass).
"""

import pytest

from parts.shelf.completeness import Coverage, CoverageError, coverage


def test_a_collection_that_covers_every_required_category_is_complete():
    result = coverage(["head", "body", "arm"], required=["head", "body", "arm"])
    assert result.complete
    assert result.covered == frozenset({"head", "body", "arm"})
    assert result.missing == frozenset()
    assert result.extra == frozenset()


def test_a_gap_is_named_exactly_not_just_flagged():
    """The point is an HONEST gap list: not 'incomplete' but 'missing the arm slot'."""
    result = coverage(["head", "body"], required=["head", "body", "arm"])
    assert not result.complete
    assert result.missing == frozenset({"arm"})
    assert result.covered == frozenset({"head", "body"})


def test_extras_are_surfaced_but_do_not_block_completeness():
    """A category present but not required is reported as `extra`, and never counts as a gap: a
    Reach that drops an accessory on top of a full armor set is still armor-complete."""
    result = coverage(["head", "body", "arm", "accessory_1"], required=["head", "body", "arm"])
    assert result.complete  # the extra does not break completeness
    assert result.extra == frozenset({"accessory_1"})
    assert "accessory_1" not in result.covered  # covered is only the required ones present


def test_duplicates_in_the_present_set_collapse():
    """Two head pieces still cover the head slot once: presence, not count (order-insensitive)."""
    result = coverage(["head", "head", "body"], required=["head", "body"])
    assert result.complete and result.covered == frozenset({"head", "body"})


def test_an_empty_requirement_is_refused():
    """Completeness against nothing required would be a meaningless pass -- fail loud instead."""
    with pytest.raises(CoverageError, match="at least one required"):
        coverage(["head", "body"], required=[])


def test_the_verdict_is_immutable():
    result = coverage(["a"], required=["a"])
    assert isinstance(result, Coverage)
    with pytest.raises(AttributeError):
        result.covered = frozenset()  # frozen dataclass: assignment raises at runtime
