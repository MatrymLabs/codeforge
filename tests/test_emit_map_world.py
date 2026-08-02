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

from tools.emit_map_world import emit

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


@pytest.mark.parametrize("name", _GENERATED)
def test_each_generated_file_declares_it_is_generated(name: str):
    # Every emitter output must carry the GENERATED header, so a reader knows not to hand-edit it
    # (and that the emitter, not the file, is the source of truth).
    assert "GENERATED" in (_AETHRYN / f"{name}.yaml").read_text(encoding="utf-8").splitlines()[0]
