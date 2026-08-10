"""Test twin for target_disambig: acceptance + hostile refusal cases."""

from __future__ import annotations

import pytest

from kernel.shelf.target_disambig import TargetError, parse_target, pick, resolve

# --- acceptance -----------------------------------------------------------


def test_parse_leading_ordinal() -> None:
    assert parse_target("2-sword") == (2, "sword")


def test_parse_trailing_ordinal() -> None:
    assert parse_target("sword-2") == (2, "sword")


def test_parse_bare_name_defaults_to_one() -> None:
    assert parse_target("sword") == (1, "sword")


def test_parse_strips_surrounding_whitespace() -> None:
    assert parse_target("  3-sword  ") == (3, "sword")


def test_parse_hyphenated_name_without_ordinal() -> None:
    # A name that merely contains a hyphen is not an ordinal.
    assert parse_target("great-sword") == (1, "great-sword")


def test_parse_large_ordinal() -> None:
    assert parse_target("12-orc") == (12, "orc")


def test_pick_returns_right_element() -> None:
    matches = ["a", "b", "c"]
    assert pick(matches, 2) == "b"


def test_pick_first_element() -> None:
    assert pick(["only"], 1) == "only"


def test_resolve_end_to_end_leading() -> None:
    swords = ["rusty", "shiny", "bent"]
    assert resolve("2-sword", swords) == "shiny"


def test_resolve_end_to_end_trailing() -> None:
    swords = ["rusty", "shiny", "bent"]
    assert resolve("sword-3", swords) == "bent"


def test_resolve_bare_picks_first() -> None:
    swords = ["rusty", "shiny"]
    assert resolve("sword", swords) == "rusty"


# --- refusal (hostile / near-miss) ---------------------------------------


def test_parse_zero_ordinal_fails_loud() -> None:
    with pytest.raises(TargetError):
        parse_target("0-sword")


def test_parse_empty_token_fails_loud() -> None:
    with pytest.raises(TargetError):
        parse_target("")


def test_parse_blank_token_fails_loud() -> None:
    with pytest.raises(TargetError):
        parse_target("   ")


def test_pick_ordinal_zero_fails_loud() -> None:
    with pytest.raises(TargetError):
        pick(["a", "b"], 0)


def test_pick_negative_ordinal_fails_loud() -> None:
    with pytest.raises(TargetError):
        pick(["a", "b"], -1)


def test_pick_beyond_matches_names_count() -> None:
    with pytest.raises(TargetError) as excinfo:
        pick(["a", "b"], 3)
    assert "only 2 here" in str(excinfo.value)


def test_resolve_beyond_matches_fails_loud() -> None:
    with pytest.raises(TargetError):
        resolve("5-sword", ["one", "two"])


def test_resolve_zero_ordinal_fails_loud() -> None:
    with pytest.raises(TargetError):
        resolve("0-sword", ["one", "two"])
