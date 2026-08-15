"""WO-S1: the differential test. One Seed, two engines, identical non-spatial behaviour.

ENGINE_SEAM.md C1: Phase 0 proves an engine SEAM, not a renderer. The thing being proved is that
the core is genuinely engine-agnostic, and the instrument is this: boot the same trivial Seed under
Engine-0D and a stub Engine-2D and assert identical state transitions for every non-spatial
command. Same inventory mutations, same progression, same permission denials, same persistence.

**Any divergence is a FINDING, not a test failure to fix.** It means something leaked across the
seam, and per the Twin Engine Sprint's kill criteria that goes to the founder as a decision, never
to the bench as a rewrite.

D3 fixes what the engines differ by: position granularity. In 0D a position IS which node you
occupy; in 2D it is a coordinate within a chunk. D4 fixes what they share: a ROOM is a semantic
label, and one room spans one or more chunks. So both engines can always answer "which room is this
session semantically in", and everything above that answer is core.

Measured before this was written, on 2026-08-12:

    kernel/world modules touching .location   21 of 136
    items, progression, accounts, callings, coinage   0 each

So D1's claim is substantially true already. This test exists to keep it true, and to say so with
evidence rather than by assertion.

Shape consumed, not code: `Transform Verifier` (Working Shelf, kernel/shelf/transform_verifier.py)
runs two implementations against a hostile battery and calls a divergence a counterexample, with a
verdict word rather than a bool. Its inputs are code transforms rather than engines, so nothing was
imported; the discipline is what transferred.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from kernel.engine_seam import (
    Divergence,
    Engine0D,
    Engine2D,
    Engine2DStub,
    SeamVerdict,
    run_differential,
)
from kernel.overlay import generate_overlay, load_overlay

# The trivial Seed C1 asks for: a handful of rooms, one item, one command set. Deliberately small,
# because if the seam fails on something this size it is learned for the price of an afternoon.
TRIVIAL_SEED = "first-forge"


def test_both_engines_answer_the_same_room_for_the_same_placement() -> None:
    """The one thing both engines MUST agree on, per D4. Everything else builds on it."""
    zero_d, two_d = Engine0D(), Engine2DStub()
    for room in ("forge", "courtyard", "library"):
        assert zero_d.room_of(zero_d.place(room)) == room
        assert two_d.room_of(two_d.place(room)) == room


def test_engine_2d_reads_generated_geometry_not_the_stub_hash() -> None:
    """The stub collides on forge/classroom's chunk bucket; the overlay must not."""
    engine = Engine2D()
    forge, classroom = engine.place("forge"), engine.place("classroom")
    assert (forge.chunk_x, forge.chunk_y) != (classroom.chunk_x, classroom.chunk_y)


def test_overlay_generation_is_byte_deterministic(tmp_path) -> None:
    seed_rooms = Path("content/seeds/first-forge/rooms.yaml")
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    assert generate_overlay(seed_rooms, first) == generate_overlay(seed_rooms, second)
    assert first.read_bytes() == second.read_bytes()


def test_room_of_place_round_trips_every_generated_room() -> None:
    engine = Engine2D()
    for room in load_overlay(Path("content/seeds/first-forge/world_overlay.json")):
        assert engine.room_of(engine.place(room)) == room


def test_corrupt_overlay_fails_round_trip_then_restores(tmp_path) -> None:
    source = Path("content/seeds/first-forge/world_overlay.json")
    target = tmp_path / source.name
    target.write_bytes(source.read_bytes())
    payload = json.loads(target.read_bytes())
    payload["forge"]["room"] = "classroom"
    target.write_text(json.dumps(payload), encoding="utf-8")
    corrupted = Engine2D(load_overlay(target))
    assert corrupted.room_of(corrupted.place("forge")) != "forge"
    target.write_bytes(source.read_bytes())
    restored = Engine2D(load_overlay(target))
    assert restored.room_of(restored.place("forge")) == "forge"


