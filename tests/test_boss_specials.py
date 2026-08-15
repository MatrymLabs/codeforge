"""Test twin for kernel/world/boss_specials.py - the telegraphed boss special (encounter depth, #4).

Acceptance: an enraged boss with a `special` begins a wind-up (a telegraph, no blow), then unleashes
a heavier blow whose affliction is guaranteed; the full loop reads through an NPC blow. Refusal: a
non-boss, an un-enraged boss, an un-special boss, and a declining cadence roll all start nothing.
"""

from __future__ import annotations

import pytest

from kernel.world import afflictions, boss_specials, combat
from kernel.world.seed import Npc
from kernel.world.session import SESSIONS, Session


class _Hit:
    """A cadence/affliction roll that always fires (randrange -> 0)."""

    def randrange(self, n: int) -> int:
        return 0


class _Miss:
    def randrange(self, n: int) -> int:
        return 1


def _boss(enraged: bool = True, special: dict | None = None) -> Npc:
    npc: Npc = {  # type: ignore[typeddict-item]
        "name": "the warden",
        "hp": 100,
        "hp_now": 20,  # below the 30% enrage line
        "atk": 20,
        "tier": "boss",
    }
    if enraged:
        npc["enraged"] = True
    if special is not None:
        npc["special"] = special
    return npc


# --- beginning a wind-up -----------------------------------------------------------------------
def test_an_enraged_boss_begins_a_wind_up(monkeypatch):
    monkeypatch.setattr(boss_specials, "_SPECIAL_RNG", _Hit())
    npc = _boss(special={"telegraph": "It coils to strike", "cadence": 2})
    line = boss_specials.maybe_begin_charge(npc)
    assert "It coils to strike" in line and boss_specials.is_charging(npc)


def test_a_non_boss_never_winds_up(monkeypatch):
    monkeypatch.setattr(boss_specials, "_SPECIAL_RNG", _Hit())
    npc = _boss(special={"telegraph": "x"})
    npc["tier"] = "normal"
    assert boss_specials.maybe_begin_charge(npc) == "" and not boss_specials.is_charging(npc)


def test_an_unenraged_boss_never_winds_up(monkeypatch):
    monkeypatch.setattr(boss_specials, "_SPECIAL_RNG", _Hit())
    npc = _boss(enraged=False, special={"telegraph": "x"})
    assert boss_specials.maybe_begin_charge(npc) == ""


def test_a_boss_without_a_special_never_winds_up(monkeypatch):
    monkeypatch.setattr(boss_specials, "_SPECIAL_RNG", _Hit())
    assert boss_specials.maybe_begin_charge(_boss(special=None)) == ""


def test_the_cadence_roll_can_decline(monkeypatch):
    monkeypatch.setattr(boss_specials, "_SPECIAL_RNG", _Miss())
    npc = _boss(special={"telegraph": "x", "cadence": 3})
    assert boss_specials.maybe_begin_charge(npc) == "" and not boss_specials.is_charging(npc)


def test_a_boss_already_charging_does_not_restack():
    npc = _boss(special={"telegraph": "x"})
    npc["charging"] = True
    assert boss_specials.maybe_begin_charge(npc) == ""  # already winding up


# --- unleashing --------------------------------------------------------------------------------
def test_unleash_spikes_the_blow_and_clears_the_charge():
    npc = _boss(special={"mult": 3})
    npc["charging"] = True
    blow, line = boss_specials.unleash(npc, 10)
    assert blow == 30 and "unleashes" in line and not boss_specials.is_charging(npc)


# --- the `mend` kind: a healing unleash turns the fight into a DPS race ---------------------------
def test_a_mend_special_heals_the_boss_and_lands_only_a_normal_blow():
    npc = _boss(special={"kind": "mend", "heal": 30})
    npc["charging"] = True
    blow, line = boss_specials.unleash(npc, 10)
    assert blow == 10  # a normal blow, NOT a spike -- the threat is the heal, not the hit
    assert npc["hp_now"] == 50  # 20 + 30 healed
    assert "knits its wounds" in line and not boss_specials.is_charging(npc)


def test_a_mend_never_heals_past_full_health():
    npc = _boss(special={"kind": "mend", "heal": 999})
    npc["hp_now"] = 90
    npc["charging"] = True
    boss_specials.unleash(npc, 10)
    assert npc["hp_now"] == 100  # capped at max hp


