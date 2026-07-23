"""Test twin for parts/world/doors.py -- locks, keys, and gated movement."""

import copy

import pytest

from parts.world import doors, items
from parts.world.doors import barred_door_for, unlock
from parts.world.items import take
from parts.world.world import resolve_move


@pytest.fixture(autouse=True)
def fresh_world():
    """Snapshot ITEMS and DOORS before each test, restore after."""
    items_snap = copy.deepcopy(items.ITEMS)
    doors_snap = copy.deepcopy(doors.DOORS)
    yield
    items.ITEMS.clear()
    items.ITEMS.update(items_snap)
    doors.DOORS.clear()
    doors.DOORS.update(doors_snap)


@pytest.fixture(autouse=True)
def fresh_sands():
    """The shared world timer is a global the beat drains every command -- reset it around each
    door test so a scheduled reclose never leaks into another test's beat."""
    from parts.shelf.hourglass import WORLD_SANDS

    WORLD_SANDS.clear()
    yield
    WORLD_SANDS.clear()


# --- self-closing doors (the Hourglass consumer) --------------------------------------
def test_reclose_relocks_an_open_self_closing_door():
    doors.DOORS["oak_door"]["locked"] = False
    doors.DOORS["oak_door"]["recloses_after"] = 3
    assert doors.reclose("oak_door") == ("library", "the oak door")
    assert doors.DOORS["oak_door"]["locked"] is True


def test_reclose_is_idempotent_on_a_shut_or_unknown_door():
    assert doors.reclose("oak_door") is None  # already locked (its seed default)
    assert doors.reclose("no_such_door") is None


def test_unlocking_a_self_closing_door_arms_the_world_timer():
    from parts.shelf.hourglass import WORLD_SANDS

    doors.DOORS["oak_door"]["recloses_after"] = 5
    take("key", "library")
    unlock("door", "key", "library")
    assert doors.DOORS["oak_door"]["locked"] is False
    assert WORLD_SANDS.remaining("reclose:oak_door") == 5  # armed, counting down


def test_a_plain_door_does_not_arm_the_world_timer():
    from parts.shelf.hourglass import WORLD_SANDS

    take("key", "library")
    unlock("door", "key", "library")  # oak_door ships no recloses_after -> stays open
    assert WORLD_SANDS.pending() == 0


def test_a_cloned_key_opens_the_door_by_prototype():
    # instancing: a door keyed to `copper_key` opens for ANY instance of it -- here a cloned key
    # carried in the pack, not the seed singleton. The match is by prototype, not id.
    items.clone("copper_key", "player")  # a fresh copper_key instance, straight into the pack
    result = unlock("door", "key", "library")
    assert "unlock" in result
    assert doors.DOORS["oak_door"]["locked"] is False


def test_a_self_closing_door_slams_shut_on_a_later_world_beat():
    from forge import handle_command
    from parts.world.session import Session

    doors.DOORS["oak_door"]["recloses_after"] = 2
    take("key", "library")
    session = Session(player_id="tester", location="library")
    handle_command(session, "unlock door with key")  # arms after=2; this beat -> remaining 1
    assert doors.DOORS["oak_door"]["locked"] is False
    out = handle_command(session, "look")  # next beat -> fires -> relock
    assert doors.DOORS["oak_door"]["locked"] is True
    assert "slams shut" in out  # the player, standing in the room, sees it


def test_oak_door_starts_locked():
    assert barred_door_for("library", "north") == "oak_door"


def test_locked_door_blocks_movement():
    arrived, message = resolve_move("library", "north")
    assert arrived == "library"
    assert "locked" in message


def test_unlock_fails_without_key():
    result = unlock("door", "key", "library")
    assert result == "You aren't carrying that."
    assert doors.DOORS["oak_door"]["locked"] is True


def test_unlock_with_carried_key_succeeds():
    take("key", "library")
    result = unlock("door", "key", "library")
    assert "unlock" in result
    assert doors.DOORS["oak_door"]["locked"] is False


def test_unlocked_door_allows_movement():
    take("key", "library")
    unlock("door", "key", "library")
    arrived, _ = resolve_move("library", "north")
    assert arrived == "archive"


def test_open_gate_opens_a_locked_door_without_a_key():
    """A quest reforging a bridge opens a barrier by engine decree, carrying no key."""
    assert doors.DOORS["oak_door"]["locked"] is True
    assert doors.open_gate("oak_door") is True
    assert doors.DOORS["oak_door"]["locked"] is False
    arrived, _ = resolve_move("library", "north")  # the gate is open now
    assert arrived == "archive"


def test_open_gate_is_a_no_op_on_unknown_or_already_open_doors():
    assert doors.open_gate("no_such_door") is False  # unknown
    doors.open_gate("oak_door")
    assert doors.open_gate("oak_door") is False  # already open -> nothing to do


def test_a_wrong_key_reports_it_does_not_fit_with_the_key_named():
    """The guard's refusal starts a sentence with the carried key's authored name, sentence-cased
    (not str.capitalize(), which would lower-case a proper-noun key)."""
    take("key", "library")  # carries the copper key
    doors.DOORS["oak_door"]["key_id"] = "some_other_key"  # fixture restores after
    result = unlock("door", "key", "library")
    assert result == "A copper key doesn't fit the lock."


def test_unlocking_an_already_open_door_says_so_with_the_door_named():
    take("key", "library")
    unlock("door", "key", "library")  # now open
    result = unlock("door", "key", "library")  # unlock again
    assert result == "The oak door is already unlocked."


# --- requires: a safe condition gating the unlock (parts.shelf.conditions) -----------------------


def test_a_gated_door_bars_an_actor_who_fails_the_requirement():
    doors.DOORS["oak_door"]["requires"] = "rank == 'wizard'"
    items.clone("copper_key", "player")  # carries the right key...
    result = unlock("door", "key", "library", {"level": 1, "rank": "player"})
    assert "warded" in result  # ...but the ward bars a non-wizard
    assert doors.DOORS["oak_door"]["locked"] is True  # stayed locked despite the key


def test_a_gated_door_opens_for_an_actor_who_meets_the_requirement():
    doors.DOORS["oak_door"]["requires"] = "rank == 'wizard' and level >= 5"
    items.clone("copper_key", "player")
    result = unlock("door", "key", "library", {"level": 10, "rank": "wizard"})
    assert "unlock" in result and doors.DOORS["oak_door"]["locked"] is False


def test_a_gated_door_with_no_actor_context_stays_barred():
    doors.DOORS["oak_door"]["requires"] = "level >= 5"
    items.clone("copper_key", "player")
    result = unlock("door", "key", "library")  # no actor -> unknown name -> unmet, never opens
    assert "warded" in result and doors.DOORS["oak_door"]["locked"] is True


def test_load_doors_rejects_an_unsafe_requires_condition(tmp_path):
    from parts.world.seed import SeedError, load_doors

    (tmp_path / "doors.yaml").write_text(
        "trap_door:\n"
        "  name: the trap door\n"
        "  keywords: [door]\n"
        "  blocks: [library, north]\n"
        "  locked: true\n"
        "  key_id: copper_key\n"
        "  requires: \"__import__('os')\"\n"  # a forbidden construct
    )
    with pytest.raises(SeedError, match="invalid 'requires' condition"):
        load_doors(tmp_path / "doors.yaml")
