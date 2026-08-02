"""CARD: respawn -- the world's RESPAWN PHILOSOPHY: a catalog of policies + the dynamic-spawn part.

The world already respawns things -- resettable items restock on a zone's beat, worked gather nodes
renew, the training dummy reassembles, a lethal boss recovers after felling a player -- but the
POLICY behind each lived only in the code that did it. This is the philosophy the campaign (Part IV)
asks for: one record per respawn policy naming WHAT respawns, its TRIGGER, its CADENCE, the gameplay
REASON it exists, and where it lives. Every respawn type earns its place; the completeness test pins
that each policy still points at a real behavior.

It also carries the primitive the DYNAMIC policies need: `pick_room`, a weighted choice of a spawn
site from a pool, so a wandering pickup can appear at one of several valid places instead of always
the same spot ("avoid static, predictable locations"). Pure and seedable, so a test draws exactly.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

# A module RNG for dynamic spawning: runtime game variety, not world-gen (which stays fixed).
# Tests seed or replace it to draw an exact site; it is never a source of security or secrecy.
SPAWN_RNG = random.Random()  # nosec B311 -- game spawn variety, not cryptographic


@dataclass(frozen=True)
class RespawnPolicy:
    """One respawn policy: what comes back, when, how often, and WHY the game wants it to."""

    key: str  # stable slug
    what: str  # the entity that respawns
    trigger: str  # what fires the respawn
    cadence: str  # how often / how fast
    reason: str  # the gameplay reason it exists (Part IV: every respawn earns its place)
    lives_in: tuple[str, str]  # (module, attribute) that implements it -- the completeness anchor
    dynamic: bool = False  # True once the site itself varies (uses pick_room), not just the timing


# The SHIPPED respawn policies. Each `lives_in` names a real callable, pinned by the test.
CATALOG: tuple[RespawnPolicy, ...] = (
    RespawnPolicy(
        key="zone_item_reset",
        what="a resettable seed item (a placed pickup a player carried off)",
        trigger="its area comes due on the world beat",
        cadence="every `beats_between` beats, while the area is empty (empty_only)",
        reason="keep a zone's pickups available without letting one player strip it permanently.",
        lives_in=("kernel.world.zones", "_perform_reset"),
    ),
    RespawnPolicy(
        key="gather_node",
        what="a worked gather node (an ore/herb vein)",
        trigger="the world beat, after the forager worked it",
        cadence="renews for THAT player after GATHER_COOLDOWN beats (per-player, uncontested)",
        reason="a forager always has somewhere to work, and no one can lock a node from others.",
        lives_in=("kernel.world.gather", "tick_gather"),
    ),
    RespawnPolicy(
        key="training_dummy",
        what="the training-ground dummy",
        trigger="the instant it is felled in combat",
        cadence="immediate, at full health",
        reason="a safe, endless sparring partner -- collapsing is its whole job.",
        lives_in=("kernel.world.combat", "land_hit"),
    ),
    RespawnPolicy(
        key="wandering_spawn",
        what="a wandering pickup (a `spawn_pool` item -- a rare herb, a loose relic)",
        trigger="an area it can appear in comes due on the world beat",
        cadence="one at a pick_room site, at most 1-in-`spawn_chance` resets, in-`seasons` only",
        reason="rewards exploration over route-memorization: the pickup moves and is often absent.",
        lives_in=("kernel.world.zones", "_spawn_wanderers"),
        dynamic=True,
    ),
    RespawnPolicy(
        key="lethal_recover",
        what="a lethal boss (and the felled player)",
        trigger="the boss fells a player",
        cadence="the boss recovers to full at once; the player wakes at their start room",
        reason="the fight is earned again -- no corpse-camping a downed hero, no free boss kill.",
        lives_in=("kernel.world.combat", "_fall_to_death"),
    ),
)

_BY_KEY = {p.key: p for p in CATALOG}


def policy(key: str) -> RespawnPolicy | None:
    """The respawn policy for a key, or None."""
    return _BY_KEY.get(key)


def pick_room(
    candidates: list[str], weights: list[int] | None = None, rng: random.Random | None = None
) -> str:
    """Choose one spawn site from a pool -- the dynamic-spawn primitive. Uniform by default, or
    `weights`-biased (heavier rooms drawn more often). Returns "" for an empty pool (a caller with
    no valid site spawns nothing, never crashes). Draws from SPAWN_RNG unless a `rng` is given."""
    if not candidates:
        return ""
    draw = rng or SPAWN_RNG
    if weights is not None:
        if len(weights) != len(candidates):
            raise ValueError("pick_room: weights and candidates must be the same length")
        return draw.choices(candidates, weights=weights, k=1)[0]
    return draw.choice(candidates)


def render_policies() -> str:
    """A readable summary of every respawn policy -- the philosophy at a glance."""
    lines = ["The world's respawn policies:"]
    for p in CATALOG:
        tag = " (dynamic)" if p.dynamic else ""
        lines.append(f"- {p.key}{tag}: {p.what} -- {p.trigger}; {p.cadence}. Why: {p.reason}")
    return "\n".join(lines)
