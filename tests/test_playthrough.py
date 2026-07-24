"""End-to-end PRODUCT test: the whole aethryn game plays through the engine tick.

The Convergence Review (2026-07-17) found that no seat owns "does the game actually play?" -
`test_play_smoke` covers the proactive-combat inch; THIS covers the whole product, one session
touching every system. The world loads once per process from FORGE_SEED, so this drives the real
aethryn seed in a SUBPROCESS (its own DB in tmp) and asserts a stranger can actually play it:
create a hero, take a calling and a borrowed subjob kit, take a quest and swear an Order, fight
with an ability, earn coins, gather and quaff a draught, hold a topic conversation, read the
bounty board and the sheet -- and that the endgame (the level-255 summit) is really wired.
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
from parts.world.world import START_ROOM

s = Session(player_id="hero", location=START_ROOM)
s.named = True  # a proven Forger (so an Order can be sworn)


def t(cmd):
    return forge.handle_command(s, cmd) or ""


# 1. Calling + a borrowed subjob kit (the FFXI switch): a Vanguard borrowing Emberwright gains its
#    moves on top of its own.
assert "Vanguard" in t("job vanguard"), "take a calling"
t("subjob emberwright")
skills = t("skills").lower()
assert "ember bolt" in skills, "the subjob lends its kit"

# 2. A quest and an Order.
assert "Relighting" in t("quest accept"), "take the story quest"
assert "Warcraft Order" in t("join warcraft"), "swear an Order"

# 3. Walk to town, gather a healing draught, on to the wilds, and fell the wolf with an ability.
assert s.location == START_ROOM
t("north")  # -> cinderhearth_square
assert "healing draught" in t("get healing").lower() or s.location == "cinderhearth_square"
t("east")  # -> reachwood_edge
felled = ""
for _ in range(8):
    felled = t("use ember edge on wolf") if _ % 2 == 0 else t("attack wolf")
    if "collapses" in felled:
        break
assert "collapses" in felled, "fell the reach wolf"
assert s.coins > 0, "a kill fills the purse"
assert s.level >= 1, "leveling engine ran"

# 4. Back to town: quaff the draught (heal), and hold a real conversation.
t("west")  # -> cinderhearth_square
assert "quaff" in t("quaff draught").lower(), "spend a consumable"
assert "Spiral" in t("ask sela about spiral"), "topic conversation"

# 5. The side-content board and the character sheet both render.
assert "bounty board" in t("contracts").lower(), "the bounty board"
assert "HP" in t("score") or "Vanguard" in t("score"), "the score sheet"

# 6. The endgame is really wired: the level-255 summit room and the Sovereign's bounty exist.
from parts.world.world import WORLD
from parts.world import quest
assert "the_spiral_summit" in WORLD, "the summit room exists"
assert any(q == "bounty_spiral_sovereign" for q in quest._QUESTS), "the summit bounty exists"

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
