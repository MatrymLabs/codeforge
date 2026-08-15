"""Test twin for kernel/world/exit_integrity.py -- no exit is one-way BY ACCIDENT.

Acceptance: a reciprocal pair is clean; a one-way passage DECLARED in the seed is clean and is
reported as declared, not hidden; named non-canonical entrances are ignored entirely.

Refusal (fail loud): an undeclared one-way canonical exit is ACCIDENTAL and reddens the gate, and
the report names the room, the direction and the destination so it can be acted on. A `one_way`
declaration naming a direction the room does not have is refused by the loader as stale.

The distinction this file exists to pin: the bar is NOT "every exit is reciprocal". Deliberate
one-way passage is a legitimate design. The bar is that a one-way passage is a DECISION on the
record, never an accident that strands a player.
"""

from __future__ import annotations

from kernel.world.exit_integrity import inspect_exits


def _rooms(**rooms):
    return {label: dict(spec) for label, spec in rooms.items()}


# --- acceptance ------------------------------------------------------------------------------


def test_a_reciprocal_pair_is_clean() -> None:
    verdict = inspect_exits(
        _rooms(
            a={"exits": {"north": "b"}},
            b={"exits": {"south": "a"}},
        )
    )
    assert verdict.clean
    assert verdict.accidental == ()


def test_every_canonical_direction_has_a_reverse_it_is_checked_against() -> None:
    pairs = [
        ("north", "south"),
        ("east", "west"),
        ("up", "down"),
        ("northeast", "southwest"),
        ("northwest", "southeast"),
        ("in", "out"),
    ]
    for forward, back in pairs:
        verdict = inspect_exits(_rooms(a={"exits": {forward: "b"}}, b={"exits": {back: "a"}}))
        assert verdict.clean, f"{forward}/{back} should be a reciprocal pair"


def test_a_named_entrance_is_never_checked() -> None:
    """A region hub naming its settlements is this world's real topology, not a defect."""
    verdict = inspect_exits(
        _rooms(
            veridia={"exits": {"greenhold": "greenhold"}},
            greenhold={"exits": {}},
        )
    )
    assert verdict.clean
    assert verdict.accidental == ()


def test_an_exit_to_a_room_that_does_not_exist_is_not_reported_here() -> None:
    """A dangling destination is a different complaint with a different owner."""
    verdict = inspect_exits(_rooms(a={"exits": {"north": "nowhere"}}))
    assert verdict.accidental == ()


# --- the declaration -------------------------------------------------------------------------


def test_a_declared_one_way_is_clean() -> None:
    verdict = inspect_exits(
        _rooms(
            cellar={"exits": {"west": "workshop"}, "one_way": ["west"]},
            workshop={"exits": {}},
        )
    )
    assert verdict.clean


def test_a_declared_one_way_is_still_REPORTED_as_declared() -> None:
    """Clean is not the same as invisible. The world should be able to list its one-way drops."""
    verdict = inspect_exits(
        _rooms(
            cellar={"exits": {"west": "workshop"}, "one_way": ["west"]},
            workshop={"exits": {}},
        )
    )
    assert len(verdict.declared) == 1
    assert verdict.declared[0].room == "cellar"
    assert verdict.declared[0].direction == "west"
    assert verdict.declared[0].to == "workshop"


def test_declaring_one_direction_does_not_excuse_another() -> None:
    verdict = inspect_exits(
        _rooms(
            a={"exits": {"north": "b", "east": "c"}, "one_way": ["north"]},
            b={"exits": {}},
            c={"exits": {}},
        )
    )
    assert len(verdict.accidental) == 1
    assert verdict.accidental[0].direction == "east"


# --- refusal ---------------------------------------------------------------------------------


def test_an_undeclared_one_way_is_accidental() -> None:
    verdict = inspect_exits(
        _rooms(
            cellar={"exits": {"west": "workshop"}},
            workshop={"exits": {}},
        )
    )
    assert not verdict.clean
    assert len(verdict.accidental) == 1


def test_the_report_names_room_direction_and_destination() -> None:
    """A report you cannot act on is not a report."""
    verdict = inspect_exits(
        _rooms(
            cellar={"exits": {"west": "workshop"}},
            workshop={"exits": {}},
        )
    )
    rendered = verdict.render()
    assert "cellar" in rendered and "west" in rendered and "workshop" in rendered


def test_a_reverse_pointing_at_a_DIFFERENT_room_is_still_accidental() -> None:
    """b goes south, but not back to a. The player cannot retrace their step."""
    verdict = inspect_exits(
        _rooms(
            a={"exits": {"north": "b"}},
            b={"exits": {"south": "c"}},
            c={"exits": {}},
        )
    )
    assert not verdict.clean
    assert verdict.accidental[0].room == "a"


def test_loader_refuses_a_stale_one_way_declaration(tmp_path) -> None:
    import pytest

    from kernel.world.seed import BlueprintError, load_rooms

    path = tmp_path / "rooms.yaml"
    path.write_text("cellar:\n  exits: {west: workshop}\n  one_way: [east]\nworkshop:\n")
    with pytest.raises(BlueprintError, match="cellar.*east"):
        load_rooms(path)


def test_loader_refuses_a_named_one_way_declaration(tmp_path) -> None:
    import pytest

    from kernel.world.seed import BlueprintError, load_rooms

    path = tmp_path / "rooms.yaml"
    path.write_text("hub:\n  exits: {gate: other}\n  one_way: [gate]\nother:\n")
    with pytest.raises(BlueprintError, match="canonical"):
        load_rooms(path)
