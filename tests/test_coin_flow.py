"""Test twin for kernel/world/coin_flow.py -- the designed coin-economy audit.

Acceptance: a normal foe mints its level in coins, tier multiplies it, a levelless foe pays
a token off its xp, and a foe set totals by tier. Refusal/edge: peaceful NPCs mint nothing,
an empty (or all-peaceful) world is a zero faucet. Parity: the audit reuses combat's and
durability's own knobs, so it can never drift from the live game.
"""

from __future__ import annotations

from kernel import coin_flow
from kernel.coin_flow import faucet_breakdown, foe_faucet, render_audit


def _foe(hp=20, level=None, tier=None, xp=10, atk=4):
    n = {"hp": hp, "xp": xp, "atk": atk}
    if level is not None:
        n["level"] = level
    if tier is not None:
        n["tier"] = tier
    return n


# --- the faucet: coins minted on death -----------------------------------------------------------


def test_a_normal_foe_mints_its_level_in_coins():
    assert foe_faucet(_foe(level=5)) == 5  # normal tier = 1 coin per level


def test_tier_multiplies_the_drop():
    assert foe_faucet(_foe(level=5, tier="elite")) == 15  # x3
    assert foe_faucet(_foe(level=5, tier="boss")) == 50  # x10


def test_a_levelless_foe_pays_a_token_off_its_xp():
    assert foe_faucet(_foe(level=None, xp=30)) == 3  # max(1, xp // 10)
    assert foe_faucet(_foe(level=None, xp=4)) == 1  # never zero for a real foe


# --- the breakdown: a whole foe set ---------------------------------------------------------------


def test_faucet_breakdown_totals_and_splits_by_tier():
    foes = {
        "vermin": _foe(level=3, tier="normal"),  # 3
        "boar": _foe(level=4, tier="normal"),  # 4
        "captain": _foe(level=5, tier="elite"),  # 15
        "dragon": _foe(level=10, tier="boss"),  # 100
        "dummy": _foe(level=None, xp=30, atk=0),  # 3 (passive but killable)
    }
    fb = faucet_breakdown(foes)
    assert fb.foe_count == 5
    assert fb.total == 3 + 4 + 15 + 100 + 3
    assert fb.by_tier == {"normal": 7, "elite": 15, "boss": 100, "tutorial": 3}


def test_peaceful_npcs_mint_nothing():
    world = {
        "baker": _foe(hp=0, atk=0),  # a peaceful vendor: not killable, no coins
        "vermin": _foe(hp=16, level=3),
    }
    fb = faucet_breakdown(world)
    assert fb.foe_count == 1  # only the vermin
    assert fb.total == 3


def test_an_all_peaceful_or_empty_world_is_a_zero_faucet():
    assert faucet_breakdown({}).total == 0
    assert faucet_breakdown({"keeper": _foe(hp=0)}).total == 0


# --- parity: the audit reuses the game's own knobs (no drift) -------------------------------------


def test_sink_rates_reuse_the_owning_constants():
    from kernel.world import combat, durability  # noqa: PLC0415

    assert coin_flow.SINK_RATES.repair_cost_per_wear_point == durability.REPAIR_COST_PER_POINT
    assert coin_flow.SINK_RATES.fall_penalty_fraction == combat.DEATH_COIN_PENALTY
    assert coin_flow.SINK_RATES.boss_first_kill_bounty_mult == combat.BOSS_BOUNTY_MULT
    assert coin_flow.SINK_RATES.raid_first_kill_bounty_mult == combat.RAID_BOUNTY_MULT


def test_foe_faucet_is_exactly_the_live_combat_drop():
    from kernel.world import combat  # noqa: PLC0415

    foe = _foe(level=7, tier="elite")
    assert foe_faucet(foe) == combat._coin_reward(foe)  # audit == game, always


# --- the render -----------------------------------------------------------------------------------


def test_render_audit_shows_faucet_sinks_and_bounty():
    out = render_audit({"vermin": _foe(level=3), "dragon": _foe(level=10, tier="boss")})
    assert "FAUCET" in out and "SINKS" in out and "BOUNTY" in out
    assert "boss" in out  # the tier breakdown is shown


# --- the balance verdict: faucet vs the repair sink ----------------------------------------------


def test_fight_repair_sink_is_strikes_to_fell_at_the_reference_damage():
    # hp 16 at reference damage 10 -> ceil(16/10)=2 strikes -> 2 coins of weapon repair
    assert coin_flow.fight_repair_sink(_foe(hp=16)) == 2
    assert coin_flow.fight_repair_sink(_foe(hp=1)) == 1  # never zero for a real fight


def test_net_flow_is_the_drop_minus_the_fights_repair():
    # a boss L10 (hp 200): drop = 10*10 = 100; sink = ceil(200/10)=20; net = +80
    foe = _foe(hp=200, level=10, tier="boss")
    assert coin_flow.foe_faucet(foe) == 100
    assert coin_flow.fight_repair_sink(foe) == 20
    assert coin_flow.net_flow(foe) == 80


def test_a_high_faucet_low_hp_world_reads_inflationary():
    # a boss mints far more than its short fight drains -> the verdict flags inflation
    report = coin_flow.balance({"boss": _foe(hp=50, level=20, tier="boss")})  # drop 200, sink 5
    assert report.net == 195
    assert "INFLATIONARY" in report.verdict
    assert report.by_tier["boss"] == 195


def test_a_tanky_low_drop_world_can_balance():
    # a foe whose long fight costs more repair than its drop nets negative -> BALANCED verdict
    report = coin_flow.balance({"sponge": _foe(hp=100, level=1, tier="normal")})  # drop 1, sink 10
    assert report.net < 0
    assert "BALANCED" in report.verdict


def test_render_audit_now_carries_the_balance_verdict():
    out = render_audit({"dragon": _foe(hp=40, level=10, tier="boss")})
    assert "Coin Balance" in out and "NET" in out
    assert "INFLATIONARY" in out or "BALANCED" in out
