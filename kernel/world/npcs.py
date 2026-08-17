"""CARD: npcs -- characters who live in rooms and talk.

An NPC is world state: a location, keywords, and a dialogue cycle.
NPCs are born from the seed (seeds/first-forge/npcs.yaml).
MUD-IL shape: verb=talk, direct_object=npc.
"""

import contextlib

from kernel.shelf import target_disambig
from kernel.world.seed import BLUEPRINT_DIR, Npc, load_npcs
from kernel.world.session import sentence_case

NPCS: dict[str, Npc] = load_npcs(BLUEPRINT_DIR / "npcs.yaml")

# Room index: room label -> the npc labels standing in it. Presence is queried on EVERY world beat
# (aggression.menace and render both call npcs_in), so a full scan of NPCS per call is O(npcs) per
# command -- fine at hundreds of NPCs, fatal at tens of thousands (the world-generation scale). Two
# things can stale it: a change in NPC MEMBERSHIP (the procedural road adding foes at boot, or a
# test), detected by the size of NPCS and rebuilt only then; and ambient ROAMING relocating a few
# wanderers per beat (kernel.world.roaming), which updates the index in place via `apply_npc_moves`
# rather than rebuilding it -- a handful of dict ops, not an O(npcs) scan. Every steady-state lookup
# is a dict hit; a full rebuild happens on membership change, never per command.
_by_room: dict[str, list[str]] = {}
_indexed_len: int = -1


def _ensure_room_index() -> None:
    global _indexed_len  # noqa: PLW0602
    if _indexed_len == len(NPCS):
        return
    _rebuild_room_index()


def _rebuild_room_index() -> None:
    global _indexed_len  # noqa: PLW0603
    _by_room.clear()
    for nid, npc in NPCS.items():
        _by_room.setdefault(npc["location"], []).append(nid)
    _indexed_len = len(NPCS)


def reindex_npcs() -> None:
    """Force the room index to rebuild on the next lookup. Production builds NPCS once at boot and
    never changes membership, so it never needs this; call it only after mutating NPCS *in place*
    (adding, removing, or REPLACING an npc at an existing label) -- e.g. in a test -- because a
    same-size replacement is invisible to the automatic size check in _ensure_room_index."""
    global _indexed_len  # noqa: PLW0603
    _indexed_len = -1


def apply_npc_moves(moves: list[tuple[str, str, str]]) -> None:
    """Relocate NPCs in the room index in O(moves), not a full O(npcs) rebuild -- used by ambient
    roaming so a handful of wanderers changing rooms does not cost a ~140ms rebuild at world scale.

    Each move is (nid, old_room, new_room); membership is unchanged, so the size key stays valid.
    Apply this AFTER a beat's moves are decided (not mid-loop), which reproduces the previous
    rebuild-once-at-end-of-beat semantics exactly: mid-beat lookups still see pre-roam positions."""
    _ensure_room_index()
    for nid, old_room, new_room in moves:
        bucket = _by_room.get(old_room)
        if bucket is not None:
            with contextlib.suppress(ValueError):
                bucket.remove(nid)  # tolerate an already-absent id, stay correct
            if not bucket:
                del _by_room[old_room]
        _by_room.setdefault(new_room, []).append(nid)


def npcs_in(room_id: str) -> list[str]:
    """The npc labels currently PRESENT in a room: indexed members minus any that are dead and
    awaiting respawn (kernel.world.mortality). Presence is a query -- O(1) index lookup via a room
    index rebuilt only when NPC membership changes (see _ensure_room_index), then an O(k) aliveness
    filter over the few in this room. A felled mortal foe is absent until its respawn beat, at which
    point the aliveness check revives it in place, so this is also the lazy-respawn seam."""
    _ensure_room_index()
    members = _by_room.get(room_id)
    if not members:
        return []
    from kernel.world.climate import now  # noqa: PLC0415
    from kernel.world.mortality import is_dead  # noqa: PLC0415

    beat = now()
    return [nid for nid in members if not is_dead(NPCS[nid], beat)]


def trace_all_npcs(word: str, room_id: str) -> list[str]:
    """Every NPC id in this room whose keywords include `word`, in spawn order.

    The one source of truth for NPC keyword matching: `trace_npc` returns the first of these, and
    numbered-target disambiguation ("2-goblin") needs the whole list to strike the Nth of several.
    """
    return [nid for nid in npcs_in(room_id) if word in NPCS[nid]["keywords"]]


def trace_npc(word: str, room_id: str) -> str | None:
    """Match a player's word against keywords of NPCs in this room (the FIRST such NPC)."""
    matches = trace_all_npcs(word, room_id)
    return matches[0] if matches else None


def resolve_npc_target(token: str, room_id: str) -> str | None:
    """Resolve a possibly-numbered target token ("goblin", "2-goblin") to one NPC id in a room.

    Splits any 1-based ordinal off the token (via the target_disambig shelf part), filters the room
    to NPCs sharing the parsed name, then picks the Nth. A bare name is ordinal 1, so behavior is
    identical to `trace_npc` for the common case. Returns None when nothing matches the name; raises
    target_disambig.TargetError when the ordinal overshoots the count or the token is malformed.
    """
    ordinal, name = target_disambig.parse_target(token)
    matches = trace_all_npcs(name, room_id)
    if not matches:
        return None
    return target_disambig.pick(matches, ordinal)


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
