"""Test twin for parts/world/maintenance_mode.py -- the runtime non-staff gate.

Acceptance: enable closes the gate with a reason (a blank falls back to a generic one), disable
re-opens it, is_on/reason report the state. Refusal / safety: the flag starts open, and the
`@maintenance` verb is owner-gated and toggles the gate. Distinct from the `maintenance` change-log
verb (they share a stem, not a meaning).
"""

from __future__ import annotations

from parts.world import maintenance_mode
from parts.world.jobs import bind_calling
from parts.world.session import Session


def _teardown() -> None:
    maintenance_mode.disable()  # never leak an on-gate into the next test


# --- acceptance -------------------------------------------------------------------------------
def test_the_gate_starts_open():
    _teardown()
    assert maintenance_mode.is_on() is False
    assert maintenance_mode.reason() == ""


def test_enable_closes_with_a_reason_and_disable_reopens():
    try:
        active = maintenance_mode.enable("rolling out the new dungeon")
        assert maintenance_mode.is_on() is True
        assert active == "rolling out the new dungeon" == maintenance_mode.reason()
        maintenance_mode.disable()
        assert maintenance_mode.is_on() is False and maintenance_mode.reason() == ""
    finally:
        _teardown()


def test_a_blank_reason_falls_back_to_a_generic_one():
    try:
        active = maintenance_mode.enable("   ")
        assert active == "scheduled maintenance"  # the door always has something honest to say
    finally:
        _teardown()


# --- the verb is reachable + owner-gated through the tick --------------------------------------
def _owner() -> Session:
    s = Session(player_id="root", named=True)
    s.rank = "owner"
    bind_calling(s, "vanguard")
    return s


def test_the_maintenance_verb_toggles_the_gate_for_an_owner():
    import forge

    try:
        owner = _owner()
        out = forge.handle_command(owner, "@maintenance on the forge is cooling")
        assert "Maintenance ON" in out and maintenance_mode.is_on() is True
        status = forge.handle_command(owner, "@maintenance")
        assert "ON" in status and "the forge is cooling" in status
        off = forge.handle_command(owner, "@maintenance off")
        assert "Maintenance OFF" in off and maintenance_mode.is_on() is False
    finally:
        _teardown()


def test_a_non_owner_cannot_toggle_maintenance():
    import forge

    try:
        player = Session(player_id="pleb", named=True)
        player.rank = "player"
        bind_calling(player, "vanguard")
        out = forge.handle_command(player, "@maintenance on sneaky")
        # a rank-gated ADMIN verb is not reachable by a player; the gate stays open
        assert "Maintenance ON" not in out
        assert maintenance_mode.is_on() is False
    finally:
        _teardown()
