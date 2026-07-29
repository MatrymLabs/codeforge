"""Tests for the gmcp card: framing, IAC escaping, negotiation reading, and state reports.

Pure and socket-free. The hostile cases matter here: a 255 byte inside a payload, a refusal, a
near-miss option, and a partial frame must all be handled without desyncing a client or raising.
"""

import json

from parts.gmcp import (
    GMCP_OPT,
    enables_gmcp,
    escape_iac,
    friends_report,
    gmcp_frame,
    guild_report,
    items_report,
    mail_report,
    party_report,
    quest_report,
    resists_report,
    room_report,
    skills_report,
    target_report,
    vitals_report,
)
from parts.world.jobs import bind_calling
from parts.world.session import Session

IAC, SB, SE = 255, 250, 240
WILL, WONT, DO, DONT = 251, 252, 253, 254


# --- framing ---------------------------------------------------------------


def test_frame_wraps_package_and_json_in_a_subnegotiation():
    frame = gmcp_frame("Char.Vitals", {"hp": 50, "maxhp": 60})
    assert frame[:3] == bytes([IAC, SB, GMCP_OPT])
    assert frame[-2:] == bytes([IAC, SE])
    body = frame[3:-2].decode("utf-8")
    package, _, payload = body.partition(" ")
    assert package == "Char.Vitals"
    assert json.loads(payload) == {"hp": 50, "maxhp": 60}


def test_frame_uses_compact_json_no_spaces():
    frame = gmcp_frame("Room.Info", {"num": "forge", "exits": {"north": "hall"}})
    assert b", " not in frame and b'": ' not in frame  # compact separators


def test_frame_without_a_body_omits_the_payload():
    frame = gmcp_frame("Core.Ping", None)
    assert frame == bytes([IAC, SB, GMCP_OPT]) + b"Core.Ping" + bytes([IAC, SE])


def test_frame_refuses_an_empty_package():
    try:
        gmcp_frame("", {"x": 1})
    except ValueError:
        return
    raise AssertionError("empty package name must fail loud")


# --- IAC escaping (the desync trap) ----------------------------------------


def test_escape_doubles_a_literal_iac_byte():
    assert escape_iac(bytes([IAC])) == bytes([IAC, IAC])
    assert escape_iac(b"a" + bytes([IAC]) + b"b") == b"a" + bytes([IAC, IAC]) + b"b"


def test_escape_leaves_ordinary_bytes_untouched():
    assert escape_iac(b"Char.Vitals {}") == b"Char.Vitals {}"


def test_frame_escapes_an_iac_byte_in_the_payload_so_the_client_never_desyncs():
    # A raw 0xFF in a body must reach the client as 0xFF 0xFF, never as a lone command byte.
    body = b'X {"b":"\xff"}'
    raw = bytes([IAC, SB, GMCP_OPT]) + escape_iac(body) + bytes([IAC, SE])
    inner = raw[3:-2]  # the escaped body, without the frame's own IAC SB / IAC SE
    assert bytes([IAC, IAC]) in inner  # the payload 0xFF got doubled
    assert inner.count(bytes([IAC])) == 2  # exactly the one doubled byte, nothing stray


# --- negotiation reading ---------------------------------------------------


def test_do_gmcp_enables():
    assert enables_gmcp(bytes([IAC, DO, GMCP_OPT])) is True


def test_will_gmcp_enables():
    assert enables_gmcp(bytes([IAC, WILL, GMCP_OPT])) is True


def test_dont_and_wont_gmcp_disable():
    assert enables_gmcp(bytes([IAC, DONT, GMCP_OPT])) is False
    assert enables_gmcp(bytes([IAC, WONT, GMCP_OPT])) is False


def test_plain_text_leaves_the_decision_unchanged():
    assert enables_gmcp(b"look\r\n") is None  # a raw nc client never enables GMCP


def test_a_different_option_is_ignored():
    assert enables_gmcp(bytes([IAC, DO, 1])) is None  # DO ECHO, not GMCP


def test_the_last_gmcp_verb_in_a_chunk_wins():
    chunk = bytes([IAC, WILL, GMCP_OPT]) + bytes([IAC, DONT, GMCP_OPT])
    assert enables_gmcp(chunk) is False


def test_a_truncated_negotiation_does_not_raise():
    assert enables_gmcp(bytes([IAC, DO])) is None  # option byte never arrived


# --- state reports (derive, don't store) -----------------------------------


