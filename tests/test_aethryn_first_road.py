"""The authored Veridia starter arc must play through the real Aethryn command path."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


_REPO = Path(__file__).resolve().parent.parent


_FIRST_ROAD = r"""
from forge import handle_command
from kernel.world.jobs import bind_calling
from kernel.world.session import SESSIONS, Session
from kernel.world.world import START_ROOM

s = Session(player_id="first_road_hero", location=START_ROOM, named=True)
SESSIONS[s.player_id] = s
bind_calling(s, "vanguard")


def play(command: str) -> str:
    return handle_command(s, command) or ""


assert "The First Road" in play("quest veridia_first_road accept")
assert s.location == "veridia"
out = play("wayhouse")
assert s.location == "veridia_wayhouse" and "Wayfarer's House" in out
out = play("north")
assert s.location == "veridia_maproom" and "Cradle Map Room" in out
assert "compass" in play("take compass").lower()
out = play("south")
assert s.location == "veridia_wayhouse" and "The Wayfarer's House" in out
out = play("out")
assert s.location == "veridia" and "Veridia" in out

# The named exits are the same exits exposed to a MUD client; no quest-only teleport is used.
play("go greenhold")
play("go square")
assert s.location == "greenhold_market"
assert "Greenhold's water" in play("look") or "Greenhold's water" in play("quest veridia_first_road")
play("out")
play("out")
play("go elderwatch")
play("go gate")
assert s.location == "elderwatch_yard"
play("go up")
assert s.location == "elderwatch_tower"
assert "Elderwatch's tower" in play("quest veridia_first_road")

play("go down")
play("out")
play("out")
play("go riverbend")
play("go landing")
play("go east")
assert s.location == "riverbend_reeds"
assert "river crossing" in play("quest veridia_first_road")
play("go west")
play("go north")
play("go down")
assert s.location == "riverbend_weirvault"

# Combat is intentionally real. A miss, daze, or training-ground defeat may consume a beat; the
# bounded retry proves the player can eventually complete the authored starter encounter without
# test-only state injection.
completed = False
for _ in range(80):
    out = play("attack lurker")
    if "The first road is yours" in out:
        completed = True
        break
assert completed, play("quest veridia_first_road")
assert "The first road is yours" in play("quest veridia_first_road")
print("FIRST_ROAD_OK")
"""


def test_aethryn_first_road_is_playable_from_spawn_to_riverbend(tmp_path: Path) -> None:
    """Run the authored arc in a clean child process so Seed imports cannot pollute other tests."""
    env = {
        **os.environ,
        "FORGE_SEED": "aethryn",
        "CODEFORGE_DB": str(tmp_path / "first-road.db"),
    }
    result = subprocess.run(
        [sys.executable, "-c", _FIRST_ROAD],
        cwd=str(_REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    detail = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, f"the authored starter arc did not play through:\n{detail}"
    assert "FIRST_ROAD_OK" in result.stdout
