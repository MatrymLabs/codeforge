"""Test twin for parts/world/afflictions.py -- harmful statuses the PLAYER suffers (roadmap #4).

Acceptance: a damage-over-time saps the player each world beat, ages, and expires; a daze blocks
offensive actions and wears off; an NPC's `inflicts` blow lays one on a hit (seeded roll); the beat
runs the ticker. Refusal: a DoT never fells the player (HP floored at 1), a missed roll lays
nothing, and a malformed `inflicts` spec fails loud at load.
"""

from __future__ import annotations

import pytest

import forge
from parts.world import afflictions, combat
from parts.world.abilities import use_ability
from parts.world.resources import Resource
from parts.world.session import SESSIONS, Session


def _hurtable(hp: int = 100, maximum: int = 100) -> Session:
    s = Session(player_id="mark", location="void")
    s.resources["hp"] = Resource(name="hp", current=hp, maximum=maximum)
    return s


class _Hit:
    """A roll that always lands the affliction (randrange -> 0). Assigned at runtime, so it need not
    be a full random.Random -- afflictions only calls randrange."""

    def randrange(self, n: int) -> int:
        return 0


class _Miss:
    def randrange(self, n: int) -> int:
        return 1  # never the 0 that lands


# --- damage-over-time --------------------------------------------------------------------------
def test_a_dot_saps_the_player_each_beat_then_expires():
    s = _hurtable()
    afflictions.apply_dot(s, "venom", 10, ticks=2)
    line = afflictions.tick_afflictions(s)
    assert s.resources["hp"].current == 90 and "venom saps you for 10" in line
    afflictions.tick_afflictions(s)  # second (last) tick
    assert s.resources["hp"].current == 80
    assert "venom" not in s.afflictions  # expired after its ticks
    assert afflictions.tick_afflictions(s) == ""  # nothing left to sap


def test_a_dot_never_fells_the_player():
    s = _hurtable(hp=5)
    afflictions.apply_dot(s, "bleed", 50, ticks=3)  # would overkill
    for _ in range(3):
        afflictions.tick_afflictions(s)
    assert s.resources["hp"].current == 1  # floored at 1: the foe's blow must land the kill


def test_apply_dot_refreshes_rather_than_stacks():
    s = _hurtable()
    afflictions.apply_dot(s, "venom", 10, ticks=1)
    afflictions.apply_dot(s, "venom", 10, ticks=3)  # re-applied: one affliction, reset clock
    assert s.afflictions["venom"] == {"damage": 10, "ticks": 3}


# --- daze --------------------------------------------------------------------------------------
def test_a_daze_holds_then_wears_off():
    s = _hurtable()
    afflictions.apply_daze(s, 2)
    assert afflictions.is_dazed(s)
    assert afflictions.tick_afflictions(s) == ""  # still dazed after one beat, silent
    assert afflictions.is_dazed(s)
    assert "shake off the daze" in afflictions.tick_afflictions(s)  # second beat clears it
    assert not afflictions.is_dazed(s)


def test_apply_daze_never_shortens_an_existing_stun():
    s = _hurtable()
    afflictions.apply_daze(s, 3)
    afflictions.apply_daze(s, 1)  # a shorter daze must not cut the stun down
    assert s.dazed == 3


def test_a_dazed_player_cannot_strike_or_channel():
    s = SESSIONS["matrym"] = Session(player_id="matrym", location="courtyard")
    from parts.world.jobs import bind_calling

    bind_calling(s, "vanguard")
    afflictions.apply_daze(s, 1)
    assert "dazed and cannot strike" in combat.attack(s, "dummy")
    assert "dazed and cannot channel" in use_ability(s, "anything")
    SESSIONS.pop("matrym", None)


# --- infliction from an NPC blow ---------------------------------------------------------------
def test_maybe_inflict_lays_a_dot_on_a_hit(monkeypatch):
    monkeypatch.setattr(afflictions, "_AFFLICT_RNG", _Hit())
    s = _hurtable()
    spec = {"status": "venom", "chance": 2, "damage": 12, "ticks": 4}
    assert afflictions.maybe_inflict(s, spec) == "You are afflicted with venom!"
    assert s.afflictions["venom"] == {"damage": 12, "ticks": 4}


