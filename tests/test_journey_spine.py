"""End-to-end JOURNEY gate: the Forgeward Road spine, walked to the endgame via waystone travel.

The keel mission is a world that plays end to end. The engine had the two halves but not the seam
between them: the campaign SPINE (`kernel/world/spine.py`) is a main-road quest whose beats fire on
ENTERING each zone hub in level order, and the WAYSTONE network (`kernel/world/travel.py`) is how a
player crosses a million-room world -- yet `travel()` teleported the player without firing the
`on_enter` beat, so the main road never advanced when you crossed the world the intended way. The
through-line was dark exactly where a real playthrough lives.

This drives the REAL modules composed -- forge the spine for a controlled multi-zone world, then
carry a fresh hero hub-to-hub with the real `travel()` -- and asserts the campaign advances one leg
per arrival, all the way to the endgame reward. It is the smallest honest proof that a character can
be made and walked from the starting valley to the endgame; the live-TCP full-world walk is the
promotion step (scripts/e2e_smoke.py).

Acceptance: each leg advances in order and the endgame terminal + XP reward fire on the last hub.
Refusal: leaping straight to the endgame hub does NOT skip the unwalked legs (no cheesing the road).
"""

from __future__ import annotations

import copy

import pytest

from kernel.world import quest as questmod
from kernel.world.jobs import bind_calling
from kernel.world.session import Session
from kernel.world.spine import forge_spine
from kernel.world.travel import travel

# A four-zone world in level order -- the aethryn shape in miniature. Each zone's hub room is also
# its waystone, exactly as the real seed emits it (waystones.yaml keys == zone hub room-ids).
_ZONES = [
    {"name": "Veridia", "rooms": ["veridia"], "level_min": 1, "level_max": 30},
    {"name": "Caeloria", "rooms": ["caeloria"], "level_min": 30, "level_max": 60},
    {"name": "Frostspire Peaks", "rooms": ["frostspire_peaks"], "level_min": 60, "level_max": 90},
    {"name": "Zhaar Desert", "rooms": ["zhaar_desert"], "level_min": 80, "level_max": 130},
]
_HUBS_IN_ORDER = ["veridia", "caeloria", "frostspire_peaks", "zhaar_desert"]


@pytest.fixture
def waystone_network():
    """Fold the Forgeward Road for the controlled world into the engine, isolated from the loaded
    seed's own quests, and hand back the matching waystone manifest. Restored after the test."""
    q_snap = dict(questmod._QUESTS)
    routes_snap = copy.deepcopy(questmod._EVENT_ROUTES)
    runs_snap = copy.deepcopy(questmod._RUNS)

    spec = forge_spine(_ZONES)
    assert spec is not None, "four zones must lay a road"
    questmod.register_specs([spec])
    stones = {z["rooms"][0]: {"name": z["name"], "level": int(z["level_min"])} for z in _ZONES}
    try:
        yield stones
    finally:
        questmod._QUESTS.clear()
        questmod._QUESTS.update(q_snap)
        questmod._EVENT_ROUTES.clear()
        questmod._EVENT_ROUTES.update(routes_snap)
        questmod._RUNS.clear()
        questmod._RUNS.update(runs_snap)


def _wayfarer(player_id: str) -> Session:
    """A fresh hero standing at the first waystone, with a calling (so the endgame XP reward can
    actually land) and a full purse (the fare sink is not what this gate measures)."""
    hero = Session(player_id=player_id, location="veridia")
    bind_calling(hero, "vanguard")  # gives real stats/resources -> award_xp fires on the endgame
    hero.coins = 10_000_000
    return hero


def test_the_forgeward_road_walks_from_the_valley_to_the_endgame(waystone_network):
    stones = waystone_network
    hero = _wayfarer("pathfinder")
    start_xp = hero.xp

    # Leg by leg: arriving at each next hub via the REAL travel() advances the main road one beat,
    # and the spine's label for the new leg rides back on the arrival text.
    to_caeloria = travel(hero, "caeloria", stones)
    assert "carried to the Caeloria waystone" in to_caeloria  # the hop happened
    assert "reached Caeloria" in to_caeloria  # ...and the spine ticked leg 1 on arrival

    to_frostspire = travel(hero, "frostspire_peaks", stones)
    assert "reached Frostspire Peaks" in to_frostspire  # leg 2

    endgame = travel(hero, "zhaar_desert", stones)  # the final hub: terminal + reward
    assert "carried to the Zhaar Desert waystone" in endgame
    assert "walked the Forgeward Road" in endgame  # the endgame terminal fired
    assert "Aethryn is yours to roam" in endgame

    # The payoff actually landed on the sheet (award_xp scales with the endgame zone's cap: 130*40).
    assert "You gain 5200 XP" in endgame  # 130 * 40, the whole-world reward
    assert hero.xp - start_xp == 130 * 40


def test_leaping_to_the_endgame_hub_does_not_skip_the_unwalked_road(waystone_network):
    stones = waystone_network
    hero = _wayfarer("skipper")

    # A rich hero can PAY to leap straight to the endgame waystone -- but the campaign is walked,
    # not bought: arriving there without walking the legs before it must NOT complete the road. The
    # quest engine refuses the out-of-order beat.
    leap = travel(hero, "zhaar_desert", stones)
    assert "carried to the Zhaar Desert waystone" in leap  # travel itself still works
    assert "walked the Forgeward Road" not in leap  # the road is NOT complete
    assert "Aethryn is yours to roam" not in leap
    # and no phantom reward for a road never walked
    assert "you gain" not in leap.lower()
    assert hero.xp == 0
