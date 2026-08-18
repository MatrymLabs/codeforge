"""Every committed world_overlay.json must still regenerate from its own rooms.yaml.

An overlay is DERIVED data: `kernel.overlay.generate_overlay` produces it from the Blueprint's
rooms. Derived data that is also committed has exactly one failure mode, and it is silent. Edit
rooms.yaml, forget to regenerate, and the overlay is stale from that moment on. Nothing raises,
nothing turns red, and the differential keeps agreeing because both engines read the same stale
file.

The existing differential suite asserts the generator is DETERMINISTIC -- generate twice, get the
same bytes. That is a property of the generator. This asserts a property of the REPOSITORY: what
is committed is what the current rooms.yaml produces. The two questions look alike and only one of
them catches a room added last week.

Same defect class as shelf-drift, which had to be discovered by a CI job going red rather than by
anyone deciding to check.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest

from kernel.overlay import generate_overlay

BLUEPRINTS = Path(__file__).resolve().parent.parent / "content" / "blueprints"


def _blueprints_with_overlays() -> list[str]:
    """Every Blueprint that commits an overlay. Discovered, never listed.

    A hardcoded list is how a new Blueprint joins the repository without joining this gate, and a
    gate that silently stops covering things is worse than one that never covered them.
    """
    if not BLUEPRINTS.is_dir():
        return []
    return sorted(
        p.parent.name
        for p in BLUEPRINTS.glob("*/world_overlay.json")
        if (p.parent / "rooms.yaml").is_file()
    )


def test_at_least_one_blueprint_commits_an_overlay() -> None:
    """The discovery above must actually find something, or every test below passes vacuously."""
    assert _blueprints_with_overlays(), "no Blueprint commits an overlay; this suite proves nothing"


@pytest.mark.parametrize("seed", _blueprints_with_overlays())
def test_the_committed_overlay_still_regenerates_from_rooms(seed: str) -> None:
    """The committed bytes must equal what today's rooms.yaml produces."""
    committed = BLUEPRINTS / seed / "world_overlay.json"
    rooms = BLUEPRINTS / seed / "rooms.yaml"

    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "world_overlay.json"
        generate_overlay(rooms, fresh)
        expected = hashlib.sha256(fresh.read_bytes()).hexdigest()

    actual = hashlib.sha256(committed.read_bytes()).hexdigest()
    assert actual == expected, (
        f"{seed}/world_overlay.json is STALE: it no longer matches what rooms.yaml produces.\n"
        f"  committed   {actual[:16]}\n"
        f"  regenerated {expected[:16]}\n"
        f"Regenerate it; do not hand-edit an overlay."
    )


def test_the_drift_check_would_catch_a_stale_overlay(tmp_path: Path) -> None:
    """The calibration, and the half that matters: a stale overlay must FAIL this comparison.

    A check that only ever runs against correct data has never been shown to notice incorrect
    data. Here the staleness is manufactured rather than waited for.
    """
    seeds = _blueprints_with_overlays()
    assert seeds, "nothing to calibrate against"
    rooms = BLUEPRINTS / seeds[0] / "rooms.yaml"

    fresh = tmp_path / "world_overlay.json"
    generate_overlay(rooms, fresh)
    good = hashlib.sha256(fresh.read_bytes()).hexdigest()

    stale = fresh.read_bytes().replace(b'"x": 0', b'"x": 999', 1)
    assert stale != fresh.read_bytes(), "the fixture did not actually change; calibration is void"
    assert hashlib.sha256(stale).hexdigest() != good