def test_runtime_overlay_mapping_is_read_only() -> None:
    overlay = load_overlay(Path("content/seeds/first-forge/world_overlay.json"))
    with pytest.raises(TypeError):
        overlay["forge"] = overlay["forge"]  # type: ignore[index]
    with pytest.raises(TypeError):
        overlay["forge"]["x"] = 99  # type: ignore[index]


def test_the_engines_genuinely_differ_below_the_seam() -> None:
    """Guard the guard: if both engines are the same object, the differential proves nothing.

    A test that compares a thing to itself passes forever and measures nothing, which is this
    Workshop's dominant defect shape. The engines must differ in position REPRESENTATION while
    agreeing on the semantic room.
    """
    zero_d, two_d = Engine0D(), Engine2DStub()
    assert type(zero_d.place("forge")) is not type(two_d.place("forge")), (
        "both engines represent position identically, so the differential compares nothing"
    )


def test_a_non_spatial_battery_diverges_nowhere() -> None:
    """The differential itself. Inventory, progression, permission, persistence, both engines."""
    verdict = run_differential(seed=TRIVIAL_SEED)
    assert isinstance(verdict, SeamVerdict)
    assert verdict.commands_compared > 0, "a battery that ran nothing cannot report agreement"
    assert verdict.divergences == (), (
        f"the core is not engine-agnostic: {[d.render() for d in verdict.divergences]}"
    )
    assert verdict.verdict == "AGREED"


def test_real_engine_2d_passes_the_non_spatial_battery() -> None:
    verdict = run_differential(seed=TRIVIAL_SEED, two_d=Engine2D())
    assert verdict.commands_compared > 8
    assert verdict.divergences == ()
    assert verdict.verdict == "AGREED"


def test_widened_battery_has_multiple_probes_per_aspect_and_covers_overlay() -> None:
    verdict = run_differential(seed=TRIVIAL_SEED, two_d=Engine2D())
    probes = {aspect: 0 for aspect in verdict.aspects_covered}
    for aspect, _, _ in __import__("kernel.engine_seam", fromlist=["_battery"])._battery():
        probes[aspect] = probes.get(aspect, 0) + 1
    assert all(
        probes[aspect] > 1 for aspect in ("inventory", "progression", "permission", "persistence")
    )
    from kernel.overlay import load_overlay

    overlay = load_overlay(Path("content/seeds/first-forge/world_overlay.json"))
    assert len(overlay) == 12
    import kernel.engine_seam as seam

    coverage = cast(
        Callable[[Engine2D], object],
        next(
            probe
            for aspect, name, probe in seam._battery()
            if aspect == "coverage" and name == "all_overlay_rooms"
        ),
    )
    assert coverage(Engine2D()) == tuple((room, room) for room in sorted(overlay))


def test_new_permission_probe_calibration_detects_wrong_room() -> None:
    class WrongRoom(Engine2D):
        def room_of(self, position: object) -> str:
            return "grand_library"

    verdict = run_differential(two_d=WrongRoom())
    assert any(d.aspect == "permission" for d in verdict.divergences)
    assert run_differential(two_d=Engine2D()).divergences == ()


def test_new_persistence_probe_calibration_detects_wrong_room() -> None:
    class WrongRoom(Engine2D):
        def room_of(self, position: object) -> str:
            return "courtyard"

    verdict = run_differential(two_d=WrongRoom())
    assert any(d.aspect == "persistence" for d in verdict.divergences)
    assert run_differential(two_d=Engine2D()).divergences == ()


def test_movement_probe_drives_a_real_command_and_detects_wrong_room() -> None:
    """Movement must enter the Session and pass through the real command tick."""

    class WrongRoom(Engine2D):
        def room_of(self, position: object) -> str:
            return "courtyard"

    verdict = run_differential(two_d=WrongRoom())
    assert any(d.aspect == "movement" for d in verdict.divergences)
    assert run_differential(two_d=Engine2D()).divergences == ()


