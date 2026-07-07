"""Test twin for parts/world.py -- graph integrity and movement."""

from parts.world import DIRECTIONS, WORLD, try_move


def test_all_exits_lead_to_real_rooms():
    """No dangling edges: every exit must point to a room that exists."""
    for room_id, room in WORLD.items():
        for direction, destination in room["exits"].items():
            assert destination in WORLD, (
                f"Room '{room_id}' has exit '{direction}' -> '{destination}', which does not exist!"
            )


def test_direction_aliases_resolve_to_canonical_forms():
    assert DIRECTIONS["n"] == "north"
    assert DIRECTIONS["north"] == "north"
    assert DIRECTIONS["d"] == "down"


def test_move_through_valid_exit_changes_location():
    arrived, message = try_move("forge", "north")
    assert arrived == "courtyard"
    assert message == ""


def test_move_through_missing_exit_stays_put():
    arrived, message = try_move("forge", "east")
    assert arrived == "forge"
    assert "can't go" in message
