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
from typing import TYPE_CHECKING

from kernel.world.engine import Engine, Engine0D, NodePosition  # noqa: F401

if TYPE_CHECKING:
    from kernel.world.seed import Room


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


class Engine2D:
    """The tile engine, reading positions from a generated world overlay."""

    name = "2D"

    def __init__(self, overlay: object | None = None) -> None:
        if overlay is None:
            from kernel.overlay import load_overlay
            from kernel.world.seed import BLUEPRINT_DIR

            overlay = load_overlay(BLUEPRINT_DIR / "world_overlay.json")
        self._overlay = overlay

    def place(self, room: str) -> ChunkPosition:
        entry = self._overlay[room]  # type: ignore[index]
        return ChunkPosition(
            chunk_x=entry["chunk_x"],
            chunk_y=entry["chunk_y"],
            x=entry["x"],
            y=entry["y"],
            room=entry["room"],
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


@dataclass(frozen=True)
class AspectFalsifiability:
    """The measured strength of one battery aspect."""

    aspect: str
    probes: tuple[str, ...] = ()
    reason: str = ""

    def render(self) -> str:
        if self.probes:
            return f"{self.aspect}: falsifiable by {', '.join(self.probes)}"
        return f"{self.aspect}: structurally unfalsifiable - {self.reason}"


@dataclass
class SeamVerdict:
    """What the differential found. A word, never a bool."""

    commands_compared: int = 0
    aspects_covered: tuple[str, ...] = ()
    divergences: tuple[Divergence, ...] = ()
    unmeasured: tuple[str, ...] = field(default_factory=tuple)
    #: Probes whose answer CHANGES when the engine misbehaves, so they can actually report a
    #: divergence. The rest are regression guards: real, but not evidence of agreement today.
    falsifiable: tuple[str, ...] = field(default_factory=tuple)
    aspect_falsifiability: tuple[AspectFalsifiability, ...] = field(default_factory=tuple)
    unmeasurable_reason: str | None = None

    @property
    def verdict(self) -> str:
        if self.unmeasurable_reason is not None:
            return "UNMEASURABLE"
        if self.divergences:
            return "DIVERGED"
        if self.commands_compared == 0:
            return "INCONCLUSIVE"
        return "AGREED"

    def render(self) -> str:
        lines = [
            f"Engine seam :: {self.commands_compared} comparison(s) across "  # noqa: ISC004
            f"{len(self.aspects_covered)} aspect(s), "
            f"{len(self.falsifiable)} of them falsifiable"
        ]
        lines += [f"  DIVERGED {d.render()}" for d in self.divergences]
        lines += [f"  [unmeasured] {u}" for u in self.unmeasured]
        if self.unmeasurable_reason is not None:
            lines.append(f"  [unmeasurable] {self.unmeasurable_reason}")
        lines += [f"  [falsifiability] {record.render()}" for record in self.aspect_falsifiability]
        if not self.divergences:
            lines.append("  no divergence - the core did not ask where exactly you are")
        lines.append(f"VERDICT: {self.verdict}")
        return "\n".join(lines)


# The battery. Each entry is (aspect, name, probe) where probe takes an engine and returns an
# answer that MUST NOT depend on which engine is running. C1 names the four aspects; a battery
# missing one silently proves less than it claims, so the test asserts all four are present.
def _battery_for_seed(seed: str) -> list[tuple[str, str, object]]:
    from kernel.world import callings, coinage, items, progression

    return [
        ("inventory", "carry_limit", lambda e: e.carry_limit()),
        ("inventory", "purse_renders", lambda e: coinage.purse(7)),  # noqa: ARG005
        ("inventory", "module_is_position_free", lambda e: "location" not in dir(items)),  # noqa: ARG005
        ("progression", "xp_for_level", lambda e: progression.cumulative_xp_for_level(5)),  # noqa: ARG005
        ("progression", "jp_for_level", lambda e: progression.cumulative_jp_for_level(3)),  # noqa: ARG005
        ("progression", "calling_gate", lambda e: callings.gate_calling("cleric", {}, {}).open),  # noqa: ARG005
        ("permission", "rank_denies_admin", lambda e: _denies_admin(e)),  # noqa: PLW0108
        (
            "permission",
            "player_denies_teleport",
            lambda e: _permission_denial(e, "player", "@teleport forge"),
        ),
        (
            "permission",
            "wizard_denies_grant",
            lambda e: _permission_denial(e, "wizard", "@grant probe owner"),
        ),
        ("permission", "workshop_barrier_denies_wizard", lambda e: _workshop_denial(e)),  # noqa: PLW0108
        ("movement", "go_north", lambda e: _movement(e, seed, "north")),
        ("movement", "go_south", lambda e: _movement(e, seed, "south")),
        ("movement", "go_east", lambda e: _movement(e, seed, "east")),
        ("movement", "go_down", lambda e: _movement(e, seed, "down")),
        ("persistence", "grant_key_shape", lambda e: _grant_key()),  # noqa: ARG005
        ("persistence", "save_restore_casefile", lambda e: _save_restore(e)),  # noqa: PLW0108
        ("persistence", "gameplay_save_preserves_auth", lambda e: _gameplay_save()),  # noqa: ARG005
        ("coverage", "all_overlay_rooms", lambda e: _room_coverage(e, seed)),
    ]


def _battery() -> list[tuple[str, str, object]]:
    """The default first-forge battery, kept stable for calibration monkeypatches."""
    return _battery_for_seed("first-forge")


def _selected_battery(seed: str) -> list[tuple[str, str, object]]:
    """Select a Blueprint battery without changing the default monkeypatch contract."""
    return _battery() if seed == "first-forge" else _battery_for_seed(seed)


def _denies_admin(engine: Engine) -> bool:
    """A permission decision must not consult position. D1 puts permissions above the seam."""
    from kernel.world import ranks
    from kernel.world.session import Session

    # A rank decision consults the SESSION's rank, never its position. That is the whole point.
    return not ranks.has_rank(Session(player_id="probe", location="forge", engine=engine), "wizard")


def _grant_key() -> str:
    from kernel.world.reward_ledger import grant_key

    return grant_key("hero", "npc:dummy", 1)


def _permission_denial(engine: Engine, rank: str, command: str) -> str:
    from kernel.world.ranks import wizard_command
    from kernel.world.session import Session

    room = "forge"
    session = Session(player_id="probe", location=room, engine=engine, rank=rank)
    return wizard_command(session, command)


def _workshop_denial(engine: Engine) -> str:
    from kernel.world import creator_workshop
    from kernel.world.session import Session

    session = Session(player_id="probe", location="forge", engine=engine, rank="wizard")
    destination = creator_workshop.door_destination(session.location, "door")
    return (
        creator_workshop.barrier_refusal()
        if destination and not creator_workshop.is_seed_owner(session)
        else "The concealed door is not here."
    )


def _blueprint_rooms(seed: str) -> dict[str, Room]:
    from kernel.world.seed import BLUEPRINTS_ROOT, load_rooms

    return load_rooms(BLUEPRINTS_ROOT / seed / "rooms.yaml")


def _movement_route(rooms: dict[str, Room], preferred: str) -> tuple[str, str]:
    routes = [
        (room, direction) for room in sorted(rooms) for direction in sorted(rooms[room]["exits"])
    ]
    preferred_routes = [route for route in routes if route[1] == preferred]
    return (preferred_routes or routes)[0]


def _movement(engine: Engine, seed: str, preferred: str) -> tuple[str, str, str]:
    """Drive one real movement command through the loaded Blueprint's Session."""
    from unittest.mock import patch

    from forge import handle_command
    from kernel.world import world
    from kernel.world.session import Session

    rooms = _blueprint_rooms(seed)
    room, direction = _movement_route(rooms, preferred)
    session = Session(player_id=f"movement-{seed}-{preferred}", location=room, engine=engine)
    with patch("forge.WORLD", rooms), patch.object(world, "WORLD", rooms):
        before = session.location
        handle_command(session, f"go {direction}")
        after = session.location
    return before, after, "accepted" if after != before else "refused"


def _save_restore(engine: Engine) -> tuple[object, object]:
    from kernel.world.character_store import InMemoryCharacterStore
    from kernel.world.characters import load_character, put_record

    store = InMemoryCharacterStore()
    casefile = {
        "location": engine.room_of(engine.place("forge")),
        "level": 4,
        "xp": 27,
        "rank": "player",
    }
    put_record("probe", casefile, store)
    restored = load_character("probe", store)
    return casefile, restored


def _gameplay_save() -> tuple[str | None, str | None]:
    from kernel.world.character_store import CharacterRecord, InMemoryCharacterStore

    store = InMemoryCharacterStore()
    original = CharacterRecord(name="probe", location="forge", auth_salt="salt", auth_hash="hash")
    changed = CharacterRecord(name="probe", location="courtyard", level=2)
    store.upsert_full(original)
    store.upsert_gameplay(changed)
    restored = store.find("probe")
    return (original.auth_hash, restored.auth_hash if restored else None)


def _room_coverage(engine: Engine, seed: str = "first-forge") -> tuple[tuple[str, str], ...]:
    from kernel.overlay import load_overlay
    from kernel.world.seed import BLUEPRINTS_ROOT

    overlay = load_overlay(BLUEPRINTS_ROOT / seed / "world_overlay.json")
    return tuple((room, engine.room_of(engine.place(room))) for room in sorted(overlay))


def _overlay_rooms(seed: str = "first-forge") -> tuple[str, ...]:
    """Every room the Blueprint under test has, derived from its overlay."""
    from kernel.overlay import load_overlay
    from kernel.world.seed import BLUEPRINTS_ROOT

    return tuple(sorted(load_overlay(BLUEPRINTS_ROOT / seed / "world_overlay.json")))


def _overlay_for_seed(seed: str) -> object:
    """Make the tested overlay available without making non-coverage probes world-dependent."""
    from kernel.overlay import load_overlay
    from kernel.world.seed import BLUEPRINTS_ROOT

    tested = load_overlay(BLUEPRINTS_ROOT / seed / "world_overlay.json")
    if seed == "first-forge":
        return tested
    baseline = load_overlay(BLUEPRINTS_ROOT / "first-forge" / "world_overlay.json")
    combined = dict(baseline)
    combined.update(tested)
    return combined


def _saboteurs(seed: str = "first-forge") -> list[Engine]:
    """Deliberately wrong engines, one per lever the Protocol lets an engine control.

    The Protocol is the complete list of levers: `place`, `room_of`, `carry_limit`. If it ever
    gains a member, add a saboteur here, or the falsifiability count starts overstating itself.

    TWO THINGS WERE LEARNED BUILDING THIS, both by getting the number wrong first.

    Every saboteur produces a LEGAL state. A wrong room is a room that EXISTS. A first version
    returned a nonexistent room and scored 5 probes falsifiable; two of those were detecting an
    impossible state rather than a plausible one, and no engine can emit a room the world lacks.
    Valid rooms scored 3. The count an instrument reports is only as honest as the sabotage
    behind it.

    And the sweep covers EVERY room, not one. A second version picked a single valid room and
    scored 3, missing the workshop barrier, which only reacts when the room is the workshop. A
    probe sensitive to one specific room is invisible to a saboteur that never names it.
    """

    saboteur_overlay = _overlay_for_seed(seed)

    class WrongCarry(Engine2D):
        def __init__(self) -> None:
            super().__init__(saboteur_overlay)

        def carry_limit(self) -> int:
            return 999_999

    def _wrong_room(room: str) -> Engine:
        class WrongRoom(Engine2D):
            def __init__(self) -> None:
                super().__init__(saboteur_overlay)

            def room_of(self, position: object) -> str:  # noqa: ARG002
                return room

            def place(self, target: str) -> ChunkPosition:  # noqa: ARG002
                return super().place(room)

        return WrongRoom()

    return [WrongCarry(), *(_wrong_room(room) for room in _overlay_rooms(seed))]


def falsifiable_probes(seed: str = "first-forge") -> tuple[str, ...]:
    """The probes that can actually report a divergence, measured rather than asserted.

    A probe earns its place by CHANGING ITS ANSWER when the engine misbehaves. One that returns the
    same value under every legal sabotage cannot produce a divergence, so it raises the comparison
    count without raising the evidence. WO-S4 grew the battery from 8 comparisons to 14 and ten of
    the fourteen were of that kind; the contract allowed it because its calibration bar was written
    per aspect rather than per probe.

    UNFALSIFIABLE IS NOT WORTHLESS AND MUST NOT BE READ THAT WAY. Those probes are regression
    guards: if the core were later changed to consult position when computing XP, they would catch
    it. They are simply not evidence of agreement TODAY, and the two are different claims.

    Some aspects are structurally unfalsifiable by engine sabotage, and progression is one. D1 puts
    progression above the seam, so a progression probe that COULD diverge would itself be the leak.
    Manufacturing falsifiability there, by folding an engine-derived value into the answer, would
    buy a number and prove nothing. The honest instrument reports the count; it does not demand one
    per aspect.
    """
    good = Engine2D(_overlay_for_seed(seed))
    found: list[str] = []

    def _answer(probe: object, engine: Engine) -> tuple[bool, object]:
        """(ran, value). A raise is an ANSWER here, not something to swallow silently."""
        try:
            return True, probe(engine)  # type: ignore[operator]
        except Exception as exc:  # noqa: BLE001 - the exception IS the observation
            return False, f"raised:{type(exc).__name__}"

    for aspect, name, probe in _selected_battery(seed):
        ran, baseline = _answer(probe, good)
        if not ran:
            # A probe that cannot run against a healthy engine is UNMEASURED, and
            # run_differential already reports it as such. It is not falsifiable evidence.
            continue
        # Only the coverage probe needs Blueprint-derived SABOTEURS, because only it enumerates
        # the overlay's rooms; the rest are sabotaged against the fixed synthetic fixture.
        #
        # This is about which saboteurs to build, NOT about which probes read the Blueprint. The
        # comment here used to say sensitivity was "intentionally limited to the coverage probe,
        # the other thirteen remain on the fixed synthetic fixture", and #992 made that false when
        # it drove the movement probes from the Blueprint under test. Measured at a620f36d, FIVE
        # probes are Blueprint-sensitive (coverage/all_overlay_rooms plus the four movement
        # probes), and 13 are not. Its arithmetic was also stale: 1 + 13 = 14, from before the
        # battery grew to 18. Evidence: reports/2026-08-16-wo-2d-6-blueprint-sensitivity.md.
        wrong = _saboteurs(seed) if aspect == "coverage" else _saboteurs()
        for saboteur in wrong:
            _, sabotaged = _answer(probe, saboteur)
            if sabotaged != baseline:
                found.append(f"{aspect}/{name}")
                break
    return tuple(found)


_STRUCTURAL_UNFALSIFIABLE_REASONS = {
    "progression": (
        "Progression is above the engine seam under D1; a divergence would itself prove a leak."
    ),
    "permission": (
        "Permission is above the engine seam under D1; a divergence would itself prove a leak."
    ),
}

_NO_MEASURED_PROBE_REASON = (
    "No measured probe survived this battery run; falsifiability is unverified."
)


def _aspect_falsifiability(
    probes: tuple[str, ...], seed: str = "first-forge"
) -> tuple[AspectFalsifiability, ...]:
    """Classify every battery aspect from the measured probe names and D1 boundaries."""
    aspects = tuple(dict.fromkeys(aspect for aspect, _, _ in _selected_battery(seed)))
    by_aspect = {
        aspect: tuple(entry.split("/", 1)[1] for entry in probes if entry.startswith(f"{aspect}/"))
        for aspect in aspects
    }
    records: list[AspectFalsifiability] = []
    for aspect in aspects:
        aspect_probes = by_aspect[aspect]
        reason = (
            ""
            if aspect_probes
            else _STRUCTURAL_UNFALSIFIABLE_REASONS.get(aspect, _NO_MEASURED_PROBE_REASON)
        )
        records.append(AspectFalsifiability(aspect, aspect_probes, reason))
    return tuple(records)


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
    # The thirteen non-coverage probes use the fixed synthetic ``forge`` room. Keep that probe
    # fixture available without making their answers depend on the Blueprint under test; only the
    # existing coverage probe reads ``seed``'s overlay.
    if two_d is None:
        try:
            right = Engine2D(_overlay_for_seed(seed))
        except FileNotFoundError as exc:
            return SeamVerdict(
                unmeasurable_reason=(
                    f"Blueprint {seed!r} is UNMEASURABLE: missing overlay file {exc.filename}"
                )
            )
    else:
        right = two_d

    divergences: list[Divergence] = []
    unmeasured: list[str] = []
    aspects: list[str] = []
    compared = 0

    for aspect, name, probe in _selected_battery(seed):
        # An aspect counts as COVERED only once a probe of it actually ran. Listing it on sight
        # let three broken probes sit unmeasured while the coverage test passed, which is the
        # dominant defect of this Workshop reproduced inside the instrument built to catch it.
        try:
            a, b = probe(left), probe(right)  # type: ignore[operator]
        except (
            Exception  # noqa: BLE001
        ) as exc:  # a probe that cannot run is UNMEASURED, never agreement
            unmeasured.append(f"{aspect}/{name}: {type(exc).__name__}: {exc}")
            continue
        compared += 1
        if aspect not in aspects:
            aspects.append(aspect)
        if a != b:
            divergences.append(Divergence(aspect=aspect, command=name, zero_d=a, two_d=b))

    falsifiable = falsifiable_probes(seed)
    return SeamVerdict(
        falsifiable=falsifiable,
        aspect_falsifiability=_aspect_falsifiability(falsifiable, seed),
        commands_compared=compared,
        aspects_covered=tuple(aspects),
        divergences=tuple(divergences),
        unmeasured=tuple(unmeasured),
    )