def test_the_differential_reports_a_planted_divergence() -> None:
    """Calibration. An instrument that cannot fail proves nothing, and this one guards a claim.

    Plant an engine whose non-spatial behaviour differs and confirm the harness NAMES it rather
    than passing. Without this the AGREED verdict above is unearned.
    """

    class LeakyEngine(Engine2DStub):
        """A 2D engine that lets position leak into a non-spatial answer."""

        def carry_limit(self) -> int:
            return 1  # Engine0D says 10; a limit that changes with the engine is a leak

    verdict = run_differential(seed=TRIVIAL_SEED, two_d=LeakyEngine())
    assert verdict.verdict == "DIVERGED"
    assert verdict.divergences, "a planted leak must be caught, or the AGREED verdict means nothing"
    assert all(isinstance(d, Divergence) for d in verdict.divergences)


def test_a_divergence_names_what_differed_and_under_which_engine() -> None:
    """A finding nobody can act on is not a finding. Name the command and both answers."""

    class LeakyEngine(Engine2DStub):
        def carry_limit(self) -> int:
            return 1

    verdict = run_differential(seed=TRIVIAL_SEED, two_d=LeakyEngine())
    rendered = " ".join(d.render() for d in verdict.divergences)
    assert "carry_limit" in rendered
    assert "0D" in rendered and "2D" in rendered


@pytest.mark.parametrize("aspect", ["inventory", "progression", "permission", "persistence"])
def test_the_battery_actually_exercises_every_aspect_C1_names(aspect: str) -> None:
    """C1 names four aspects by name. A battery missing one silently proves less than it claims."""
    verdict = run_differential(seed=TRIVIAL_SEED)
    assert aspect in verdict.aspects_covered, (
        f"C1 requires {aspect!r} in the battery; the differential does not exercise it"
    )


def test_an_aspect_with_no_MEASURED_probe_is_not_reported_as_covered() -> None:
    """The hole this instrument had, closed.

    Three probes were bound to APIs that did not exist. They were correctly recorded as unmeasured,
    and the coverage test passed anyway, because an aspect was listed the moment its probe was
    ATTEMPTED. Coverage over a probe that raised is coverage over nothing, which is exactly the
    defect shape this Workshop keeps finding in its own instruments.
    """
    import kernel.engine_seam as seam

    def broken_battery() -> list[tuple[str, str, object]]:
        def explode(_engine: object) -> object:
            raise RuntimeError("this probe cannot run")

        return [("inventory", "works", lambda e: 1), ("permission", "broken", explode)]

    original = seam._battery
    try:
        seam._battery = broken_battery
        verdict = seam.run_differential()
    finally:
        seam._battery = original

    assert "inventory" in verdict.aspects_covered
    assert "permission" not in verdict.aspects_covered, (
        "an aspect whose only probe raised was reported as covered"
    )
    assert verdict.unmeasured, "the failure must still be reported, never hidden"


def test_a_battery_that_measures_nothing_is_INCONCLUSIVE_not_AGREED() -> None:
    """UNVERIFIED is not PASS, applied to this instrument before anyone can round it up."""
    import kernel.engine_seam as seam

    original = seam._battery
    try:
        seam._battery = lambda: []
        assert seam.run_differential().verdict == "INCONCLUSIVE"
    finally:
        seam._battery = original


# --- the battery measures its own falsifiability -------------------------------------------------


def test_the_verdict_reports_how_many_probes_could_actually_fail() -> None:
    """WO-S4's finding, converted from a one-off audit into a permanent reading.

    The battery grew from 8 comparisons to 14 and satisfied a calibration bar written PER ASPECT.
    Most of the fourteen could not produce a divergence under any legal input, so the count rose
    and the evidence did not. A number that cannot be checked against its own strength invites
    exactly that, so the strength is now reported beside it.
    """
    verdict = run_differential(two_d=Engine2D())
    assert verdict.falsifiable, "a battery where nothing can fail is not evidence"
    assert len(verdict.falsifiable) <= verdict.commands_compared
    assert f"{len(verdict.falsifiable)} of them falsifiable" in verdict.render()


