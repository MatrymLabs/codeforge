"""Test twin for kernel/domains/hosted_world.py -- install a generated region as a bootable World
Package (North Star #5, the engine side).

Acceptance: a generated journey installs as a real seed under content/seeds/<name>/ with a rooms +
quest + a world.yaml MANIFEST, and it passes the engine's OWN gates -- the manifest is valid
(describe_world) and the declared spawn is the seed's first room (check_world), because the Linker
now emits the start room first. Verdict HOSTABLE.

Refusal (fail loud): a region that does not link is REFUSED; an unslug-able region name fails loud.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.domains.game_linker import GameSpec, RoomSpec
from kernel.domains.hosted_world import (
    HOSTABLE,
    REFUSED,
    HostedWorldError,
    install_world,
)
from kernel.domains.journey import journey_region
from kernel.world.seed import load_rooms
from kernel.world.world_manifest import check_world, describe_world


def test_a_generated_journey_installs_as_a_hostable_world(tmp_path: Path) -> None:
    spec = journey_region("veridia", ["greenhold", "riverside", "summit"])
    world = install_world(spec, tmp_path)
    assert world.verdict == HOSTABLE and world.ok is True
    assert world.seed_name == "veridia" and world.start_room == "trailhead"
    seed_dir = Path(world.seed_dir)
    for f in ("rooms.yaml", "quest.yaml", "world.yaml"):
        assert (seed_dir / f).exists()
    # The engine's own gates agree: valid manifest, and the declared spawn IS the seed's first room.
    assert describe_world("veridia", root=tmp_path).start_room == "trailhead"
    assert check_world("veridia", root=tmp_path) == []


def test_the_seed_spawns_at_the_declared_start(tmp_path: Path) -> None:
    # A start that is NOT alphabetically first must still be the seed's spawn (start-first emit).
    spec = journey_region("zephyr", ["alpha_camp", "beacon"])  # start "trailhead" sorts last
    install_world(spec, tmp_path)
    rooms = load_rooms(Path(tmp_path) / "content" / "blueprints" / "zephyr" / "rooms.yaml")
    assert next(iter(rooms)) == "trailhead"  # the engine spawns here (world.START_ROOM)


def test_a_region_slug_becomes_a_valid_world_id(tmp_path: Path) -> None:
    # An underscored region name is slugged to a lowercase-hyphenated world_id the manifest accepts.
    world = install_world(journey_region("iron_hold", ["gate"]), tmp_path)
    assert world.verdict == HOSTABLE and world.seed_name == "iron-hold"


# --- refusal: fail loud --------------------------------------------------------------------------


def test_a_region_that_does_not_link_is_refused(tmp_path: Path) -> None:
    broken = GameSpec(
        region="broken", start="gate", rooms=(RoomSpec(label="gate", exits={"north": "nowhere"}),)
    )
    world = install_world(broken, tmp_path)
    assert world.verdict == REFUSED and any("did not link" in p for p in world.problems)


def test_an_unslugable_region_name_fails_loud(tmp_path: Path) -> None:
    spec = GameSpec(region="!!!", start="gate", rooms=(RoomSpec(label="gate"),))
    with pytest.raises(HostedWorldError):
        install_world(spec, tmp_path)


def test_a_bad_world_id_is_unhostable(tmp_path: Path) -> None:
    from kernel.domains.hosted_world import UNHOSTABLE  # noqa: PLC0415

    # An explicit seed_name that is not a valid world_id (uppercase/underscore) is caught by the
    # engine's own manifest gate -> UNHOSTABLE, with the problem surfaced (never a false HOSTABLE).
    world = install_world(journey_region("veridia", ["gate"]), tmp_path, seed_name="Bad_ID")
    assert world.verdict == UNHOSTABLE and world.problems
