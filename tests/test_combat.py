"""Test twin for parts/combat.py -- deterministic training-loop math."""

import copy

import pytest

from parts import npcs
from parts.combat import attack, strike_power
from parts.jobs import bind_calling
from parts.seed import Npc
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_world():
    # Restore in place (clear + update, never rebind): combat.py holds
    # `from parts.npcs import NPCS`, so rebinding npcs.NPCS would strand that alias.
    npcs_snap = copy.deepcopy(npcs.NPCS)
    SESSIONS.clear()
    yield
    npcs.NPCS.clear()
    npcs.NPCS.update(npcs_snap)
    SESSIONS.clear()


def _fighter(job: str = "vanguard", location: str = "courtyard") -> Session:
    s = Session(player_id="matrym", location=location)
    SESSIONS["matrym"] = s
    bind_calling(s, job)
    return s


def test_attack_without_a_calling_is_refused():
    s = Session(player_id="matrym", location="courtyard")
    assert "no calling yet" in attack(s, "dummy")


def test_defeating_an_npc_surfaces_a_triggered_quest_line(monkeypatch):
    """Combat rides the quest hook on top: if a fallen npc completes a story beat, its line is
    appended to the defeat report (the aethryn Cinder-Wight uses this to end the Relighting)."""
    import parts.quest as quest_mod

    monkeypatch.setattr(
        quest_mod, "on_event", lambda session, kind, target: "[The Relighting] the cold breaks"
    )
    s = _fighter()  # courtyard: the training dummy
    out = ""
    for _ in range(10):
        out = attack(s, "dummy")
        if "collapses" in out:
            break
    assert "[The Relighting] the cold breaks" in out  # the quest hook reached the player


def test_peaceful_npcs_cannot_be_fought():
    s = _fighter(location="library")
    assert "not something you can fight" in attack(s, "librarian")


def test_damage_comes_from_strength():
    assert strike_power(_fighter("vanguard")) == 3 + 14 // 3  # 7
    SESSIONS.clear()
    assert strike_power(_fighter("scholar")) == 3 + 5 // 3  # 4


def test_strikes_wear_the_dummy_down_and_it_reassembles():
    s = _fighter()  # 7 damage vs 20 hp: 13, 6, defeat
    assert "(13/20)" in attack(s, "dummy")
    assert "(6/20)" in attack(s, "dummy")
    final = attack(s, "dummy")
    assert "reassembles" in final
    assert "You gain 30 XP." in final
    assert npcs.NPCS["training_dummy"]["hp_now"] == 20


def test_a_landed_strike_advances_the_combat_clock():
    """A basic attack is a combat action: it thaws cooldowns and ages statuses, so a player
    can trade normal blows while a cooldown recovers (not only by spending another ability)."""
    s = _fighter("engineer")
    s.cooldowns["field_repair"] = 2
    s.statuses["barrier"] = 2
    attack(s, "dummy")
    assert s.cooldowns["field_repair"] == 1  # one round passed
    assert s.statuses["barrier"] == 1


def test_a_refused_swing_does_not_advance_the_clock():
    """Only a LANDED strike counts. A swing at nothing (no target) is not a round."""
    s = _fighter("engineer")
    s.cooldowns["field_repair"] = 2
    attack(s, "nobody-here")
    assert s.cooldowns["field_repair"] == 2  # unchanged: no action was taken


def test_attack_flows_through_the_engine_tick():
    from forge import handle_command

    s = _fighter()
    out = handle_command(s, "attack dummy")
    assert "You strike the training dummy" in out


def _spawn_hostile(label: str = "brawler", location: str = "courtyard", atk: int = 5, hp: int = 50):
    """Place a fighting NPC in a room. Written to both aliased registries; the fixture cleans up."""
    hostile: Npc = {
        "name": f"the {label}",
        "keywords": [label],
        "location": location,
        "dialogue": ["..."],
        "next_line": 0,
        "hp": hp,
        "hp_now": hp,
        "xp": 10,
        "atk": atk,
    }
    npcs.NPCS[label] = hostile  # combat.py's NPCS alias sees this (same object, no rebinds)
    return label


