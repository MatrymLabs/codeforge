"""Test twin for parts/payload_check.py -- the practical adapter + the one-core proof."""

from parts.payload_check import validate_signup
from parts.shelf.validation import Validator


def test_a_valid_signup_passes():
    result = validate_signup({"username": "ada_l", "email": "ada@example.com", "age": 30})
    assert result.is_valid


def test_a_bad_signup_reports_every_problem_at_once():
    result = validate_signup({"username": "AB", "email": "not-an-email", "age": 5})
    fields = {i.field for i in result.issues}
    assert fields == {"username", "email", "age"}


def test_a_missing_required_field_is_caught():
    result = validate_signup({"email": "ada@example.com", "age": 30})
    assert "username: is required" in result.errors


def test_one_core_powers_both_the_game_name_check_and_the_practical_payload_check():
    import parts.name_check as game
    import parts.payload_check as practical

    assert isinstance(game._VALIDATOR, Validator)
    assert isinstance(practical.SIGNUP, Validator)
