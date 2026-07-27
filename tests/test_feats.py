"""Test twin for parts/world/feats.py -- the derived deed ledger.

Acceptance: a fresh hero has earned nothing; a seasoned one earns the feats their persisted state
already proves (level/job/subjob/order/coins/rank), the ledger recomputes live, and the panel shows
earned vs locked with a next-deed nudge. Derive-don't-store: no feat carries its own state.
"""

from __future__ import annotations

import forge
from parts.world import feats
from parts.world.session import Session


def test_a_fresh_hero_has_earned_no_feats():
    s = Session(player_id="rookie")
    assert feats.earned_feats(s) == []
    out = feats.feats(s)
    assert "(0/" in out and "No deeds yet" in out


def test_feats_are_derived_live_from_the_characters_state():
    s = Session(player_id="hero")
    forge.handle_command(s, "job vanguard")  # "Called"
    s.level = 60  # Journeyman + Veteran
    s.secondary_job = "scout"  # Twin-Souled
    s.order = "warcraft"  # Sworn
    s.coins = 15_000  # Coinbearer (>= 1 ember)
    names = {f.name for f in feats.earned_feats(s)}
    assert names == {"Called", "Twin-Souled", "Sworn", "Journeyman", "Veteran", "Coinbearer"}
    assert "Master" not in names  # level 60 < 100


def test_the_ledger_recomputes_when_the_hero_grows():
    s = Session(player_id="climber")
    forge.handle_command(s, "job vanguard")
    s.level = 100
    assert any(f.name == "Master" for f in feats.earned_feats(s))
    s.level = 255
    assert any(f.name == "Ascendant" for f in feats.earned_feats(s))


def test_the_crown_is_a_feat_only_the_owner_earns():
    owner = Session(player_id="root", rank="owner")
    assert any(f.name == "The Maker" for f in feats.earned_feats(owner))
    player = Session(player_id="commoner", rank="player")
    assert not any(f.name == "The Maker" for f in feats.earned_feats(player))


def test_the_panel_reads_through_the_tick_and_nudges_the_next_deed():
    s = Session(player_id="hero")
    forge.handle_command(s, "job vanguard")
    s.level = 10
    out = forge.handle_command(s, "feats")
    assert "[x] Called" in out and "[x] Journeyman" in out
    assert "[ ] Veteran" in out and "Next:" in out  # a locked deed and the nudge toward it