def test_npc_strike_power_reads_the_atk_stat():
    from parts.combat import npc_strike_power

    _spawn_hostile(atk=5)
    assert npc_strike_power(npcs.NPCS["brawler"]) == 5
    assert npc_strike_power(npcs.NPCS["training_dummy"]) == 0  # passive by default


def test_a_hostile_npc_strikes_back_when_it_survives():
    s = _fighter()
    _spawn_hostile(atk=5, hp=50)
    max_hp = s.resources["hp"].maximum
    out = attack(s, "brawler")
    assert "strikes back for 5" in out
    assert s.resources["hp"].current == max_hp - 5  # exact, deterministic


def test_the_passive_training_dummy_never_strikes_back():
    s = _fighter()  # the dummy carries no atk stat
    max_hp = s.resources["hp"].maximum
    out = attack(s, "dummy")
    assert "strikes back" not in out
    assert s.resources["hp"].current == max_hp  # unhurt: backward compatible


def test_a_defeated_npc_does_not_counter():
    s = _fighter()
    _spawn_hostile(atk=99, hp=1)  # a huge atk, but it dies to the first blow
    max_hp = s.resources["hp"].maximum
    out = attack(s, "brawler")
    assert "strikes back" not in out
    assert s.resources["hp"].current == max_hp  # a corpse never counters


def test_a_fallen_player_is_restored_safely():
    s = _fighter()  # a vanguard: no Engineer reaction
    _spawn_hostile(atk=9999, hp=50)  # its counter empties the player's HP
    out = attack(s, "brawler")
    assert "Emergency Repair" not in out  # only an Engineer gets the reaction
    assert "wake restored at full health" in out
    assert s.resources["hp"].is_full  # never a broken state
    assert s.location == "courtyard"  # restored in place


def test_an_engineer_emergency_repairs_out_of_a_killing_blow():
    s = _fighter("engineer")
    _spawn_hostile(atk=9999, hp=50)  # a counter that would fell anyone else
    out = attack(s, "brawler")
    assert "Emergency Repair triggers" in out  # the Engineer's reaction fired
    assert s.resources["hp"].current > 0  # pulled back from the fall
    assert "wake restored" not in out  # never needed the training-ground failsafe
    assert "emergency_repair" in s.cooldowns  # and armed its cooldown


def test_emergency_repair_fires_once_then_cools_down():
    s = _fighter("engineer")
    _spawn_hostile(atk=9999, hp=9999)  # survives every blow and keeps countering
    first = attack(s, "brawler")
    assert "Emergency Repair triggers" in first  # fires the first time
    second = attack(s, "brawler")
    assert "Emergency Repair" not in second  # on cooldown now
    assert "wake restored" in second  # so the failsafe catches this fall instead


def test_counterattack_flows_through_the_engine_tick():
    from forge import handle_command

    s = _fighter()
    _spawn_hostile(atk=4, hp=50)
    out = handle_command(s, "attack brawler")
    assert "strikes back for 4" in out


def test_the_seeded_gate_boss_is_a_real_fight():
    """The spiral-ascent Coilwarden is wired for combat: reachable in play, and it hits back."""
    from parts.seed import SEEDS_ROOT, load_npcs

    boss = load_npcs(SEEDS_ROOT / "spiral-ascent" / "npcs.yaml")["coilwarden"]
    npcs.NPCS["coilwarden"] = boss  # its seed location is gate_chamber
    s = _fighter(location="gate_chamber")
    max_hp = s.resources["hp"].maximum
    out = attack(s, "coilwarden")
    assert "strikes back for 8" in out  # the seeded atk engages through the attack path
    assert s.resources["hp"].current == max_hp - 8  # the player took a real blow


def test_defeating_an_enemy_awards_jp():
    s = _fighter("engineer")
    out = ""
    for _ in range(10):  # strike until the dummy collapses
        out = attack(s, "dummy")
        if "reassembles" in out:
            break
    assert "JP (Engineer)" in out  # the kill line reports the JP award
    assert s.job_progress["engineer"].jp > 0


def test_defeating_an_enemy_awards_tp():
    s = _fighter("engineer")
    out = ""
    for _ in range(10):
        out = attack(s, "dummy")
        if "reassembles" in out:
            break
    assert "TP (Engineer)" in out
    assert s.job_progress["engineer"].tp > 0
