"""CARD: coverage -- every engine capability must be witnessed by shipped content (no dark feature).

The Convergence Review (2026-07-17) named the ship's recurring failure mode: a capability is built,
tested, and filed, yet its LAST INCH is orphaned. No shipped seed exercises it, so a stranger who
plays the game never meets it (proactive NPCs shipped green in unit tests but dark in every seed).
This gate closes that whole class. Each engine capability the world is meant to demonstrate must be
witnessed by at least one shipped seed pack, or be explicitly RESERVED with a reason. Adding a
headline capability then forces a choice, wire it into content or reserve it, never ship it dark.

The world is data (architecture law 2): a capability is only real when a seed uses it. This gate
makes that law enforceable, the same shape as the registry's completeness gate: a curated checklist
of capabilities plus a detector each, and a test twin that pins zero unexercised capabilities.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from parts.world.seed import (
    SEEDS_ROOT,
    Door,
    Item,
    Job,
    Npc,
    QuestSpec,
    load_doors,
    load_items,
    load_jobs,
    load_npcs,
    load_quest,
)


@dataclass(frozen=True)
class PackContent:
    """The loaded content of one shipped seed pack, enough to witness each capability."""

    pack: str
    npcs: dict[str, Npc]
    doors: dict[str, Door]
    items: dict[str, Item]
    jobs: dict[str, Job]
    quest: QuestSpec | None


@dataclass(frozen=True)
class Capability:
    """One engine capability shipped content is meant to demonstrate, and how to detect it."""

    name: str
    description: str
    witnessed_by: Callable[[PackContent], bool]


# The curated capability checklist. Add a row when a headline capability lands; the gate then
# requires a seed to exercise it (or a RESERVED entry below). Detectors read the seed schema, so a
# capability is witnessed only by real content, never by the presence of engine code.
CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        "proactive_combat",
        "an aggressive NPC that strikes first on the world beat",
        lambda c: any(npc.get("aggressive") for npc in c.npcs.values()),
    ),
    Capability(
        "reactive_combat",
        "an NPC that counters when struck (a nonzero atk stat)",
        lambda c: any(npc.get("atk", 0) > 0 for npc in c.npcs.values()),
    ),
    Capability(
        "locked_barrier",
        "a locked door gating an exit (the doors and keys system)",
        lambda c: any(door.get("locked") for door in c.doors.values()),
    ),
    Capability(
        "quest",
        "a multi-step quest (the story-beat system)",
        lambda c: c.quest is not None,
    ),
    Capability(
        "equipment",
        "an equippable item that grants stat modifiers (a nonempty mods map)",
        lambda c: any(item.get("mods") for item in c.items.values()),
    ),
    Capability(
        "calling",
        "a job a player can take up (the calling system)",
        lambda c: len(c.jobs) > 0,
    ),
)

# Capabilities deliberately not yet exercised by any shipped pack. A name here is a conscious
# declaration ("built, not yet content"), not an accident; each carries a reason. Empty today:
# every capability above is witnessed by a shipped seed.
RESERVED: dict[str, str] = {}


def _load_pack(pack_dir: Path) -> PackContent:
    """Load one pack's content. A file a pack omits (spiral-ascent has no doors or quest) is an
    absence, not an error: that pack simply does not witness the capabilities it would carry."""

    def _table(loader: Callable[[Path], dict], filename: str) -> dict:
        path = pack_dir / filename
        return loader(path) if path.exists() else {}

    quest_path = pack_dir / "quest.yaml"
    return PackContent(
        pack=pack_dir.name,
        npcs=_table(load_npcs, "npcs.yaml"),
        doors=_table(load_doors, "doors.yaml"),
        items=_table(load_items, "items.yaml"),
        jobs=_table(load_jobs, "jobs.yaml"),
        quest=load_quest(quest_path) if quest_path.exists() else None,
    )


def shipped_packs(root: Path = SEEDS_ROOT) -> list[PackContent]:
    """Every seed pack under root (a directory holding a splash.txt), loaded. Injectable root so the
    gate is tested against a fixture world, never only the live seeds."""
    packs = sorted(d for d in root.iterdir() if d.is_dir() and (d / "splash.txt").exists())
    return [_load_pack(d) for d in packs]


def _coverage(packs: list[PackContent]) -> dict[str, list[str]]:
    """For each capability, the packs (from this set) that witness it. Pure: no filesystem."""
    return {cap.name: [c.pack for c in packs if cap.witnessed_by(c)] for cap in CAPABILITIES}


def coverage(root: Path = SEEDS_ROOT) -> dict[str, list[str]]:
    """For each capability, the packs that witness it (evidence). Empty list = unexercised."""
    return _coverage(shipped_packs(root))


def _violations(seen: dict[str, list[str]]) -> list[str]:
    """The gate logic over a coverage map. Pure, so it is tested without a fixture world."""
    problems: list[str] = []
    for cap in CAPABILITIES:
        witnesses = seen[cap.name]
        if not witnesses and cap.name not in RESERVED:
            problems.append(
                f"dark capability '{cap.name}' ({cap.description}): no shipped seed exercises it. "
                f"Wire it into a seed, or add it to coverage.RESERVED with a reason."
            )
        if witnesses and cap.name in RESERVED:
            problems.append(
                f"stale reserve '{cap.name}': marked RESERVED but now exercised by {witnesses}. "
                f"Remove it from coverage.RESERVED."
            )
    return problems


def unexercised_capabilities(root: Path = SEEDS_ROOT) -> list[str]:
    """Capabilities no shipped pack witnesses and that are not RESERVED: the gate's violations.
    A RESERVED capability that a pack DOES exercise is also flagged, so the reserve list cannot go
    stale and quietly hide a now-covered capability."""
    return _violations(coverage(root))


def coverage_report(root: Path = SEEDS_ROOT) -> str:
    """Human render: each capability, its witnessing packs or a DARK/RESERVED flag."""
    seen = coverage(root)
    lines = ["Content coverage (every engine capability witnessed by shipped content):"]
    for cap in CAPABILITIES:
        witnesses = seen[cap.name]
        if witnesses:
            mark = "witnessed by " + ", ".join(witnesses)
        elif cap.name in RESERVED:
            mark = f"RESERVED ({RESERVED[cap.name]})"
        else:
            mark = "DARK -- no seed exercises it"
        lines.append(f"  {cap.name}: {mark}")
    problems = unexercised_capabilities(root)
    lines.append("")
    lines.append(
        "Coverage: CLEAN (every capability witnessed or reserved)"
        if not problems
        else "Coverage PROBLEMS:\n  " + "\n  ".join(problems)
    )
    return "\n".join(lines)
