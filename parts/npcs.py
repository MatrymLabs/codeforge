"""CARD: npcs -- characters who live in rooms and talk.

An NPC is world state: a location, keywords, and a dialogue cycle.
NPCs are born from the seed (seeds/first-forge/npcs.yaml).
MUD-IL shape: verb=talk, direct_object=npc.
"""

from parts.seed import SEED_DIR, Npc, load_npcs

NPCS: dict[str, Npc] = load_npcs(SEED_DIR / "npcs.yaml")


def npcs_in(room_id: str) -> list[str]:
    """All npc labels currently in a room. Presence is a query."""
    return [nid for nid, npc in NPCS.items() if npc["location"] == room_id]


def trace_npc(word: str, room_id: str) -> str | None:
    """Match a player's word against keywords of NPCs in this room."""
    for nid in npcs_in(room_id):
        if word in NPCS[nid]["keywords"]:
            return nid
    return None


def talk(word: str, room_id: str) -> str:
    nid = trace_npc(word, room_id)
    if nid is None:
        return "There is no one like that here."
    npc = NPCS[nid]
    line = npc["dialogue"][npc["next_line"]]
    npc["next_line"] = (npc["next_line"] + 1) % len(npc["dialogue"])
    return f"{npc['name'].capitalize()} says: {line}"


def _presence_line(nid: str) -> str:
    """One room-render line for an NPC. An aggressive foe is telegraphed so a strike on
    the world beat is never a surprise: the room render is the player's only danger rubric."""
    npc = NPCS[nid]
    hostile = ", and looks hostile" if npc.get("aggressive") else ""
    return f"{npc['name'].capitalize()} is here{hostile}."


def room_npcs_text(room_id: str) -> str:
    """Extra line(s) for room rendering. Empty string if nobody here."""
    here = npcs_in(room_id)
    if not here:
        return ""
    return "\n".join(_presence_line(nid) for nid in here)