def _hero() -> Session:
    session = Session(player_id="ada")
    bind_calling(session, "vanguard")  # grants a job, stats, and hp/mp pools
    return session


def test_vitals_report_reads_live_pools():
    report = vitals_report(_hero())
    assert report is not None
    assert report["hp"] == report["maxhp"] > 0  # freshly bound: full pool
    assert set(report) == {"hp", "maxhp", "mp", "maxmp", "level", "xp", "nextlevel"}
    assert report["level"] == 1


def test_vitals_report_is_none_before_a_calling():
    assert vitals_report(Session(player_id="nobody")) is None  # no job yet


def test_room_report_names_the_current_location_and_its_exits():
    session = _hero()
    report = room_report(session)
    assert report["num"] == session.location
    assert isinstance(report["name"], str) and report["name"]
    assert isinstance(report["exits"], dict)


def test_room_report_on_an_unknown_location_renders_honestly():
    session = Session(player_id="lost", location="void_that_is_not_seeded")
    report = room_report(session)
    assert report == {"num": "void_that_is_not_seeded", "name": "(nowhere)", "exits": {}}


def test_skills_report_lists_the_wieldable_kit():
    session = _hero()  # a vanguard: wields Power Strike in first-forge
    kit = skills_report(session)
    assert kit  # non-empty
    ps = next(s for s in kit if s["name"] == "Power Strike")
    assert ps["kind"] == "strike" and "mp_cost" in ps
    assert "element" not in ps  # first-forge Power Strike is untyped: the key is omitted


def test_skills_report_carries_an_abilitys_element(monkeypatch):
    from parts.world.abilities import ABILITIES

    session = _hero()
    monkeypatch.setitem(ABILITIES["power_strike"], "element", "FIR")
    ps = next(s for s in skills_report(session) if s["name"] == "Power Strike")
    assert ps["element"] == "FIR"  # a typed move carries its element, so a client can match a foe


def test_skills_report_is_empty_before_a_calling():
    assert skills_report(Session(player_id="nobody")) == []  # no calling: an empty kit clears it


def test_resists_report_lists_the_players_nonnormal_resistances():
    session = Session(player_id="rae")
    bind_calling(session, "engineer")  # first-forge engineer declares LGT: Weak, ERT: Resist
    grid = resists_report(session)
    assert grid.get("LGT") == "Weak"
    assert grid.get("ERT") == "Resist"
    assert "FIR" not in grid  # a Normal resistance is omitted (only deviations are worth a warning)


def test_resists_report_is_empty_before_a_calling():
    assert resists_report(Session(player_id="nobody")) == {}  # no calling: no grid to warn on


def test_items_report_lists_the_equipped_loadout_with_mods_and_is_empty_when_bare():
    from parts.world.items import ITEMS, clone

    session = _hero()
    assert items_report(session) == {}  # nothing worn: an empty frame clears the client panel
    iid = clone("forge_wrench", "player")
    session.equipped["weapon"] = iid
    session.equipped["ghost"] = "vanished_instance"  # an equipped id with no ITEMS entry is skipped
    try:
        report = items_report(session)
        assert set(report) == {"weapon"}  # the ghost is omitted
        assert report["weapon"]["name"] == "a modular forge wrench"
        assert report["weapon"]["mods"] == ITEMS[iid]["mods"]  # the stat modifiers it grants
        assert report["weapon"]["rarity"] == "common"  # a base clone is common until a drop rolls
    finally:
        ITEMS.pop(iid, None)  # conftest clears SESSIONS, not ITEMS: do not leak this instance


# --- Char.Target: the foe you are fighting ---------------------------------


def test_target_report_is_none_when_not_in_combat():
    session = _hero()  # spawns away from any foe, engaged with nothing
    assert target_report(session) is None


def test_target_report_names_an_engaged_foe_with_its_hp():
    session = _hero()
    session.location = "courtyard"  # where the training dummy stands
    session.aggro_beats["training_dummy"] = 1  # engaged: it is hounding us this beat
    report = target_report(session)
    assert report == {"name": "The training dummy", "hp": 20, "maxhp": 20}


def test_target_report_reads_a_wounded_foe_even_without_aggression(monkeypatch):
    from parts.world.npcs import NPCS

    session = _hero()
    session.location = "courtyard"
    monkeypatch.setitem(NPCS["training_dummy"], "hp_now", 7)  # a bloodied foe, restored after test
    report = target_report(session)
    assert report == {"name": "The training dummy", "hp": 7, "maxhp": 20}


