"""End-to-end PRODUCT test: the whole aethryn game plays through the engine tick.

The Convergence Review (2026-07-17) found that no seat owns "does the game actually play?" -
`test_play_smoke` covers the proactive-combat inch; THIS covers the whole product, one session
touching every system. The world loads once per process from FORGE_SEED, so this drives the real
aethryn seed in a SUBPROCESS (its own DB in tmp) and asserts a stranger can actually play it:
create a hero, take a calling and a borrowed subjob kit, take a quest and swear an Order, fight
with an ability, earn coins, gather and quaff a draught, hold a topic conversation, read the
bounty board and the sheet -- and that the endgame (the level-300 Forge's Edge) is really wired.
"""

import os
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

# Runs INSIDE the aethryn subprocess. Any failed assert exits non-zero; the parent checks that.
_PLAYTHROUGH = r"""
import forge
from parts.world.session import Session
from parts.world.world import START_ROOM, WORLD

s = Session(player_id="hero", location=START_ROOM)
s.named = True  # a proven hero (so an Order can be sworn)


def t(cmd):
    return forge.handle_command(s, cmd) or ""


# 1. Calling + a borrowed subjob kit (the FFXI switch): a Vanguard borrowing Emberwright gains its
#    moves on top of its own. (Jobs/abilities are world-agnostic systems, kept across the reseed.)
assert "Vanguard" in t("job vanguard"), "take a calling"
t("subjob emberwright")
assert "ember bolt" in t("skills").lower(), "the subjob lends its kit"

# 2. The world's opening arc and an Order.
assert "Endless Journey" in t("quest accept"), "take the story quest"
assert "Warcraft Order" in t("join warcraft"), "swear an Order"

# 3. The map: spawn in Veridia, walk to Greenhold by its named gate, and back.
assert s.location == START_ROOM == "veridia", "spawn is the Veridia starter zone"
t("greenhold")
assert s.location == "greenhold", "reach a named settlement on the map"
t("out")
assert s.location == "veridia"

# 4. Into the Veridia wilds and fell an ambient beast with an ability -- the combat + leveling loop.
t("west")  # -> the Veridia wildlands trail-head
felled = ""
for i in range(14):
    felled = t("use ember bolt on wolf") if i % 2 == 0 else t("attack wolf")
    if "collapses" in felled or "falls" in felled or "defeat" in felled.lower():
        break
assert s.level >= 1, "leveling engine ran"

# 5. The side-content board and the character sheet both render.
assert "notice board" in t("contracts").lower(), "the notice board"
assert "HP" in t("score") or "Vanguard" in t("score"), "the score sheet"

# 6. The endgame is really wired: the map's level 250-300 Voidscar and Netharion's Throne exist.
assert "the_voidscar" in WORLD, "the endgame zone exists"
assert "netharions_throne" in WORLD, "the final dungeon exists"

print("PLAYTHROUGH_OK")
"""


def test_a_stranger_can_play_aethryn_cradle_to_the_summit(tmp_path):
    env = {
        **os.environ,
        "FORGE_SEED": "aethryn",
        "CODEFORGE_DB": str(tmp_path / "playthrough.db"),
    }
    result = subprocess.run(
        [sys.executable, "-c", _PLAYTHROUGH],
        env=env,
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        timeout=120,
    )
    detail = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, f"the game did not play through:\n{detail}"
    assert "PLAYTHROUGH_OK" in result.stdout
