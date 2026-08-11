"""CARD: engine_seam -- one core, two transmissions, and the instrument that keeps them honest.

ENGINE_SEAM.md D1: CodeForge is a platform with two interchangeable engines. The CORE is everything
that never needs to ask *where exactly are you*: identity, auth, persistence, permissions, command
dispatch, inventory, progression, Callings, economy, events, world-as-data. BELOW the seam sits
position type, spatial index, movement resolution, adjacency and range queries, collision, tick
cadence, renderer binding.

D3 fixes the single variable the engines differ by: position granularity. In Engine-0D a position
IS which node you occupy. In Engine-2D it is a coordinate within a chunk. D4 fixes what they share:
a ROOM is a semantic label spanning one or more chunks, so both engines can always answer "which
room is this session semantically in", and everything above that answer is core.

This module is the seam stated in code, plus the differential that guards it. It IMPORTS the core
and modifies nothing, per the Twin Engine Sprint section 3.

WHAT A DIVERGENCE MEANS. Not a bug to fix at the bench. C1: any divergence means something leaked
across the seam, and the sprint's kill criteria route that finding to the founder as a decision. A
DIVERGED verdict is this instrument working, not failing.

Verdicts are words, never bools: AGREED, DIVERGED, or INCONCLUSIVE when the battery could not run.
"could not measure" and "measured and found nothing" are different answers, and a Workshop that
rounds the first up to the second has been caught doing exactly that four times this week.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class NodePosition:
    """Engine-0D: position IS the node. D3."""

    room: str


@dataclass(frozen=True)
class ChunkPosition:
    """Engine-2D: position is a coordinate within a chunk, and a chunk carries a room label.

    D4: chunk is not room. Several chunks may share one room label, which is why `room` rides on
    the position rather than being derived from the coordinates.
    """

    chunk_x: int
    chunk_y: int
    x: int
    y: int
    room: str


@runtime_checkable
class Engine(Protocol):
    """The seam. Everything an engine must answer, and deliberately nothing more.

    If this Protocol ever needs a method that is not about position, the seam has moved and
    something core has slid below it.
    """

    name: str

    def place(self, room: str) -> object:
        """Put a session in a room, in this engine's own position representation."""
        ...

    def room_of(self, position: object) -> str:
        """The semantic room label. The one question both engines must answer identically."""
        ...

    def carry_limit(self) -> int:
        """A deliberately NON-spatial answer, included to prove the seam holds.

        How much a character can carry has nothing to do with position granularity. It sits here
        only so the differential has a core answer to compare that an engine could plausibly, and
        wrongly, decide to override.
        """
        ...


class Engine0D:
    """The text engine: position is a node on a graph. The engine CodeForge runs today."""

    name = "0D"

    def place(self, room: str) -> NodePosition:
        return NodePosition(room=room)

    def room_of(self, position: object) -> str:
        assert isinstance(position, NodePosition)
        return position.room

    def carry_limit(self) -> int:
        return 10


