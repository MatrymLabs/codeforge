"""Test twin for parts/sanitizer.py -- deterministic, idempotent input normalization."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from parts.sanitizer import DEFAULT, SanitizeError, SanitizeRule, sanitize


def test_it_strips_control_characters():
    assert sanitize("he\x00l\x07lo") == "hello"


def test_it_folds_whitespace_and_trims():
    assert sanitize("  a\t\tb\n c  ") == "a b c"


def test_it_can_lowercase_and_cap_length():
    rule = SanitizeRule(lowercase=True, max_length=5)
    assert sanitize("HELLO WORLD", rule) == "hello"


def test_a_cap_that_lands_on_a_space_does_not_strand_whitespace():
    rule = SanitizeRule(max_length=2)
    assert sanitize("a b c", rule) == "a"  # capped to "a " then trimmed


def test_a_bad_max_length_fails_loud():
    with pytest.raises(SanitizeError):
        SanitizeRule(max_length=-1)


def test_a_non_string_fails_loud():
    bad: object = 123
    with pytest.raises(SanitizeError):
        sanitize(bad)


@pytest.mark.property
@given(text=st.text(max_size=100), cap=st.integers(min_value=0, max_value=50))
def test_sanitize_is_idempotent_and_bounded(text, cap):
    rule = SanitizeRule(max_length=cap)
    once = sanitize(text, rule)
    assert sanitize(once, rule) == once  # idempotent
    assert len(once) <= cap  # bounded
    assert all(ord(c) >= 32 and ord(c) != 127 for c in once)  # no control chars
    assert once == once.strip()  # trimmed


@pytest.mark.property
@given(text=st.text(max_size=100))
def test_the_default_rule_is_also_idempotent(text):
    once = sanitize(text, DEFAULT)
    assert sanitize(once, DEFAULT) == once
