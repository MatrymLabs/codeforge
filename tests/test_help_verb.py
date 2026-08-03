"""Engine-tick test for the `help` verb (RD-2026-0007: help_index shelf-part consumer).

A verb is not wired until handle_command proves it reachable. Proves the fix: `help <command>`
answers the specific question (the old static blob ignored its argument), and multi-word/@ verbs
resolve (the help_index name-grammar rework). Lives here, not in the help_index shelf twin, so the
part stays engine-free.
"""

from __future__ import annotations

from forge import handle_command
from kernel.world.session import Session


def _p() -> Session:
    return Session(player_id="helper")


def test_help_of_a_command_answers_that_command() -> None:
    out = handle_command(_p(), "help look")
    assert "look" in out and "surroundings" in out.lower()
    # the old defect: help <x> was identical to help; now they differ
    assert out != handle_command(_p(), "help")


def test_help_resolves_a_multi_word_verb() -> None:
    # proves the name-grammar rework: "pm status" is a real multi-word verb the old snake_case
    # validation would have rejected outright.
    out = handle_command(_p(), "help pm status")
    assert "pm status" in out


def test_help_search_and_miss() -> None:
    assert "No help" in handle_command(_p(), "help zzzznope")
    # bare help lists commands (grouped) plus the intro
    assert "help <command>" in handle_command(_p(), "help")
