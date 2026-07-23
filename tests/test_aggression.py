"""Test twin for parts/world/aggression.py -- proactive NPCs that strike on the world beat.

Acceptance: an aggressive NPC sharing the player's room opens with a strike each tick,
reachable through the engine tick (handle_command), and lands exactly one blow per beat
even when the player attacks it (open-strike, never open + counter). Refusal: a reactive
NPC never opens; an aggressive NPC in another room is no threat; a player with no calling
is left alone. The training-ground failsafe still catches a fatal opening blow.
"""

import copy

import pytest

from parts.world import npcs
from parts.world.aggression import LEASH, menace
from parts.world.combat import open_strike
from parts.world.jobs import bind_calling
from parts.world.seed import Npc
from parts.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_world():
    # Restore in place (clear + update, never rebind): aggression/combat hold
    # `from parts.world.npcs import NPCS`, so rebinding npcs.NPCS would strand that alias.
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


def _spawn_aggressor(
    label: str = "reaver",
    location: str = "courtyard",
    atk: int = 5,
    hp: int = 50,
    aggressive: bool = True,
) -> str:
    """Place a proactive NPC in a room. Written to the aliased registry; the fixture cleans up."""
    foe: Npc = {
        "name": f"the {label}",
        "keywords": [label],
        "location": location,
        "dialogue": ["..."],
        "next_line": 0,
        "hp": hp,
        "hp_now": hp,
        "xp": 10,
        "atk": atk,
        "aggressive": aggressive,
    }
    npcs.NPCS[label] = foe
    return label


# --- acceptance --------------------------------------------------------------------------------


def test_an_aggressive_npc_opens_with_a_strike_on_the_beat():
    s = _fighter()
    _spawn_aggressor(atk=5, hp=50)
    max_hp = s.resources["hp"].maximum
    out = menace(s)
    assert "The reaver lunges for 5" in out
    assert s.resources["hp"].current == max_hp - 5  # exact, deterministic


def test_it_strikes_through_the_engine_tick():
    from forge import handle_command

    s = _fighter()
    _spawn_aggressor(atk=4, hp=50)
    max_hp = s.resources["hp"].maximum
    out = handle_command(s, "look")  # any tick is a world beat; the NPC does not wait
    assert "lunges for 4" in out
    assert s.resources["hp"].current == max_hp - 4


def test_an_aggressive_npc_strikes_once_per_tick_not_twice():
    """Attacking an aggressive NPC yields ONE blow (its open-strike on the beat), never a
    counter AND an open-strike in the same tick."""
    from forge import handle_command

    s = _fighter()
    _spawn_aggressor(atk=6, hp=50)
    max_hp = s.resources["hp"].maximum
    out = handle_command(s, "attack reaver")
    assert "You strike the reaver" in out  # the player's blow landed
    assert "lunges for 6" in out  # the NPC opened on the beat
    assert "strikes back" not in out  # but did NOT also counter
    assert s.resources["hp"].current == max_hp - 6  # exactly one NPC blow, not two


def test_the_leash_releases_a_foe_that_is_never_answered():
    """A player who cannot win but stops fighting is not soft-locked: after LEASH unanswered
    beats the foe breaks off and strikes no more (the engineered exit the failsafe lacks)."""
    s = _fighter()
    _spawn_aggressor(atk=2, hp=50)
    max_hp = s.resources["hp"].maximum
    out = ""
    for _ in range(LEASH):  # LEASH beats: (LEASH-1) strikes, then the break-off
        out = menace(s)
    assert "breaks off" in out  # the leash snapped taut on the final beat
    assert s.resources["hp"].current == max_hp - 2 * (LEASH - 1)  # only the pre-leash blows landed
    assert menace(s) == ""  # broken off: silent until re-provoked


def test_answering_a_foe_re_engages_the_leash():
    """A real fight keeps the foe engaged: a player strike resets the leash to zero."""
    s = _fighter()
    _spawn_aggressor(atk=2, hp=50)
    from forge import handle_command

    for _ in range(LEASH - 1):  # climb the leash without answering
        menace(s)
    handle_command(s, "attack reaver")  # answer it: resets the count
    out = menace(s)
    assert "lunges" in out  # re-engaged, striking again
    assert "breaks off" not in out


# --- refusal / hostile -------------------------------------------------------------------------


def test_a_reactive_npc_never_opens():
    s = _fighter()
    _spawn_aggressor(atk=5, hp=50, aggressive=False)  # armed, but reactive-only
    max_hp = s.resources["hp"].maximum
    assert menace(s) == ""
    assert s.resources["hp"].current == max_hp  # untouched: it waits to be hit


def test_an_aggressive_npc_in_another_room_is_no_threat():
    s = _fighter(location="courtyard")
    _spawn_aggressor(location="library")  # a room away
    max_hp = s.resources["hp"].maximum
    assert menace(s) == ""
    assert s.resources["hp"].current == max_hp


def test_a_player_without_a_calling_is_not_engaged():
    s = Session(player_id="matrym", location="courtyard")  # no bind_calling: stats is None
    SESSIONS["matrym"] = s
    _spawn_aggressor(atk=99)
    assert menace(s) == ""  # you cannot bleed someone who has not entered the fight


def test_a_felled_player_is_restored_by_the_failsafe():
    s = _fighter()  # a vanguard: no Engineer reaction
    _spawn_aggressor(atk=9999, hp=50)  # its opening blow would empty the player's HP
    out = menace(s)
    assert "wake restored at full health" in out
    assert s.resources["hp"].is_full  # never a broken state
    assert s.location == "courtyard"  # restored in place


def test_a_second_aggressor_never_re_fells_a_restored_player():
    """Multi-aggressor blast is bounded: the beat stops after the first blow that fells the
    player, so a failsafe-restored player is not immediately re-felled inside the same tick."""
    s = _fighter()
    _spawn_aggressor(label="wight", atk=9999, hp=50)
    _spawn_aggressor(label="brute", atk=9999, hp=50)  # a second lethal foe in the same room
    out = menace(s)
    assert out.count("wake restored") == 1  # exactly one near-death this beat, not two
    assert s.resources["hp"].is_full  # restored, and not struck down again


def test_open_strike_from_a_passive_npc_lands_nothing():
    """Belt-and-suspenders: even if combat is asked to open a strike for a passive NPC
    (atk 0), it lands nothing -- the seed forbids aggressive+atk0, but the engine is safe."""
    s = _fighter()
    passive = npcs.NPCS["training_dummy"]  # carries no atk
    max_hp = s.resources["hp"].maximum
    assert open_strike(s, passive) == ""
    assert s.resources["hp"].current == max_hp
