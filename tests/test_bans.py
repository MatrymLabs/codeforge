"""Test twin for parts/world/bans.py + the @ban/@unban/@bans verbs.

Acceptance: ban records a character with a reason and moderator; is_banned/reason report it; unban
lifts it; all_bans lists them. Refusal / safety: unban a hero who is not banned returns False; the
verbs are wizard-gated, drop an online target, and record every ban/unban to the audit log. Real
store, quarantined to tmp by conftest.
"""

from __future__ import annotations

from parts.world import audit, bans
from parts.world.jobs import bind_calling
from parts.world.session import SESSIONS, Session


def _staff(name: str = "root", rank: str = "wizard") -> Session:
    s = SESSIONS[name] = Session(player_id=name, named=True)
    s.rank = rank
    bind_calling(s, "vanguard")
    return s


def _teardown() -> None:
    for name in list(SESSIONS):
        SESSIONS.pop(name, None)


# --- the store ----------------------------------------------------------------------------------
def test_ban_records_and_is_banned_reports_it():
    bans.ban("griefer", "spawn camping", "root")
    assert bans.is_banned("griefer") is True
    assert bans.reason("griefer") == "spawn camping"
    assert bans.is_banned("innocent") is False and bans.reason("innocent") == ""


def test_unban_lifts_a_ban_and_returns_false_for_a_clean_hero():
    bans.ban("griefer", "x", "root")
    assert bans.unban("griefer") is True
    assert bans.is_banned("griefer") is False
    assert bans.unban("griefer") is False  # nothing left to lift


def test_all_bans_lists_every_ban():
    bans.ban("a", "one", "root")
    bans.ban("b", "two", "mod")
    assert set(bans.all_bans()) == {("a", "one", "root"), ("b", "two", "mod")}


# --- the verbs (audited + online drop) ---------------------------------------------------------
def test_the_ban_verb_records_audits_and_drops_an_online_target():
    import forge

    try:
        root = _staff("root", "owner")
        victim = SESSIONS["griefer"] = Session(player_id="griefer", named=True)
        out = forge.handle_command(root, "@ban griefer harassment")
        assert "banned" in out.lower()
        assert bans.is_banned("griefer") is True
        assert victim.alive is False  # dropped on their next command
        assert any(e["action"] == "ban" and "griefer" in e["detail"] for e in audit.tail())
    finally:
        _teardown()


def test_unban_verb_lifts_and_audits():
    import forge

    try:
        root = _staff("root", "owner")
        bans.ban("griefer", "x", "root")
        out = forge.handle_command(root, "@unban griefer")
        assert "no longer banned" in out.lower()
        assert bans.is_banned("griefer") is False
        assert any(e["action"] == "unban" for e in audit.tail())
    finally:
        _teardown()


def test_a_plain_player_cannot_ban():
    import forge

    try:
        pleb = _staff("pleb", "player")
        forge.handle_command(pleb, "@ban someone spite")
        assert bans.is_banned("someone") is False  # a rank-gated verb never ran
    finally:
        _teardown()