def test_a_probe_that_ignores_its_engine_is_not_counted_falsifiable() -> None:
    """The property, stated directly. `lambda e: pure_function(5)` can never diverge."""
    import kernel.engine_seam as seam

    falsifiable = set(seam.falsifiable_probes())
    # Progression is the clearest case and is structurally unfalsifiable by engine sabotage:
    # D1 puts it above the seam, so a progression probe that COULD diverge would be the leak.
    assert not any(entry.startswith("progression/") for entry in falsifiable), (
        "a progression probe that reacts to engine sabotage means position reached progression"
    )


def test_every_saboteur_names_a_room_the_world_actually_has() -> None:
    """Realism is load-bearing: an impossible state measures error handling, not sensitivity.

    Calibrated by getting it wrong. A saboteur returning a nonexistent room reported 5 probes
    falsifiable; two were reacting to a room the world does not contain, which no engine can
    produce. With legal rooms the honest answer is 3.
    """
    import kernel.engine_seam as seam

    rooms = set(seam._overlay_rooms())
    assert rooms, "the overlay must supply the sabotage rooms, never a literal"
    for saboteur in seam._saboteurs():
        reported = saboteur.room_of(saboteur.place("forge"))
        assert reported in rooms, f"saboteur emitted {reported!r}, which the Seed does not have"


def test_overlay_room_calibration_distinguishes_blueprints() -> None:
    """The overlay-room source must change when the Blueprint under test changes."""
    import kernel.engine_seam as seam

    first_forge = seam._overlay_rooms("first-forge")
    seam_probe = seam._overlay_rooms("seam-probe")
    assert first_forge != seam_probe, "the two Blueprint overlays are byte-identical"
    assert len(first_forge) == 12
    assert len(seam_probe) == 2


def test_seam_probe_runs_the_same_battery_as_first_forge() -> None:
    """Only the existing coverage probe changes its Blueprint input."""
    import kernel.engine_seam as seam

    first = run_differential("first-forge")
    probe = run_differential("seam-probe")
    assert first.verdict == "AGREED"
    assert probe.verdict == "AGREED"
    assert first.commands_compared == probe.commands_compared == len(seam._battery())

    assert seam._room_coverage(Engine0D(), "first-forge") != seam._room_coverage(
        Engine0D(), "seam-probe"
    )


def test_an_unfalsifiable_probe_is_still_run_and_still_counted_as_a_comparison() -> None:
    """Unfalsifiable is not worthless: those probes are regression guards, and they must not be
    quietly dropped to make the ratio look better."""
    verdict = run_differential(two_d=Engine2D())
    assert verdict.commands_compared > len(verdict.falsifiable)
    assert verdict.verdict == "AGREED"


def test_the_verdict_classifies_every_aspect_falsifiability() -> None:
    verdict = run_differential(two_d=Engine2D())
    seam = __import__("kernel.engine_seam", fromlist=["_battery"])
    expected = {aspect for aspect, _, _ in seam._battery()}
    assert {record.aspect for record in verdict.aspect_falsifiability} == expected


def test_structurally_unfalsifiable_aspects_name_their_reason() -> None:
    verdict = run_differential(two_d=Engine2D())
    records = {record.aspect: record for record in verdict.aspect_falsifiability}
    assert records["progression"].probes == ()
    assert "above the engine seam" in records["progression"].reason
    assert records["permission"].probes == ()
    assert "above the engine seam" in records["permission"].reason


def test_render_shows_each_aspect_falsifiability_record() -> None:
    rendered = run_differential(two_d=Engine2D()).render()
    assert "[falsifiability] progression: structurally unfalsifiable" in rendered
    assert "[falsifiability] inventory: falsifiable by" in rendered