def test_target_report_carries_a_typed_foes_elemental_profile(monkeypatch):
    """The Char.Target frame names the foe's attack element and its non-normal resistances, so a
    client's co-pilot can advise the right element. Both keys are additive: a Normal row is omitted
    and an untyped foe carries neither."""
    from parts.world.npcs import NPCS

    session = _hero()
    session.location = "courtyard"
    session.aggro_beats["training_dummy"] = 1
    monkeypatch.setitem(NPCS["training_dummy"], "attack_element", "FIR")
    grid = {"FIR": "Immune", "ICE": "Weak", "LGT": "Normal"}
    monkeypatch.setitem(NPCS["training_dummy"], "resistances", grid)
    report = target_report(session)
    assert report is not None
    assert report["element"] == "FIR"
    assert report["resists"] == {"FIR": "Immune", "ICE": "Weak"}  # the Normal row is dropped


def test_target_report_omits_the_profile_for_an_untyped_foe():
    session = _hero()
    session.location = "courtyard"  # the training dummy: untyped, resists nothing
    session.aggro_beats["training_dummy"] = 1
    report = target_report(session)
    assert report == {"name": "The training dummy", "hp": 20, "maxhp": 20}  # no profile keys


def test_target_report_skips_a_non_combatant():
    session = _hero()
    session.location = "library"  # the librarian lives here: hp 0, never a target
    session.aggro_beats["librarian"] = 1  # even if flagged, a 0-hp NPC has no health bar
    assert target_report(session) is None


# --- Char.Quest: the story arc you are on ----------------------------------


def test_quest_report_tracks_the_active_story_quest():
    report = quest_report(_hero())
    assert report is not None
    assert set(report) == {"name", "step"}
    assert report["name"] and report["step"]  # a live name and a human-readable step


def test_quest_report_is_none_when_no_authored_quest_is_active(monkeypatch):
    from parts.world import quest as quest_card

    monkeypatch.setattr(quest_card, "_QUESTS", {})  # a world with no story arcs
    assert quest_report(_hero()) is None


# --- Char.Party / Char.Guild social frames ------------------------------------------------------
def test_party_report_is_none_when_solo():
    session = _hero()
    assert party_report(session) is None


def test_party_report_names_the_fellowship_and_leader():
    from parts.world import party
    from parts.world.session import SESSIONS

    try:
        ada = _hero()  # player_id "ada"
        bram = Session(player_id="bram")
        SESSIONS["ada"], SESSIONS["bram"] = ada, bram
        party.invite("ada", "bram")
        party.join("bram", "ada")
        report = party_report(ada)
        assert report == {"members": ["Ada", "Bram"], "leader": "Ada", "size": 2}
    finally:
        party._reset()
        for name in ("ada", "bram"):
            SESSIONS.pop(name, None)


def test_guild_report_is_none_when_guildless():
    session = _hero()
    assert guild_report(session) is None


def test_guild_report_carries_the_guild_name_and_rank():
    session = _hero()
    session.guild = "iron_wardens"
    session.guild_rank = "officer"
    assert guild_report(session) == {"name": "Iron Wardens", "rank": "officer"}


def test_mail_report_is_none_for_an_empty_inbox_or_unnamed_hero():
    from parts.world.session import Session

    solo = _hero()  # not named
    assert mail_report(solo) is None  # unnamed: no inbox
    named = Session(player_id="ada", named=True)
    assert mail_report(named) is None  # named but empty inbox


def test_mail_report_counts_unread_and_total():
    from parts.world import mail_store
    from parts.world.session import Session

    ada = Session(player_id="ada", named=True)
    mail_store.send("ada", "bram", "one", sent_utc="2026-07-28T12:00:00Z")
    mail_store.send("ada", "bram", "two", sent_utc="2026-07-28T12:01:00Z")
    mail_store.mark_read(mail_store.inbox("ada")[0].id)  # read the newest
    assert mail_report(ada) == {"unread": 1, "total": 2}


def test_friends_report_is_none_with_no_friends():
    assert friends_report(_hero()) is None


def test_friends_report_counts_online_and_names_them():
    from parts.world.session import SESSIONS, Session

    try:
        ada = _hero()
        ada.friends = ["bram", "cade"]  # cade is offline
        SESSIONS["bram"] = Session(player_id="bram")
        report = friends_report(ada)
        assert report == {"online": 1, "total": 2, "names": ["Bram"]}
    finally:
        SESSIONS.pop("bram", None)