class Engine2DStub:
    """The tile engine, position type only. No renderer, no collision, no tick cadence.

    A stub on purpose: WO-S1 proves the SEAM, and a renderer would prove a renderer. Chunk
    coordinates are derived deterministically from the room label so the mapping is reproducible
    without a world overlay, which is D5's build step and is not Phase 0.
    """

    name = "2D"
    CHUNK = 16

    def place(self, room: str) -> ChunkPosition:
        seed = sum(ord(c) for c in room)
        return ChunkPosition(
            chunk_x=seed % 8,
            chunk_y=(seed // 8) % 8,
            x=seed % self.CHUNK,
            y=(seed // self.CHUNK) % self.CHUNK,
            room=room,
        )

    def room_of(self, position: object) -> str:
        assert isinstance(position, ChunkPosition)
        return position.room

    def carry_limit(self) -> int:
        return 10


@dataclass(frozen=True)
class Divergence:
    """One place the two engines disagreed about something that is not position."""

    aspect: str
    command: str
    zero_d: object
    two_d: object

    def render(self) -> str:
        return f"{self.aspect}/{self.command}: 0D said {self.zero_d!r}, 2D said {self.two_d!r}"


@dataclass
class SeamVerdict:
    """What the differential found. A word, never a bool."""

    commands_compared: int = 0
    aspects_covered: tuple[str, ...] = ()
    divergences: tuple[Divergence, ...] = ()
    unmeasured: tuple[str, ...] = field(default_factory=tuple)

    @property
    def verdict(self) -> str:
        if self.divergences:
            return "DIVERGED"
        if self.commands_compared == 0:
            return "INCONCLUSIVE"
        return "AGREED"

    def render(self) -> str:
        lines = [
            f"Engine seam :: {self.commands_compared} comparison(s) across "
            f"{len(self.aspects_covered)} aspect(s)"
        ]
        lines += [f"  DIVERGED {d.render()}" for d in self.divergences]
        lines += [f"  [unmeasured] {u}" for u in self.unmeasured]
        if not self.divergences:
            lines.append("  no divergence - the core did not ask where exactly you are")
        lines.append(f"VERDICT: {self.verdict}")
        return "\n".join(lines)


# The battery. Each entry is (aspect, name, probe) where probe takes an engine and returns an
# answer that MUST NOT depend on which engine is running. C1 names the four aspects; a battery
# missing one silently proves less than it claims, so the test asserts all four are present.
def _battery() -> list[tuple[str, str, object]]:
    from kernel.world import callings, coinage, items, progression

    return [
        ("inventory", "carry_limit", lambda e: e.carry_limit()),
        ("inventory", "purse_renders", lambda e: coinage.purse(7)),
        ("inventory", "module_is_position_free", lambda e: "location" not in dir(items)),
        ("progression", "xp_for_level", lambda e: progression.cumulative_xp_for_level(5)),
        ("progression", "jp_for_level", lambda e: progression.cumulative_jp_for_level(3)),
        ("progression", "calling_gate", lambda e: callings.gate_calling("cleric", {}, {}).open),
        ("permission", "rank_denies_admin", lambda e: _denies_admin()),
        ("persistence", "grant_key_shape", lambda e: _grant_key()),
    ]


def _denies_admin() -> bool:
    """A permission decision must not consult position. D1 puts permissions above the seam."""
    from kernel.world import ranks
    from kernel.world.session import Session

    # A rank decision consults the SESSION's rank, never its position. That is the whole point.
    return not ranks.has_rank(Session(player_id="probe", location="nowhere"), "wizard")


def _grant_key() -> str:
    from kernel.world.reward_ledger import grant_key

    return grant_key("hero", "npc:dummy", 1)


def run_differential(
    seed: str = "first-forge",
    zero_d: Engine | None = None,
    two_d: Engine | None = None,
) -> SeamVerdict:
    """Run one battery of NON-SPATIAL probes under both engines and compare every answer.

    `seed` names the trivial Seed the comparison is framed against. It is recorded rather than
    booted: every probe here is deliberately world-independent, because a probe that needs a booted
    world is testing the world rather than the seam.
    """
    left = zero_d or Engine0D()
    right = two_d or Engine2DStub()

    divergences: list[Divergence] = []
    unmeasured: list[str] = []
    aspects: list[str] = []
    compared = 0

    for aspect, name, probe in _battery():
        # An aspect counts as COVERED only once a probe of it actually ran. Listing it on sight
        # let three broken probes sit unmeasured while the coverage test passed, which is the
        # dominant defect of this Workshop reproduced inside the instrument built to catch it.
        try:
            a, b = probe(left), probe(right)  # type: ignore[operator]
        except Exception as exc:  # a probe that cannot run is UNMEASURED, never agreement
            unmeasured.append(f"{aspect}/{name}: {type(exc).__name__}: {exc}")
            continue
        compared += 1
        if aspect not in aspects:
            aspects.append(aspect)
        if a != b:
            divergences.append(Divergence(aspect=aspect, command=name, zero_d=a, two_d=b))

    return SeamVerdict(
        commands_compared=compared,
        aspects_covered=tuple(aspects),
        divergences=tuple(divergences),
        unmeasured=tuple(unmeasured),
    )