def test_maybe_inflict_lays_a_daze_on_a_hit(monkeypatch):
    monkeypatch.setattr(afflictions, "_AFFLICT_RNG", _Hit())
    s = _hurtable()
    assert "dazed" in (afflictions.maybe_inflict(s, {"status": "daze", "beats": 2}) or "")
    assert s.dazed == 2


def test_maybe_inflict_misses_on_a_failed_roll(monkeypatch):
    monkeypatch.setattr(afflictions, "_AFFLICT_RNG", _Miss())
    s = _hurtable()
    assert afflictions.maybe_inflict(s, {"status": "venom", "chance": 3}) is None
    assert s.afflictions == {}


def test_maybe_inflict_is_a_no_op_without_a_spec():
    assert afflictions.maybe_inflict(_hurtable(), None) is None


def test_an_inflicting_npc_blow_afflicts_the_player(monkeypatch):
    """Integration: a hostile foe carrying `inflicts` lays the affliction when its blow lands."""
    monkeypatch.setattr(afflictions, "_AFFLICT_RNG", _Hit())
    s = SESSIONS["matrym"] = Session(player_id="matrym", location="courtyard")
    from parts.world.jobs import bind_calling

    bind_calling(s, "vanguard")
    foe = {
        "name": "the venom-warden",
        "atk": 20,
        "hp": 50,
        "hp_now": 50,
        "inflicts": {"status": "venom", "chance": 1, "damage": 8, "ticks": 3},
    }
    line = combat._resolve_npc_blow(s, foe, "lunges")
    assert "afflicted with venom" in line
    assert s.afflictions.get("venom") == {"damage": 8, "ticks": 3}
    SESSIONS.pop("matrym", None)


def test_render_afflictions_summarizes_what_ails_you():
    s = _hurtable()
    assert afflictions.render_afflictions(s) == ""  # hale
    afflictions.apply_dot(s, "venom", 5, ticks=3)
    afflictions.apply_daze(s, 2)
    line = afflictions.render_afflictions(s)
    assert "venom (3)" in line and "dazed (2)" in line


# --- the world beat runs the ticker ------------------------------------------------------------
def test_the_beat_ages_afflictions():
    s = SESSIONS["matrym"] = Session(player_id="matrym", location="courtyard")
    s.resources["hp"] = Resource(name="hp", current=100, maximum=100)
    afflictions.apply_dot(s, "venom", 7, ticks=2)
    forge.handle_command(s, "look")  # any command takes a world beat
    assert s.resources["hp"].current == 93  # the beat sapped the venom
    SESSIONS.pop("matrym", None)


# --- seed validation: an NPC's inflicts spec fails loud on misuse ------------------------------
def _npc_yaml(tmp_path, body: str):
    from parts.world.seed import load_npcs

    path = tmp_path / "npcs.yaml"
    path.write_text(body)
    return lambda: load_npcs(path)


def test_inflicts_must_name_a_status(tmp_path):
    from parts.world.seed import SeedError

    load = _npc_yaml(tmp_path, "boss:\n  location: a\n  hp: 10\n  inflicts: {chance: 2}\n")
    with pytest.raises(SeedError, match="inflicts.status"):
        load()


def test_inflicts_rejects_an_unknown_key(tmp_path):
    from parts.world.seed import SeedError

    load = _npc_yaml(
        tmp_path, "boss:\n  location: a\n  hp: 10\n  inflicts: {status: venom, dot: 5}\n"
    )
    with pytest.raises(SeedError, match="inflicts"):
        load()


def test_inflicts_rejects_a_non_positive_number(tmp_path):
    from parts.world.seed import SeedError

    load = _npc_yaml(
        tmp_path, "boss:\n  location: a\n  hp: 10\n  inflicts: {status: venom, damage: 0}\n"
    )
    with pytest.raises(SeedError, match="inflicts.damage"):
        load()


def test_a_valid_inflicts_loads(tmp_path):
    from parts.world.seed import load_npcs

    path = tmp_path / "npcs.yaml"
    path.write_text(
        "boss:\n  location: a\n  hp: 10\n  inflicts: {status: venom, damage: 12, ticks: 4}\n"
    )
    npc = load_npcs(path)["boss"]
    assert npc["inflicts"] == {"status": "venom", "damage": 12, "ticks": 4}


