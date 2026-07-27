"""CARD: npcs -- characters who live in rooms and talk.

An NPC is world state: a location, keywords, and a dialogue cycle.
NPCs are born from the seed (seeds/first-forge/npcs.yaml).
MUD-IL shape: verb=talk, direct_object=npc.
"""

from parts.world.seed import SEED_DIR, Npc, load_npcs
from parts.world.session import sentence_case

NPCS: dict[str, Npc] = load_npcs(SEED_DIR / "npcs.yaml")

# Room index: room label -> the npc labels standing in it. Presence is queried on EVERY world beat
# (aggression.menace and render both call npcs_in), so a full scan of NPCS per call is O(npcs) per
# command -- fine at hundreds of NPCs, fatal at tens of thousands (the world-generation scale). NPCs
# never relocate after creation (only their runtime fields -- hp_now, burn -- change; felled foes
# reassemble in place), so the ONLY event that can stale this index is a change in NPC MEMBERSHIP:
# the procedural road adding foes at boot, or a test adding one. We detect that by the size of NPCS
# and rebuild only then; every steady-state lookup is a dict hit. Rebuilding is O(npcs), but happens
# on a membership change, not per command. (Location is never mutated, so len is a sufficient key.)
_by_room: dict[str, list[str]] = {}
_indexed_len: int = -1


def _ensure_room_index() -> None:
    global _indexed_len
    if _indexed_len == len(NPCS):
        return
    _rebuild_room_index()


def _rebuild_room_index() -> None:
    global _indexed_len
    _by_room.clear()
    for nid, npc in NPCS.items():
        _by_room.setdefault(npc["location"], []).append(nid)
    _indexed_len = len(NPCS)


def reindex_npcs() -> None:
    """Force the room index to rebuild on the next lookup. Production builds NPCS once at boot and
    never changes membership, so it never needs this; call it only after mutating NPCS *in place*
    (adding, removing, or REPLACING an npc at an existing label) -- e.g. in a test -- because a
    same-size replacement is invisible to the automatic size check in _ensure_room_index."""
    global _indexed_len
    _indexed_len = -1


def npcs_in(room_id: str) -> list[str]:
    """All npc labels currently in a room. Presence is a query -- O(1) via a room index rebuilt only
    when NPC membership changes (see _ensure_room_index), not a scan of every NPC on every call."""
    _ensure_room_index()
    return list(_by_room.get(room_id, []))


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
