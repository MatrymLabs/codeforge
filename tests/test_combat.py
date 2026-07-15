"""Test twin for parts/combat.py -- deterministic training-loop math."""

import copy

import pytest

from parts import npcs
from parts.combat import attack, award_jp, award_xp, strike_power
from parts.events import bind_echo, unbind_echo
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


def test_level_up_crosses_the_locked_curve_and_grows_resources():
    s = _fighter()  # vanguard: sta 12, mag 4; level 2 needs 75 XP
    hp_before = s.resources["hp"].maximum
    message = award_xp(s, 80)
    assert "LEVEL UP" in message
    assert s.level == 2
    assert s.resources["hp"].maximum == hp_before + 4 + 12 // 4  # mk1 formula
    assert s.resources["hp"].is_full


def test_the_room_witnesses_the_level_up():
    s = _fighter()
    b = Session(player_id="bystander", location="courtyard")
    SESSIONS["bystander"] = b
    heard: list[str] = []
    bind_echo("bystander", heard.append)
    award_xp(s, 80)
    assert "Matrym has reached level 2!" in heard
    unbind_echo("bystander")


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
    s = _fighter()
    _spawn_hostile(atk=9999, hp=50)  # its counter empties the player's HP
    out = attack(s, "brawler")
    assert "wake restored at full health" in out
    assert s.resources["hp"].is_full  # never a broken state
    assert s.location == "courtyard"  # restored in place


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


def test_awards_never_drain_progress_on_a_negative_amount():
    """Defense in depth: an award is a gain, never a loss - a negative amount (should be impossible
    after the loader refuses negative NPC xp) is clamped to zero, not subtracted from the player."""
    from parts.combat import award_tp

    s = _fighter("engineer")
    s.xp = 100
    award_jp(s, 50)
    award_tp(s, 40)
    jp_before = s.job_progress["engineer"].jp
    tp_before = s.job_progress["engineer"].tp
    award_xp(s, -1000)
    award_jp(s, -1000)
    award_tp(s, -1000)
    assert s.xp == 100  # not drained
    assert s.job_progress["engineer"].jp == jp_before
    assert s.job_progress["engineer"].tp == tp_before


def test_jp_accrues_to_the_active_job_and_levels_it():
    s = _fighter("engineer")
    # cumulative JP to reach job level 2 is 60 (20 for lvl 1 + 40 for lvl 2).
    out = award_jp(s, 60)
    assert s.job_progress["engineer"].jp == 60
    assert s.job_progress["engineer"].job_level == 2  # crossed the threshold
    assert "advances to job level 2" in out


def test_a_small_jp_gain_accrues_without_leveling():
    s = _fighter("engineer")
    award_jp(s, 10)
    assert s.job_progress["engineer"].jp == 10
    assert s.job_progress["engineer"].job_level == 1  # below the level-2 threshold


def test_a_seat_with_no_active_job_earns_no_jp():
    s = Session(player_id="matrym")  # no calling taken
    assert award_jp(s, 50) == ""


def test_earned_jp_persists_for_a_named_character():
    from parts.characters import load_character, restore_character

    s = Session(player_id="matrym", location="courtyard", named=True)
    SESSIONS["matrym"] = s
    bind_calling(s, "engineer")
    award_jp(s, 45)  # a named seat persists on award
    fresh = Session(player_id="matrym")
    record = load_character("matrym")
    assert record is not None
    restore_character(fresh, record)
    assert fresh.job_progress["engineer"].jp == 45


def test_jp_only_touches_the_active_job():
    s = _fighter("engineer")
    from parts.job_progress import JobProgress

    s.job_progress["scholar"] = JobProgress("scholar", job_level=5, jp=200)
    award_jp(s, 30)
    assert s.job_progress["scholar"] == JobProgress("scholar", job_level=5, jp=200)  # untouched


def test_defeating_an_enemy_awards_jp():
    s = _fighter("engineer")
    out = ""
    for _ in range(10):  # strike until the dummy collapses
        out = attack(s, "dummy")
        if "reassembles" in out:
            break
    assert "JP (Engineer)" in out  # the kill line reports the JP award
    assert s.job_progress["engineer"].jp > 0


def test_tp_accrues_to_the_active_job():
    s = _fighter("engineer")
    from parts.combat import award_tp

    award_tp(s, 120)
    assert s.job_progress["engineer"].tp == 120


def test_no_active_job_earns_no_tp():
    from parts.combat import award_tp

    assert award_tp(Session(player_id="matrym"), 50) == ""


def test_earned_tp_persists_for_a_named_character():
    from parts.characters import load_character, restore_character
    from parts.combat import award_tp

    s = Session(player_id="matrym", location="courtyard", named=True)
    SESSIONS["matrym"] = s
    bind_calling(s, "engineer")
    award_tp(s, 75)
    fresh = Session(player_id="matrym")
    record = load_character("matrym")
    assert record is not None
    restore_character(fresh, record)
    assert fresh.job_progress["engineer"].tp == 75


def test_defeating_an_enemy_awards_tp():
    s = _fighter("engineer")
    out = ""
    for _ in range(10):
        out = attack(s, "dummy")
        if "reassembles" in out:
            break
    assert "TP (Engineer)" in out
    assert s.job_progress["engineer"].tp > 0
