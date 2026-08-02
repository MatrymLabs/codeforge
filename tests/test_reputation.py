"""Test twin for kernel/world/reputation.py -- a hero's standing with each Order (roadmap #2).

Acceptance: standing bands into named tiers; `grant` raises/lowers it and spills over the faction
politics (allies shift the same way, rivals the opposite); swearing an Order earns a starting
standing; the sheet and the tick show it; standing persists across a save. Refusal: an unknown Order
is a clean no-op, and a malformed saved pair is dropped, never a crash.
"""

from __future__ import annotations

import forge
from kernel.world import reputation
from kernel.world.factions import relations_of
from kernel.world.session import Session


def _hero(order: str = "") -> Session:
    s = Session(player_id="rep", location="void")
    s.order = order
    return s


def test_tiers_band_the_standing_value():
    assert reputation.tier_for(-500) == "Hostile"
    assert reputation.tier_for(-100) == "Unfriendly"
    assert reputation.tier_for(0) == "Neutral"
    assert reputation.tier_for(100) == "Friendly"
    assert reputation.tier_for(300) == "Honored"
    assert reputation.tier_for(600) == "Revered"


def test_standing_of_defaults_to_zero():
    assert reputation.standing_of(_hero(), "making") == 0


def test_grant_raises_standing_and_announces_a_tier_change():
    s = _hero()
    line = reputation.grant(s, "making", reputation.SWEAR_STANDING)  # 0 -> 100 == Friendly
    assert reputation.standing_of(s, "making") == 100
    assert line is not None and "Friendly" in line and "Making" in line


def test_grant_spills_over_allies_and_rivals():
    s = _hero()
    allies, rivals = relations_of("making")
    assert allies and rivals  # making has both, or this test proves nothing
    reputation.grant(s, "making", 100)
    for ally in allies:
        assert reputation.standing_of(s, ally) == 50  # allies shift half, same direction
    for rival in rivals:
        assert reputation.standing_of(s, rival) == -50  # rivals shift half, opposite


def test_a_negative_grant_lowers_standing_and_flips_the_spillover():
    s = _hero()
    allies, rivals = relations_of("making")
    reputation.grant(s, "making", -100)
    assert reputation.standing_of(s, "making") == -100
    for rival in rivals:
        assert reputation.standing_of(s, rival) == 50  # hurting an Order pleases its rivals


def test_a_tiny_grant_does_not_move_allies_whose_spillover_rounds_to_zero():
    s = _hero()
    allies, _ = relations_of("making")
    reputation.grant(s, "making", 1)  # 1 // 2 == 0 spillover -> allies untouched
    assert reputation.standing_of(s, "making") == 1
    assert all(reputation.standing_of(s, a) == 0 for a in allies)


def test_grant_is_a_no_op_for_an_unknown_order():
    s = _hero()
    assert reputation.grant(s, "no_such_order", 100) is None
    assert s.reputation == {}


def test_the_sheet_lists_every_order_with_tier_and_marks_the_sworn():
    s = _hero(order="making")
    s.reputation["making"] = 300
    sheet = reputation.render_standing(s)
    assert "Making Order (sworn): Honored (300)" in sheet
    assert sheet.count("\n") >= 4  # a line per Order plus the header


def test_swearing_an_order_earns_a_starting_standing():
    from kernel.world.orders import swear_order

    s = Session(player_id="rep", location="void", named=True)
    swear_order(s, "making")
    assert reputation.standing_of(s, "making") == reputation.SWEAR_STANDING  # Friendly on joining


def test_standing_persists_round_trip():
    s = _hero()
    s.reputation = {"making": 300, "knowing": -50}
    restored = _hero()
    reputation.restore(restored, reputation.serialize(s))
    assert restored.reputation == {"making": 300, "knowing": -50}


def test_restore_drops_unknown_or_malformed_pairs():
    s = _hero()
    reputation.restore(s, "making:120,ghost_order:9,junk,knowing:notanumber")
    assert s.reputation == {"making": 120}  # only the real, well-formed pair survives


def test_standing_verb_is_reachable_through_the_tick():
    out = forge.handle_command(Session(player_id="rep", location="void"), "standing")
    assert "Your standing with the Orders" in out
