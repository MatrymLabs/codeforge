"""CARD: npcs -- characters who live in rooms and talk.

An NPC is world state: a location, keywords, and a dialogue cycle.
MUD-IL shape: verb=talk, direct_object=npc.
Dialogue advances one line per talk and loops -- deterministic,
testable, and enough personality for a first conversation.
"""

from typing import TypedDict


class Npc(TypedDict):
    """The shape every NPC must have."""

    name: str
    keywords: list[str]
    location: str  # room label
    dialogue: list[str]
    next_line: int


NPCS: dict[str, Npc] = {
    "librarian": {
        "name": "the librarian",
        "keywords": ["librarian", "keeper", "woman"],
        "location": "library",
        "dialogue": [
            '"Welcome to the old library. Mind the dust -- it remembers things."',
            '"That oak door? Sealed for years. A copper key went missing ages ago..."',
            '"If you ever stand inside the Archive, tell no one what you read."',
        ],
        "next_line": 0,
    },
}


def npcs_in(room_id: str) -> list[str]:
    """All npc labels currently in a room. Presence is a query."""
    return [nid for nid, npc in NPCS.items() if npc["location"] == room_id]


def find_npc(word: str, room_id: str) -> str | None:
    """Match a player's word against keywords of NPCs in this room."""
    for nid in npcs_in(room_id):
        if word in NPCS[nid]["keywords"]:
            return nid
    return None


def talk(word: str, room_id: str) -> str:
    nid = find_npc(word, room_id)
    if nid is None:
        return "There is no one like that here."
    npc = NPCS[nid]
    line = npc["dialogue"][npc["next_line"]]
    npc["next_line"] = (npc["next_line"] + 1) % len(npc["dialogue"])
    return f"{npc['name'].capitalize()} says: {line}"


def room_npcs_text(room_id: str) -> str:
    """Extra line(s) for room rendering. Empty string if nobody here."""
    here = npcs_in(room_id)
    if not here:
        return ""
    return "\n".join(f"{NPCS[nid]['name'].capitalize()} is here." for nid in here)
