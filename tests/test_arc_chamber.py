"""Test twin for ARC slice 3: the ARC Chamber room surfaces the readiness verdict on look."""

from forge import handle_command, render_scene
from parts.seed import load_rooms
from parts.session import Session
from parts.world import WORLD, dynamic_capability


def test_the_chamber_exists_and_is_reachable_both_ways():
    assert "arc_chamber" in WORLD
    assert WORLD["diagnostic_console"]["exits"].get("up") == "arc_chamber"
    assert WORLD["arc_chamber"]["exits"].get("down") == "diagnostic_console"


def test_the_chamber_declares_the_arc_capability():
    assert dynamic_capability("arc_chamber") == "arc"
    assert dynamic_capability("courtyard") == ""  # a normal room declares none


def test_looking_in_the_chamber_shows_the_live_verdict():
    out = render_scene("arc_chamber")
    assert "The ARC Chamber" in out
    assert "VERDICT:" in out
    assert "architecture" in out  # the actual ARC panel, not just the room text


def test_a_normal_room_has_no_dynamic_panel():
    assert "VERDICT:" not in render_scene("courtyard")


def test_the_look_verb_shows_the_chamber_through_the_tick():
    out = handle_command(Session(player_id="matrym", location="arc_chamber"), "look")
    assert "The ARC Chamber" in out
    assert "VERDICT:" in out


def test_the_loader_carries_the_dynamic_field(tmp_path):
    path = tmp_path / "rooms.yaml"
    path.write_text("start:\n  exits: {}\n  dynamic: arc\nplain:\n  exits: {}\n")
    rooms = load_rooms(path)
    assert rooms["start"].get("dynamic") == "arc"
    assert "dynamic" not in rooms["plain"]  # a room without it stays clean
