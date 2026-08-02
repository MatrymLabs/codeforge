"""CARD: wardens -- name each dungeon's deep boss for its dungeon, so the whole web names one foe.

The delve generator gives every deep boss a random forge-name (Grathok the Shadow Warden), but the
rest of the content web already speaks of a specific keeper: the town rumour warns of a terror, the
depths inscription reads 'here we bound its keeper', the relic is torn from the deep terror of the
dungeon. This makes the boss BE that keeper: it renames each `<room>_deep_boss` to a titled warden
of its own dungeon (the Warden of The Black Hollow), so rumour, inscription, relic, and foe all name
one individual. Nothing about its stats or tier changes -- only its identity, made coherent.

`name_wardens(dungeons, npcs)` mutates the deep bosses in place and returns how many it renamed.
Deterministic: the same dungeon always crowns the same warden, reproducible like the generators.
"""

from __future__ import annotations

from typing import Any

from kernel.world.relics import iconic_word
from kernel.world.seed import Npc

DEEP_BOSS_SUFFIX = (
    "_deep_boss"  # the delve generator names each dungeon's deep boss `<room>_deep_boss`
)

# The title a warden bears, chosen by dungeon index so the depths vary. Each reads as the keeper the
# rumour and the inscription already speak of.
_TITLES: tuple[str, ...] = ("Warden", "Keeper", "Devourer", "Sentinel", "Herald", "Scourge")


def name_wardens(dungeons: list[dict[str, Any]], npcs: dict[str, Npc]) -> int:
    """Rename each dungeon's deep boss to a titled warden of that dungeon, and re-key its keywords
    so a player can name it by title or dungeon. Mutates in place; returns the number renamed.
    A dungeon whose deep boss is absent is skipped. Deterministic."""
    renamed = 0
    for idx, dungeon in enumerate(dungeons):
        room = str(dungeon["room"])
        boss = npcs.get(f"{room}{DEEP_BOSS_SUFFIX}")
        if boss is None:
            continue
        name = str(dungeon["name"])
        title = _TITLES[idx % len(_TITLES)]
        display = f"the {title} of {name}"
        core = iconic_word(room)
        boss["name"] = display
        boss["keywords"] = list(
            dict.fromkeys(
                [title.lower(), core.lower(), "warden", "boss", *boss.get("keywords", [])]
            )
        )
        boss["dialogue"] = [f'{display} rises from the dark. "None pass me."']
        renamed += 1
    return renamed
