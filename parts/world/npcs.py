"""CARD: npcs -- characters who live in rooms and talk.

An NPC is world state: a location, keywords, and a dialogue cycle.
NPCs are born from the seed (seeds/first-forge/npcs.yaml).
MUD-IL shape: verb=talk, direct_object=npc.
"""

from parts.world.seed import SEED_DIR, Npc, load_npcs
from parts.world.session import sentence_case

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
    return f"{sentence_case(npc['name'])} says: {line}"


def ask(word: str, topic: str, room_id: str) -> str:
    """`ask <npc> about <topic>`: a topic-based conversation. A bare topic lists what the NPC can
    discuss; an unknown topic says so and lists the options. Turns a cycling dialogue into a real
    exchange, without breaking `talk` (NPCs with no topics simply have nothing to ask about)."""
    nid = trace_npc(word, room_id)
    if nid is None:
        return "There is no one like that here."
    npc = NPCS[nid]
    name = sentence_case(npc["name"])
    topics = npc.get("topics")
    if not topics:
        return f"{name} has nothing more to discuss. (Try TALK.)"
    if not topic.strip():
        return f"You could ask {name} about: " + ", ".join(sorted(topics)) + "."
    key = topic.strip().lower()
    lines = topics.get(key) or next((ls for t, ls in topics.items() if key in t or t in key), None)
    if lines is None:
        options = ", ".join(sorted(topics))
        return f"{name} has nothing to say about that. Ask about: {options}."
    body = "\n".join(lines)
    return f"{name} says: {body}"


def _presence_line(nid: str) -> str:
    """One room-render line for an NPC. An aggressive foe is telegraphed so a strike on
    the world beat is never a surprise: the room render is the player's only danger rubric."""
    npc = NPCS[nid]
    hostile = ", and looks hostile" if npc.get("aggressive") else ""
    return f"{sentence_case(npc['name'])} is here{hostile}."


def room_npcs_text(room_id: str) -> str:
    """Extra line(s) for room rendering. Empty string if nobody here."""
    here = npcs_in(room_id)
    if not here:
        return ""
    return "\n".join(_presence_line(nid) for nid in here)
