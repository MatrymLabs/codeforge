"""Tests for the gmcp card: framing, IAC escaping, negotiation reading, and state reports.

Pure and socket-free. The hostile cases matter here: a 255 byte inside a payload, a refusal, a
near-miss option, and a partial frame must all be handled without desyncing a client or raising.
"""

import json

from parts.gmcp import (
    GMCP_OPT,
    enables_gmcp,
    escape_iac,
    gmcp_frame,
    room_report,
    vitals_report,
)
from parts.jobs import bind_calling
from parts.session import Session

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
