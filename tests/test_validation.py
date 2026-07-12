"""Test twin for parts/validation.py -- composable rules that collect every issue at once."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from parts.validation import (
    ValidationFailed,
    Validator,
    in_range,
    matches,
    max_length,
    of_type,
    one_of,
    required,
)

_V = Validator(
    required("name"),
    matches("name", r"[a-z]+", "must be lowercase letters"),
    of_type("age", int),
    in_range("age", 0, 120),
    one_of("role", ["admin", "user"]),
    max_length("bio", 10),
)


def test_a_fully_valid_payload_passes():
    result = _V.check({"name": "ada", "age": 30, "role": "user", "bio": "short"})
    assert result.is_valid
    assert result.errors == ()


def test_a_missing_required_field_is_reported():
    result = _V.check({"age": 30, "role": "user"})
    assert not result.is_valid
    assert "name: is required" in result.errors


def test_every_issue_is_collected_at_once():
    result = _V.check({"name": "Ada!", "age": 200, "role": "root", "bio": "way too long a bio"})
    fields = {i.field for i in result.issues}
    assert fields == {"name", "age", "role", "bio"}  # all four, in one pass


def test_a_required_and_empty_field_reports_once_not_twice():
    result = _V.check({"name": "", "age": 30, "role": "user"})
    name_issues = [i for i in result.issues if i.field == "name"]
    assert len(name_issues) == 1  # 'required' fires; the pattern rule skips the empty value


def test_wrong_type_and_out_of_range_are_distinct_rules():
    assert "age: must be a int" in Validator(of_type("age", int)).check({"age": "x"}).errors
    assert (
        "age: must be between 0 and 120"
        in Validator(in_range("age", 0, 120)).check({"age": -1}).errors
    )


def test_raise_if_invalid_raises_with_the_messages_or_stays_quiet():
    _V.check({"name": "ada", "age": 30, "role": "user"}).raise_if_invalid()  # no raise
    with pytest.raises(ValidationFailed) as exc:
        _V.check({"role": "nope"}).raise_if_invalid()
    assert exc.value.result.issues  # the result is carried on the exception


def test_results_merge():
    a = Validator(required("x")).check({})
    b = Validator(required("y")).check({})
    merged = a.merge(b)
    assert {i.field for i in merged.issues} == {"x", "y"}


@pytest.mark.property
@given(
    name=st.text(alphabet="abcdefghijklmnop", min_size=1, max_size=8),
    age=st.integers(min_value=0, max_value=120),
)
def test_a_value_satisfying_all_rules_is_valid_and_issues_never_exceed_rules(name, age):
    result = _V.check({"name": name, "age": age, "role": "user", "bio": "ok"})
    assert result.is_valid
    assert len(result.issues) <= 6  # never more issues than rules
