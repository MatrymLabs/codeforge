"""End-to-end play smoke: the proactive-combat lifecycle through the engine tick.

The Convergence Review (2026-07-17) found no test owned "does the game actually play?" -
the proactive-NPC engine was green in unit tests yet dark in every seed, so a stranger
running the game never met it. This smoke drives the REAL armed aethryn boss (loaded from
its seed, so the `aggressive: true` seed change is exercised, not a synthetic fixture) through
`handle_command`: enter the scene and read the danger, take an unprovoked blow on the beat,
fight back, and be released by the leash. It asserts the loop plays and never leaves a broken
state - the last inch the board said was missing.
"""

import copy

import pytest

from parts import npcs
from parts.aggression import LEASH
from parts.jobs import bind_calling
from parts.seed import SEEDS_ROOT, load_npcs
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_world():
    npcs_snap = copy.deepcopy(npcs.NPCS)
    SESSIONS.clear()
    yield
    npcs.NPCS.clear()
    npcs.NPCS.update(npcs_snap)
    SESSIONS.clear()


def _fighter_at(location: str) -> Session:
    s = Session(player_id="matrym", location=location)
    SESSIONS["matrym"] = s
    bind_calling(s, "vanguard")
    return s


def _place_the_real_boss(location: str) -> None:
    """Load the aethryn Cinder-Wight from its seed (proving the seed's aggressive flag) and
    stand it in a room the default world can render."""
    boss = load_npcs(SEEDS_ROOT / "aethryn" / "npcs.yaml")["cinder_wight"]
    assert boss["aggressive"] is True  # the seed change is live, not just the engine
    boss["location"] = location
    npcs.NPCS["cinder_wight"] = boss


def test_a_stranger_can_play_the_proactive_combat_loop():
    from forge import handle_command

    s = _fighter_at("courtyard")
    _place_the_real_boss("courtyard")
    max_hp = s.resources["hp"].maximum

    # Enter the scene: the room telegraphs the danger AND the foe strikes on the beat.
    scene = handle_command(s, "look")
    assert "looks hostile" in scene  # fair warning: the danger is legible before the blow
    assert "lunges for 7" in scene  # the unprovoked strike landed on the world beat
    assert s.resources["hp"].current < max_hp

    # Fight back: the player's blow lands and the foe answers exactly once (open-strike, no double).
    trade = handle_command(s, "attack wight")
    assert "You strike the Cinder-Wight" in trade
    assert "lunges for 7" in trade
    assert "strikes back" not in trade

    # Stop fighting: the leash releases the foe within its window, and the player is never
    # left dead - the failsafe catches any fatal beat en route.
    released = False
    for _ in range(LEASH + 1):
        out = handle_command(s, "look")
        assert s.resources["hp"].current > 0  # never a broken state, beat after beat
        if "breaks off its assault" in out:
            released = True
            break
    assert released  # the soft-lock exit fired: the fight ends, badly-but-safely
