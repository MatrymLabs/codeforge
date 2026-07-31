"""CARD: gmcp -- structured out-of-band state frames for GMCP-aware clients.

GMCP (Generic MUD Communication Protocol) rides Telnet subnegotiation: `IAC SB GMCP
<package> <json> IAC SE`. It lets a capable client read state as data (a health bar, a
minimap) instead of scraping the text projection. This card is PURE: it builds frames and
reports and reads negotiation replies; the gateway owns the socket and decides when to send.

Two laws hold here. State is canonical and text is a projection (architecture law 1), so a
GMCP report is just another read-only projection of the same `Session` the renderer reads --
never a second source of truth. And derive-don't-store (law 3): vitals come through
`sheet_from_session`, the same aggregator the score sheet uses, so a client never sees a
number the game itself would not compute.
"""

from __future__ import annotations

import json

from parts.shelf.telnet_codec import IAC, SB, SE, escape_iac, read_negotiation
from parts.world.character_view import sheet_from_session
from parts.world.session import Session
from parts.world.world import WORLD

# GMCP is Telnet option 201 (0xC9). The IAC/SB/SE bytes and the escape/negotiation codec come from
# parts.shelf.telnet_codec, the one home for the Telnet wire; this card only knows the GMCP option
# and how to shape a GMCP payload. `escape_iac` is re-exported so consumers keep importing it here.
GMCP_OPT = 201

__all__ = [
    "GMCP_OPT",
    "enables_gmcp",
    "escape_iac",
    "gmcp_frame",
    "items_report",
    "quest_report",
    "resists_report",
    "room_report",
    "skills_report",
    "target_report",
    "vitals_report",
]


def gmcp_frame(package: str, data: object) -> bytes:
    """Frame one GMCP message as raw bytes ready to write to a socket.

    `IAC SB GMCP <package> <compact-json> IAC SE`. `data` is JSON-encoded; pass `None` for a
    body-less package (the space and payload are omitted).
    """
    if not package:
        raise ValueError("GMCP package name must not be empty")
    body = package if data is None else f"{package} {json.dumps(data, separators=(',', ':'))}"
    return bytes([IAC, SB, GMCP_OPT]) + escape_iac(body.encode("utf-8")) + bytes([IAC, SE])


def enables_gmcp(data: bytes) -> bool | None:
    """Read a client's negotiation reply for GMCP support (the GMCP-specific read_negotiation).

    True  -> the client enabled GMCP (`IAC DO GMCP` or `IAC WILL GMCP`): safe to push frames.
    False -> the client refused (`IAC DONT GMCP` or `IAC WONT GMCP`): stop pushing.
    None  -> no GMCP negotiation in this chunk: leave the current decision unchanged.

    A raw `nc` never sends any of these, so it never flips to True: it stays a plain-text client
    and receives no binary GMCP noise.
    """
    return read_negotiation(data, GMCP_OPT)


def vitals_report(session: Session) -> dict[str, int] | None:
    """A Char.Vitals payload from live state, or None before the player has a calling.

    Derived through `sheet_from_session` (the score sheet's own aggregator), so these numbers
    always match what the game would render. `nextlevel` is -1 at the level cap (no next
    threshold), which a client reads as "maxed" without a null.
    """
    sheet = sheet_from_session(session)
    if sheet is None:
        return None
    hp_cur, hp_max = sheet.hp
    mp_cur, mp_max = sheet.mp if sheet.mp is not None else (0, 0)  # a job with no MP reads as 0/0
    return {
        "hp": hp_cur,
        "maxhp": hp_max,
        "mp": mp_cur,
        "maxmp": mp_max,
        "level": sheet.player_level,
        "xp": sheet.current_xp,
        "nextlevel": sheet.next_level_xp if sheet.next_level_xp is not None else -1,
    }


def room_report(session: Session) -> dict[str, object]:
    """A Room.Info payload for the session's current location, from world data.

    `num` is the room's frozen label (the dict key); `name` and `exits` come straight from the
    seeded room. `area` is the label of the zone that owns the room, when one does, so a client can
    colour its map by region -- additive and optional: a room in no zone carries no `area`, and an
    old client ignores it. An unknown location renders honestly rather than raising: the player is
    somewhere the world does not describe, and the client should see that, not a crash.
    """
    from parts.world.zones import zone_of

    room = WORLD.get(session.location)
    if room is None:
        return {"num": session.location, "name": "(nowhere)", "exits": {}}
    report: dict[str, object] = {
        "num": session.location,
        "name": room["name"],
        "exits": dict(room["exits"]),
    }
    area = zone_of(session.location)
    if area is not None:
        report["area"] = area
    return report


