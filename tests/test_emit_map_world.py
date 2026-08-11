"""Drift guard for tools/emit_map_world.py -- the map emitter IS the source of truth.

The seven aethryn seed files (rooms, npcs, zones, wildlands, settlements, dungeons, waystones) are
GENERATED from the emitter's in-script world data, but they have been hand-tuned in places (a
lived-in wander on the starter towns; telegraphed specials, raid-gating, and regional armour drops
on the anchor bosses). Those hand-edits are now reproduced BY the emitter, so a regen is
non-destructive. This test pins that: emitting to a temp dir must reproduce every committed file
byte for byte. It fails the moment a generated file is hand-edited without teaching the emitter, or
the emitter is changed without regenerating -- catching the exact hazard that a blind regen once hit
(it silently wiped boss drops and specials).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.emit_map_world import _REV, LINKS, MapCollision, _wire_hubs, emit

_AETHRYN = Path(__file__).resolve().parent.parent / "content" / "seeds" / "aethryn"
_GENERATED = ("rooms", "npcs", "zones", "wildlands", "settlements", "dungeons", "waystones")


def test_the_emitter_reproduces_every_committed_seed_file(tmp_path: Path):
    emit(tmp_path)
    for name in _GENERATED:
        fresh = (tmp_path / f"{name}.yaml").read_text(encoding="utf-8")
        committed = (_AETHRYN / f"{name}.yaml").read_text(encoding="utf-8")
        assert fresh == committed, (
            f"{name}.yaml has drifted from the emitter. The committed file was hand-edited without "
            f"teaching tools/emit_map_world.py, or the emitter changed without a regen. Update the "
            f"emitter (its hand-tuning tables) so a regen is non-destructive, then rerun it."
        )


def test_wire_hubs_binds_a_route_in_both_directions():
    # ACCEPTANCE: a route is only wired if the player can walk it and walk back.
    bound = _wire_hubs(
        [("alpha", "beta", "east", "road")], {"alpha": "alpha", "beta": "beta"}, ["alpha", "beta"]
    )
    assert bound["alpha"]["east"] == "beta"
    assert bound["beta"]["west"] == "alpha"


def test_wire_hubs_refuses_two_routes_claiming_one_heading():
    # REFUSAL: the defect that stranded four Aethryn zones. A plain assignment let the second
    # writer win, so the loser kept its forward exit and silently lost its return path.
    with pytest.raises(MapCollision) as caught:
        _wire_hubs(
            [("alpha", "beta", "east", "road"), ("gamma", "beta", "east", "sea")],
            {"alpha": "alpha", "beta": "beta", "gamma": "gamma"},
            ["alpha", "beta", "gamma"],
        )
    # It must name BOTH claimants, or it tells you a slot is contested without saying by what.
    assert "beta 'west'" in str(caught.value)
    assert "alpha <-> beta (east)" in str(caught.value)
    assert "gamma <-> beta (east)" in str(caught.value)


def test_the_shipped_map_has_no_colliding_headings():
    # The real map, not a fixture: every inter-zone route keeps its return path.
    hubs = {zid: zid for a, b, _d, _r in LINKS for zid in (a, b)}
    bound = _wire_hubs(LINKS, hubs, list(hubs))
    for a, b, direction, _route in LINKS:
        assert bound[a][direction] == b
        assert bound[b][_REV[direction]] == a


@pytest.mark.parametrize("name", _GENERATED)
def test_each_generated_file_declares_it_is_generated(name: str):
    # Every emitter output must carry the GENERATED header, so a reader knows not to hand-edit it
    # (and that the emitter, not the file, is the source of truth).
    assert "GENERATED" in (_AETHRYN / f"{name}.yaml").read_text(encoding="utf-8").splitlines()[0]