# --- seed validation: a boss's `special` (the telegraphed-unleash mechanic) -----------------------
def test_a_mend_special_loads(tmp_path):
    from parts.world.seed import load_npcs

    path = tmp_path / "npcs.yaml"
    path.write_text("boss:\n  location: a\n  hp: 10\n  special: {kind: mend, heal: 40}\n")
    assert load_npcs(path)["boss"]["special"] == {"kind": "mend", "heal": 40}


def test_special_rejects_an_unknown_kind(tmp_path):
    from parts.world.seed import SeedError

    load = _npc_yaml(tmp_path, "boss:\n  location: a\n  hp: 10\n  special: {kind: explode}\n")
    with pytest.raises(SeedError, match="special.kind"):
        load()


def test_special_rejects_an_unknown_key(tmp_path):
    from parts.world.seed import SeedError

    load = _npc_yaml(tmp_path, "boss:\n  location: a\n  hp: 10\n  special: {summon: 3}\n")
    with pytest.raises(SeedError, match="special"):
        load()


def test_special_rejects_a_non_positive_heal(tmp_path):
    from parts.world.seed import SeedError

    load = _npc_yaml(tmp_path, "boss:\n  location: a\n  hp: 10\n  special: {kind: mend, heal: 0}\n")
    with pytest.raises(SeedError, match="special.heal"):
        load()


# --- cleanse: purge every affliction at once (the support's counter) -----------------------------


def test_cleanse_purges_dots_and_daze_and_names_them():
    s = _hurtable()
    afflictions.apply_dot(s, "venom", 3)
    afflictions.apply_daze(s, 2)
    cleared = afflictions.cleanse(s)
    assert cleared == ["venom", "daze"]  # dots (sorted) then daze
    assert s.afflictions == {} and s.dazed == 0


def test_cleanse_of_a_clean_hero_returns_nothing():
    s = _hurtable()
    assert afflictions.cleanse(s) == []


def test_cleanse_ability_purges_an_afflicted_ally_and_spends_mp():
    from parts.world.jobs import bind_calling

    healer = Session(player_id="cleo", location="void")
    bind_calling(healer, "scholar")
    ally = Session(player_id="bram", location="void")
    bind_calling(ally, "vanguard")
    SESSIONS.update({"cleo": healer, "bram": ally})
    afflictions.apply_daze(ally, 3)
    afflictions.apply_dot(ally, "venom", 2)
    mp_before = healer.resources["mp"].current
    try:
        out = use_ability(healer, "cleansing light on bram")
        assert "purging" in out and "on Bram" in out
        assert not ally.afflictions and ally.dazed == 0  # the ally is clean
        assert healer.resources["mp"].current == mp_before - 4  # MP spent
    finally:
        SESSIONS.clear()


def test_cleanse_on_a_clean_ally_spends_no_mp():
    from parts.world.jobs import bind_calling

    healer = Session(player_id="cleo", location="void")
    bind_calling(healer, "scholar")
    SESSIONS["cleo"] = healer  # cleanse self, nothing ails
    mp_before = healer.resources["mp"].current
    try:
        out = use_ability(healer, "cleansing light on me")
        assert "Nothing ails you" in out
        assert healer.resources["mp"].current == mp_before  # no MP wasted on a clean target
    finally:
        SESSIONS.clear()


def test_cleanse_ability_on_self_shakes_off_the_affliction():
    from parts.world.jobs import bind_calling

    healer = Session(player_id="cleo", location="void")
    bind_calling(healer, "scholar")
    SESSIONS["cleo"] = healer
    afflictions.apply_dot(healer, "venom", 3)  # a DoT, not a daze -- a dazed caster can't act
    try:
        out = use_ability(healer, "cleansing light on me")
        assert "shake off" in out and "venom" in out
        assert not healer.afflictions
    finally:
        SESSIONS.clear()


def test_cleanse_ability_on_an_absent_ally_fails_loud():
    from parts.world.jobs import bind_calling

    healer = Session(player_id="cleo", location="void")
    bind_calling(healer, "scholar")
    SESSIONS["cleo"] = healer
    try:
        assert "no ally called 'ghost'" in use_ability(healer, "cleansing light on ghost")
    finally:
        SESSIONS.clear()