def target_report(session: Session) -> dict[str, object] | None:
    """A Char.Target payload for the foe the player is fighting, or None when not in combat.

    Combat here resolves per-strike, so there is no stored "current target"; the honest signal is
    a foe in the player's own room that is engaged -- either an aggressor hounding them
    (`aggro_beats`) or one already wounded (`hp_now < hp`). A non-combatant (a shopkeeper, no `hp`)
    is never a target. Read-only projection of live NPC state, like the room and vitals reports.
    """
    from parts.world.npcs import NPCS, npcs_in
    from parts.world.session import sentence_case

    for nid in npcs_in(session.location):
        npc = NPCS[nid]
        hp = npc.get("hp") or 0
        if hp <= 0:  # a non-combatant (shopkeeper, teacher) has no health bar to show
            continue
        hp_now = npc.get("hp_now", hp)
        if nid in session.aggro_beats or hp_now < hp:  # engaged: hounding us, or already bloodied
            report: dict[str, object] = {
                "name": sentence_case(npc["name"]),
                "hp": hp_now,
                "maxhp": hp,
            }
            # The foe's elemental profile, so a client (its co-pilot) can advise on element choice
            # without the player dying to learn it. Both keys are additive and optional: an untyped
            # foe that resists nothing carries neither, and an old client ignores what it can't use.
            attack = npc.get("attack_element")
            if attack:
                report["element"] = attack
            resists = {c: lvl for c, lvl in npc.get("resistances", {}).items() if lvl != "Normal"}
            if resists:
                report["resists"] = resists
            return report
    return None


def quest_report(session: Session) -> dict[str, str] | None:
    """A Char.Quest payload for the player's foremost unfinished story quest, or None when the
    authored arcs are all done. Delegates to the quest card's own read-only projection."""
    from parts.world.quest import active_quest

    return active_quest(session)


def party_report(session: Session) -> dict[str, object] | None:
    """A Char.Party payload: the player's fellowship as {members: [names], leader, size}, or None
    when solo (an empty frame then clears the client's party panel, like Char.Target). Read-only
    projection of the party registry; the leader is always members[0]."""
    from parts.world.party import party_of, roster_frame

    band = party_of(session.player_id)
    if band is None:
        return None
    return roster_frame(band)


def guild_report(session: Session) -> dict[str, str] | None:
    """A Char.Guild payload: the player's guild as {name, rank}, or None when guildless (an empty
    frame clears the client's guild panel). Read-only projection of the persisted guild columns."""
    from parts.world.session import display_name

    if not session.guild:
        return None
    return {"name": display_name(session.guild), "rank": session.guild_rank}


def mail_report(session: Session) -> dict[str, int] | None:
    """A Char.Mail payload: {unread, total} for the hero's inbox, or None when the inbox is empty
    (an empty frame then clears the client's mail badge). A named hero only; an unnamed connection
    at the login desk has no inbox to read."""
    from parts.world.mail_store import count, unread_count

    if not session.named:
        return None
    total = count(session.player_id)
    if total == 0:
        return None
    return {"unread": unread_count(session.player_id), "total": total}


def friends_report(session: Session) -> dict[str, object] | None:
    """A Char.Friends payload: {online, total, names} for the hero's friends who are logged in right
    now, or None when the list is empty. Read-only projection of session.friends against who is
    seated (SESSIONS); names are the online friends, so a client can show who is around."""
    from parts.world.session import SESSIONS, display_name

    if not session.friends:
        return None
    online = [f for f in session.friends if f in SESSIONS]
    return {
        "online": len(online),
        "total": len(session.friends),
        "names": [display_name(f) for f in sorted(online)],
    }


def items_report(session: Session) -> dict[str, dict[str, object]]:
    """A Char.Items payload: the equipped loadout as {slot: {name, mods, rarity}}, so a client can
    show what is worn, what it grants (the flat stat modifiers), and its rarity tier (to colour it).
    Empty when nothing is worn (an empty frame clears the client's panel, like Char.Target).
    Read-only projection of `session.equipped`; no value a client sees that the game would not."""
    from parts.world.items import ITEMS

    worn: dict[str, dict[str, object]] = {}
    for slot, iid in session.equipped.items():
        item = ITEMS.get(iid)
        if item is not None:
            worn[slot] = {
                "name": item["name"],
                "mods": dict(item["mods"]),
                "rarity": item.get("rarity", "common"),
            }
    return worn


def skills_report(session: Session) -> list[dict[str, object]]:
    """A Char.Skills payload: the abilities the character can wield right now (their primary job's
    kit plus a subjob's), each as {name, kind, mp_cost, element?}. So a client (its co-pilot) can
    recommend a SPECIFIC move for a foe's weakness ("cast Frostbite"), not just name the weakness.
    Empty when the character has no calling. Read-only projection of the ability data.
    """
    from parts.world.abilities import abilities_for_session

    kit: list[dict[str, object]] = []
    for _label, ability in abilities_for_session(session):
        entry: dict[str, object] = {
            "name": ability["name"],
            "kind": ability["kind"],
            "mp_cost": ability["mp_cost"],
        }
        element = ability.get("element")
        if element:  # only a typed move can answer a foe's weakness; untyped moves omit the key
            entry["element"] = element
        kit.append(entry)
    return kit


def resists_report(session: Session) -> dict[str, str]:
    """A Char.Resists payload: the player's OWN non-normal resistances {code: level}, the defensive
    mirror of a foe's profile in Char.Target. So a client can warn when a foe's blows strike an
    element you are Weak to (or reassure you it is one you shrug off). Empty before a calling, or
    when the calling resists nothing out of the ordinary. Read-only projection of the job's grid."""
    from parts.world.character_view import session_resistance
    from parts.world.score_sheet_model import RESIST_ORDER

    grid: dict[str, str] = {}
    for code in RESIST_ORDER:
        level = session_resistance(session, code)
        if level != "Normal":  # only what deviates from Normal is worth a frame (and a warning)
            grid[code] = level
    return grid