def test_a_mend_defaults_its_heal_when_the_seed_omits_it():
    npc = _boss(special={"kind": "mend"})
    npc["charging"] = True
    boss_specials.unleash(npc, 5)
    assert npc["hp_now"] == 20 + boss_specials.DEFAULT_HEAL


def test_the_default_kind_still_strikes_backward_compatible():
    npc = _boss(special={"mult": 2})  # no kind -> the original `strike` spike
    npc["charging"] = True
    blow, line = boss_specials.unleash(npc, 10)
    assert blow == 20 and "unleashes" in line


# --- the `drain` kind: vampiric -- it spikes the hero AND heals itself for half the blow ---------
def test_a_drain_special_spikes_the_blow_and_heals_the_boss():
    npc = _boss(special={"kind": "drain", "mult": 3})
    npc["charging"] = True
    blow, line = boss_specials.unleash(npc, 10)
    assert blow == 30  # a real spike (10 * 3), UNLIKE mend's normal blow -- the heal rides the hit
    assert npc["hp_now"] == 35  # 20 + 30//2 (15) siphoned back
    assert "drinks your wound" in line and not boss_specials.is_charging(npc)


def test_a_drain_never_heals_past_full_health():
    npc = _boss(special={"kind": "drain", "mult": 99})
    npc["hp_now"] = 98
    npc["charging"] = True
    boss_specials.unleash(npc, 10)
    assert npc["hp_now"] == 100  # capped at max hp


def test_unleash_is_a_no_op_when_not_charging():
    assert boss_specials.unleash(_boss(special={}), 10) == (10, "")


# --- the full loop through a real NPC blow -----------------------------------------------------
def test_the_special_loop_reads_through_an_npc_blow(monkeypatch):
    monkeypatch.setattr(boss_specials, "_SPECIAL_RNG", _Hit())  # always begins the wind-up
    monkeypatch.setattr(afflictions, "_AFFLICT_RNG", _Miss())  # unleash affliction is NOT a roll
    s = SESSIONS["matrym"] = Session(player_id="matrym", location="courtyard")
    from kernel.world.jobs import bind_calling
    from kernel.world.resources import Resource

    bind_calling(s, "vanguard")
    s.resources["hp"] = Resource(name="hp", current=500, maximum=500)  # enough to survive the spike
    npc: Npc = {  # type: ignore[typeddict-item]
        "name": "the warden",
        "hp": 100,
        "hp_now": 20,
        "atk": 20,
        "tier": "boss",
        "enraged": True,
        "inflicts": {"status": "venom", "chance": 99, "damage": 8, "ticks": 3},
        "special": {"telegraph": "It gathers dark power", "mult": 2, "cadence": 1},
    }
    hp_before = s.resources["hp"].current

    wind = combat._resolve_npc_blow(s, npc, "lunges")
    assert "It gathers dark power" in wind  # the wind-up beat: a telegraph...
    assert s.resources["hp"].current == hp_before  # ...and no blow landed
    assert "venom" not in s.afflictions

    unleashed = combat._resolve_npc_blow(s, npc, "lunges")
    assert "unleashes" in unleashed  # the next beat: the heavy hit
    assert s.resources["hp"].current < hp_before  # it hurt
    assert s.afflictions.get("venom") == {"damage": 8, "ticks": 3}  # affliction GUARANTEED
    SESSIONS.pop("matrym", None)


# --- seed validation ---------------------------------------------------------------------------
def _load(tmp_path, body: str):
    from kernel.world.seed import load_npcs

    path = tmp_path / "npcs.yaml"
    path.write_text(body)
    return lambda: load_npcs(path)


def test_special_rejects_an_unknown_key(tmp_path):
    from kernel.world.seed import BlueprintError

    load = _load(tmp_path, "b:\n  location: a\n  hp: 10\n  special: {telegraph: x, power: 9}\n")
    with pytest.raises(BlueprintError, match="special"):
        load()


def test_special_rejects_a_non_positive_mult(tmp_path):
    from kernel.world.seed import BlueprintError

    load = _load(tmp_path, "b:\n  location: a\n  hp: 10\n  special: {mult: 0}\n")
    with pytest.raises(BlueprintError, match="special.mult"):
        load()


def test_a_valid_special_loads(tmp_path):
    from kernel.world.seed import load_npcs

    path = tmp_path / "npcs.yaml"
    path.write_text(
        "b:\n  location: a\n  hp: 10\n  special: {telegraph: Winds up, mult: 2, cadence: 3}\n"
    )
    npc = load_npcs(path)["b"]
    assert npc["special"] == {"telegraph": "Winds up", "mult": 2, "cadence": 3}
