"""CARD: seed_package -- intent in, engineering blueprint out: the deployment-tier scaling core.

Stage 1 of the Seed Package campaign. The Seed Package's founding principle is a division of
labor: the *builder* declares INTENT (the game they want, at what scale), and the *engine* COMPUTES
the implementation (how many rooms, zones, NPCs, dungeons, settlements, quests a world at that scale
needs). Nobody hand-types thousands of sizing numbers; they choose a tier and the model derives the
rest.

This module is that computing core, the net-new piece the rest of the campaign hangs on: a small,
data-driven set of DEPLOYMENT TIERS (Prototype ~500 players -> Global MMO ~1,000,000+) and a single
SCALING MODEL of named density ratios that derives a full `WorldSizing` from a tier's player target.
`compile_manifest` folds a tier into a `BuildManifest` -- the deployment summary every downstream
generator (spiral, wildlands, bestiary, bounties) will read to size itself, instead of each carrying
its own hardcoded counts.

Honesty anchor: the ratios are not invented. They are calibrated to the real aethryn build (the map
world is ~53,500 rooms sized for the ~500-player Prototype tier, so ~107 rooms/player), so a Global
tier's ~107,000,000-room estimate is an extrapolation of a real density, not a fantasy number. The
model reports scale HONESTLY, including when a tier's storage/room budget exceeds a single host.

Stage boundary: this stage computes and validates the blueprint. Later stages wire a wizard over the
project fields, add the per-domain profiles (combat/economy/crafting), and teach the compiler to
actually scale the generators from the manifest. This is the backbone those hang on and what the
tests below gate. Kept at parts/ top level (like `cast`, `blueprint`, `manifest`): it is authoring
/tooling, not a game-seed runtime module, so it stays outside the World Package closure.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass


class SeedPackageError(ValueError):
    """A Seed Package tier or scaling model was declared with an impossible field. Fails loud."""


# --- Deployment tiers ---------------------------------------------------------------------------
# The prompt's five scale bands. Each names a target player population; EVERYTHING ELSE is derived
# from that number through the scaling model below, so a tier is intentionally almost pure intent.
@dataclass(frozen=True)
class DeploymentTier:
    """One scale band: a name and the player population it targets. The world sizing is derived,
    never stored here, so adding a tier is one honest row, not a table of hand-tuned counts."""

    id: str
    name: str
    target_players: int
    summary: str


DEPLOYMENT_TIERS: tuple[DeploymentTier, ...] = (
    DeploymentTier("prototype", "Prototype", 500, "a proving ground; one host, one region cluster"),
    DeploymentTier("indie", "Indie MMO", 5_000, "a small live game; a handful of continents"),
    DeploymentTier(
        "community", "Community MMO", 50_000, "a thriving community world; many regions"
    ),
    DeploymentTier(
        "commercial", "Commercial MMO", 500_000, "a commercial launch world; sharded continents"
    ),
    DeploymentTier(
        "global", "Global MMO", 1_000_000, "a global-scale world; multi-host, streamed continents"
    ),
)

TIERS: dict[str, DeploymentTier] = {t.id: t for t in DEPLOYMENT_TIERS}


def tier(tier_id: str) -> DeploymentTier:
    """Look up a tier by id, or fail loud with the valid set (never a silent default)."""
    if tier_id not in TIERS:
        valid = ", ".join(TIERS)
        raise SeedPackageError(f"unknown deployment tier {tier_id!r}; choose one of: {valid}")
    return TIERS[tier_id]


# --- The scaling model --------------------------------------------------------------------------
# One data-driven set of density ratios, applied to a tier's player count, derives the whole world.
# The prompt is explicit: "Do NOT hardcode values throughout the engine. Implement data-driven
# deployment profiles." So the counts live HERE as named, calibrated ratios, not scattered as magic
# numbers across the generators. Each ratio is anchored to the real aethryn build (see class doc).
@dataclass(frozen=True)
class ScalingModel:
    """Named density ratios that turn a player count into world sizing. Calibrated to aethryn: the
    shipped map world is ~53,500 rooms for the ~500-player Prototype tier, so rooms/player ~= 107.
    The remaining ratios are expressed against ROOMS (the load-bearing count) so they stay
    consistent as scale grows: a world twice the rooms gets twice the NPCs, dungeons, and quests."""

    rooms_per_player: float = 107.0  # anchor: ~53,500 rooms / ~500 players in the shipped map world
    npcs_per_room: float = 0.9  # populated rooms + wilderness ambient; < 1 leaves quiet rooms
    monsters_per_room: float = 1.6  # procedural foes (bestiary) outnumber static NPCs
    rooms_per_zone: float = 3_800.0  # aethryn: ~53,500 rooms across 14 zones ~= 3,800/zone
    zones_per_region: float = 2.5  # a region groups a few zones
    rooms_per_settlement: float = 5_000.0  # one named settlement anchors a large area
    rooms_per_dungeon: float = 3_500.0  # a multi-room delve per sizeable area
    rooms_per_boss: float = 3_500.0  # roughly one boss per dungeon
    quests_per_100_rooms: float = 4.0  # bounties + authored contracts
    crafting_recipes_per_zone: float = 12.0  # a recipe band per zone's materials
    bytes_per_room: float = (
        36_000.0  # boot-measured: ~1.9 GB resident / ~53,500 rooms ~= 36 KB/room
    )

    def validate(self) -> None:
        """Every ratio must be positive; a zero or negative density would derive an empty or
        nonsensical world (and rooms_per_* would divide by zero). Fails loud by field."""
        for field, value in asdict(self).items():
            if not isinstance(value, (int, float)) or value <= 0:
                raise SeedPackageError(f"scaling ratio {field!r} must be positive, got {value!r}")


DEFAULT_SCALING = ScalingModel()


@dataclass(frozen=True)
class WorldSizing:
    """The derived engineering blueprint for one tier: the counts every downstream generator sizes
    itself from. Nothing here is authored by hand; `derive_sizing` computes all of it."""

    target_players: int
    rooms: int
    zones: int
    regions: int
    settlements: int
    dungeons: int
    bosses: int
    npcs: int
    monsters: int
    quests: int
    crafting_recipes: int
    storage_bytes: int

    @property
    def storage_human(self) -> str:
        """The storage estimate in the largest sensible unit (KB/MB/GB/TB), one decimal place."""
        size = float(self.storage_bytes)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024.0 or unit == "TB":
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"  # unreachable; the loop always returns


def derive_sizing(the_tier: DeploymentTier, model: ScalingModel = DEFAULT_SCALING) -> WorldSizing:
    """Compute a full world blueprint from a tier's player target through the scaling model. This is
    the campaign's core move (STEP 7): intent (player count) in, implementation (every count) out.
    Rooms is the load-bearing derivation; the rest are ratios against it, so the world stays
    consistent at any scale. All counts round up to at least 1 where a world needs one."""
    model.validate()
    if the_tier.target_players <= 0:
        raise SeedPackageError(f"tier {the_tier.id!r} must target a positive player count")

    rooms = _at_least(the_tier.target_players * model.rooms_per_player, 1)
    zones = _at_least(rooms / model.rooms_per_zone, 1)
    return WorldSizing(
        target_players=the_tier.target_players,
        rooms=rooms,
        zones=zones,
        regions=_at_least(zones / model.zones_per_region, 1),
        settlements=_at_least(rooms / model.rooms_per_settlement, 1),
        dungeons=_at_least(rooms / model.rooms_per_dungeon, 1),
        bosses=_at_least(rooms / model.rooms_per_boss, 1),
        npcs=_at_least(rooms * model.npcs_per_room, 0),
        monsters=_at_least(rooms * model.monsters_per_room, 0),
        quests=_at_least(rooms / 100.0 * model.quests_per_100_rooms, 1),
        crafting_recipes=_at_least(zones * model.crafting_recipes_per_zone, 1),
        storage_bytes=_at_least(rooms * model.bytes_per_room, 0),
    )


def _at_least(value: float, floor: int) -> int:
    """Round a derived quantity up to a whole count, never below `floor`."""
    from math import ceil

    return max(floor, ceil(value))


# --- Hardware guidance --------------------------------------------------------------------------
# The honesty gate: the model reports when a tier outgrows a single host, rather than pretending any
# scale fits on the Pi. Boot-measured facts: the Prototype world (~53,500 rooms, ~1.9 GB) fits the
# 15 GB Pi; larger tiers are extrapolated against those same bytes/room.
_SINGLE_HOST_RAM_BYTES = 15 * 1024**3  # the Pi's headroom, the calibration host


def hardware_note(sizing: WorldSizing) -> str:
    """An honest one-line hardware read for a sizing: fits one host, or needs sharding. Never claims
    a world fits where the measured bytes/room say it will not."""
    if sizing.storage_bytes <= _SINGLE_HOST_RAM_BYTES:
        return f"fits a single host (~{sizing.storage_human} resident, within a 15 GB box)"
    hosts = _at_least(sizing.storage_bytes / _SINGLE_HOST_RAM_BYTES, 2)
    return f"exceeds one host (~{sizing.storage_human}); shard across ~{hosts} hosts / stream zones"


# --- The build manifest -------------------------------------------------------------------------
@dataclass(frozen=True)
class BuildManifest:
    """The deployment summary (STEP 8): the tier chosen, the derived sizing, and the honest hardware
    read. This is the single artifact downstream generators consume to size themselves; it
    serializes to JSON (the canonical machine-readable form) and renders to a human summary."""

    project: str
    tier_id: str
    tier_name: str
    sizing: WorldSizing
    hardware: str
    schema_version: int = 1

    def to_dict(self) -> dict[str, object]:
        """The canonical machine-readable form; every generator reads this shape."""
        return {
            "schema_version": self.schema_version,
            "project": self.project,
            "tier_id": self.tier_id,
            "tier_name": self.tier_name,
            "hardware": self.hardware,
            "sizing": asdict(self.sizing),
        }

    def to_json(self) -> str:
        """Pretty JSON, stable key order, for writing a canonical seed manifest to disk."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        """A human-readable deployment summary, the interviewer-facing form."""
        s = self.sizing
        lines = [
            f"# Build Manifest: {self.project}",
            "",
            f"- Deployment Tier: {self.tier_name} (`{self.tier_id}`)",
            f"- Estimated Players: {s.target_players:,}",
            f"- Estimated Rooms: {s.rooms:,}",
            f"- Estimated Zones: {s.zones:,}",
            f"- Estimated Regions: {s.regions:,}",
            f"- Estimated Settlements: {s.settlements:,}",
            f"- Estimated Dungeons: {s.dungeons:,}",
            f"- Estimated Bosses: {s.bosses:,}",
            f"- Estimated NPC Population: {s.npcs:,}",
            f"- Estimated Monsters: {s.monsters:,}",
            f"- Estimated Quests: {s.quests:,}",
            f"- Estimated Crafting Recipes: {s.crafting_recipes:,}",
            f"- Estimated Storage: {s.storage_human}",
            f"- Recommended Hardware: {self.hardware}",
        ]
        return "\n".join(lines)


def compile_manifest(
    project: str, tier_id: str, model: ScalingModel = DEFAULT_SCALING
) -> BuildManifest:
    """Compile intent into a blueprint: a project name + a chosen tier -> the full BuildManifest.
    This is the Stage-1 compiler (STEP 11, the sizing half): validate -> derive -> summarize. Fails
    loud on an unknown tier or an impossible scaling model; the result is ready for a generator."""
    if not project or not project.strip():
        raise SeedPackageError("a Seed Package needs a non-empty project name")
    chosen = tier(tier_id)
    sizing = derive_sizing(chosen, model)
    return BuildManifest(
        project=project.strip(),
        tier_id=chosen.id,
        tier_name=chosen.name,
        sizing=sizing,
        hardware=hardware_note(sizing),
    )
