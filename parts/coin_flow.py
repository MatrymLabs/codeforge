"""CARD: coin_flow -- the designed coin economy: where coins are minted (foe drops) and
burned (repair, the fall penalty), so live-ops can read the faucet/sink balance without
instrumenting the running server.

Read-only and pure: it reasons over foe DATA and the balance knobs that combat and
durability already own (reused here, never re-defined), so this audit and the live game
can never disagree -- a parity test pins that. It reports the DESIGNED economy (what the
numbers intend, if every foe is felled once); a later slice can add a live event seam for
the ACTUAL flow at population. This first slice answers "where do coins come from and go,
and in what proportion" -- the question the AAA scorecard flags as unanswerable today.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from parts.world.coinage import purse
from parts.world.combat import (
    BOSS_BOUNTY_MULT,
    DEATH_COIN_PENALTY,
    RAID_BOUNTY_MULT,
    _coin_reward,  # combat owns the drop formula; reuse it so the audit can never drift
)
from parts.world.durability import REPAIR_COST_PER_POINT
from parts.world.seed import Npc


@dataclass(frozen=True)
class FaucetBreakdown:
    """The designed coin faucet across a set of foes: the total minted by felling each once,
    split by the tier that set the rate, and how many foes contributed."""

    total: int
    by_tier: dict[str, int]
    foe_count: int


@dataclass(frozen=True)
class SinkRates:
    """The knobs that BURN coins, named from the code that owns them (reused, not re-defined)."""

    repair_cost_per_wear_point: int
    fall_penalty_fraction: float  # of the CARRIED purse, scattered on a non-lethal fall
    boss_first_kill_bounty_mult: int  # a faucet AMPLIFIER on the period's first boss kill
    raid_first_kill_bounty_mult: int  # ...and the (larger) weekly raid amplifier


SINK_RATES = SinkRates(
    repair_cost_per_wear_point=REPAIR_COST_PER_POINT,
    fall_penalty_fraction=DEATH_COIN_PENALTY,
    boss_first_kill_bounty_mult=BOSS_BOUNTY_MULT,
    raid_first_kill_bounty_mult=RAID_BOUNTY_MULT,
)


def _is_combatant(npc: Npc) -> bool:
    """A foe mints coins on death; a peaceful NPC (vendor, voice) does not. The discriminator is
    killability: authored peaceful NPCs carry `hp: 0`, every foe carries hp > 0 (even the passive
    training dummy, which is farmable and does drop a token purse)."""
    return npc.get("hp", 0) > 0


def foe_faucet(npc: Npc) -> int:
    """The coins one foe is designed to mint on death -- combat's own `_coin_reward`, reused so
    the audit and the live drop can never disagree."""
    return _coin_reward(npc)


def faucet_breakdown(npcs: dict[str, Npc]) -> FaucetBreakdown:
    """Total designed coin injection if every combatant in `npcs` is felled once, split by tier.
    Peaceful NPCs are skipped; a levelless foe is filed under 'tutorial'."""
    by_tier: dict[str, int] = {}
    total = 0
    count = 0
    for npc in npcs.values():
        if not _is_combatant(npc):
            continue
        coins = foe_faucet(npc)
        tier = npc.get("tier", "normal") if npc.get("level") is not None else "tutorial"
        by_tier[tier] = by_tier.get(tier, 0) + coins
        total += coins
        count += 1
    return FaucetBreakdown(total=total, by_tier=by_tier, foe_count=count)


# --- the balance verdict: does the faucet outrun the repair sink? --------------------------------
#
# The only sink that scales with combat (the activity that mints coins) is gear repair: each landed
# strike wears one point = REPAIR_COST_PER_POINT coins to mend. So the coin a kill NETS into the
# economy is its drop minus the repair the fight cost. Fight length is modelled from the foe's HP at
# a documented reference strike: real level-appropriate players hit HARDER than this, so they land
# FEWER strikes and pay LESS repair -- so any inflation this reports is a conservative floor, never
# an overstatement.
REFERENCE_STRIKE_DAMAGE = 10  # a deliberately low, documented per-strike reference (see above)


@dataclass(frozen=True)
class BalanceReport:
    """Whether the designed economy mints faster than it drains, over a foe set.

    `net` is total faucet minus total repair-sink; positive means coins accumulate (inflationary).
    `by_tier` shows the net per tier, so the steepest imbalance (bosses) is visible."""

    total_faucet: int
    total_repair_sink: int
    net: int
    by_tier: dict[str, int]
    verdict: str


def fight_repair_sink(npc: Npc) -> int:
    """The coins repairing the wear of one fight costs: strikes-to-fell (HP at the reference strike)
    times the per-point repair rate. One point of weapon wear per landed strike."""
    hp = npc.get("hp", 0)
    strikes = max(1, ceil(hp / REFERENCE_STRIKE_DAMAGE))
    return strikes * REPAIR_COST_PER_POINT


def net_flow(npc: Npc) -> int:
    """Coins one kill nets into the economy: its drop minus the repair its fight costs."""
    return foe_faucet(npc) - fight_repair_sink(npc)


def balance(npcs: dict[str, Npc]) -> BalanceReport:
    """The faucet-vs-repair-sink balance over a foe set, with a one-line verdict."""
    faucet = 0
    sink = 0
    by_tier: dict[str, int] = {}
    for npc in npcs.values():
        if not _is_combatant(npc):
            continue
        faucet += foe_faucet(npc)
        sink += fight_repair_sink(npc)
        tier = npc.get("tier", "normal") if npc.get("level") is not None else "tutorial"
        by_tier[tier] = by_tier.get(tier, 0) + net_flow(npc)
    net = faucet - sink
    if net <= 0:
        verdict = "BALANCED: repair drains at least what kills mint."
    else:
        pct = round(100 * net / faucet) if faucet else 0
        verdict = (
            f"INFLATIONARY: kills mint {pct}% more than repair drains "
            "(a conservative floor; real players hit harder and pay less repair)."
        )
    return BalanceReport(
        total_faucet=faucet, total_repair_sink=sink, net=net, by_tier=by_tier, verdict=verdict
    )


def render_balance(npcs: dict[str, Npc]) -> str:
    """A live-ops verdict on the faucet/repair-sink balance, by tier."""
    b = balance(npcs)
    lines = ["== Coin Balance (faucet vs repair sink) =="]
    lines.append(f"FAUCET  {purse(b.total_faucet)}   REPAIR SINK  {purse(b.total_repair_sink)}")
    lines.append(f"NET     {'+' if b.net >= 0 else ''}{purse(b.net)} per full clear")
    for tier, tier_net in sorted(b.by_tier.items()):
        lines.append(f"          {tier:8} net {'+' if tier_net >= 0 else ''}{purse(tier_net)}")
    lines.append(b.verdict)
    return "\n".join(lines)


def render_audit(npcs: dict[str, Npc]) -> str:
    """A live-ops one-look report of the designed coin economy over a foe set."""
    fb = faucet_breakdown(npcs)
    lines = ["== Coin Economy Audit (designed) =="]
    lines.append(f"FAUCET  {purse(fb.total)} minted per full clear of {fb.foe_count} foe(s)")
    for tier, amount in sorted(fb.by_tier.items()):
        lines.append(f"          {tier:8} {purse(amount)}")
    lines.append(
        f"SINKS   repair {SINK_RATES.repair_cost_per_wear_point} cinder/wear-point; "
        f"a fall scatters {int(SINK_RATES.fall_penalty_fraction * 100)}% of the carried purse"
    )
    lines.append(
        f"BOUNTY  period-first kill pays x{SINK_RATES.boss_first_kill_bounty_mult} (boss) / "
        f"x{SINK_RATES.raid_first_kill_bounty_mult} (raid) the drop"
    )
    lines.append("")
    lines.append(render_balance(npcs))
    return "\n".join(lines)
