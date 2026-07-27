"""Test twin for parts/world/creator_workshop.py -- the Creator's Workshop barrier.

Gates the prompt's absolutes: every world carries a discoverable Grand Library and a CONCEALED
Creator's Door onto an isolated Workshop instance; ONLY the authenticated Seed Owner crosses, and
everyone else -- whether they name the door or try to teleport past it -- meets the exact barrier
refusal. Covers both the unit placement/logic AND the engine tick (a barrier is not real until
handle_command proves it): acceptance (owner enters) and refusal (player and wizard turned back).
"""

import pytest

from forge import handle_command
from parts.world import creator_workshop as cw
from parts.world import events
from parts.world.session import SESSIONS, Session
from parts.world.world import WORLD, render_room


@pytest.fixture(autouse=True)
def fresh_sessions():
    SESSIONS.clear()
    events.SHUTDOWN["hook"] = None
    yield
    SESSIONS.clear()
    events.SHUTDOWN["hook"] = None


def _seat(name: str, rank: str = "player", location: str = cw.GRAND_LIBRARY) -> Session:
    s = Session(player_id=name, location=location, named=True, rank=rank)
    SESSIONS[name] = s
    return s


# --- placement (unit) ---------------------------------------------------------------------------
def test_install_places_the_library_and_workshop_and_links_the_spawn():
    world = {"spawn": {"name": "Spawn", "desc": "start", "exits": {}}}
    cw.install_workshop(world)
    assert cw.GRAND_LIBRARY in world and cw.CREATOR_WORKSHOP in world
    # The Library is discoverable from the spawn...
    assert world["spawn"]["exits"]["library"] == cw.GRAND_LIBRARY
    # ...and leads back out; the Workshop hall opens onto the Library via `out`.
    assert world[cw.GRAND_LIBRARY]["exits"]["out"] == "spawn"
    assert world[cw.CREATOR_WORKSHOP]["exits"]["out"] == cw.GRAND_LIBRARY


def test_install_builds_every_station_room_off_the_hall():
    world = {"spawn": {"name": "Spawn", "desc": "start", "exits": {}}}
    cw.install_workshop(world)
    hall = world[cw.CREATOR_WORKSHOP]["exits"]
    for station in cw.STATIONS:
        assert station.label in world, f"missing station room {station.label}"
        assert hall[station.noun] == station.label  # the hall opens onto it by its noun
        # Every station returns to the hall (both `hall` and `out`), and lives behind the barrier.
        assert world[station.label]["exits"] == {
            "hall": cw.CREATOR_WORKSHOP,
            "out": cw.CREATOR_WORKSHOP,
        }
        assert cw.is_workshop_room(station.label)


def test_install_is_idempotent():
    world = {"spawn": {"name": "Spawn", "desc": "start", "exits": {}}}
    cw.install_workshop(world)
    before = dict(world[cw.CREATOR_WORKSHOP]["exits"])
    cw.install_workshop(world)  # a second call must not double-place or raise
    assert world[cw.CREATOR_WORKSHOP]["exits"] == before


def test_install_refuses_an_empty_world():
    with pytest.raises(cw.WorkshopError, match="empty world"):
        cw.install_workshop({})


def test_the_creators_door_is_concealed_from_the_library_exits():
    # The door is named, never listed: it must NOT appear among the Grand Library's visible exits,
    # so a player cannot discover, observe, or reveal it.
    exits = WORLD[cw.GRAND_LIBRARY]["exits"]
    assert cw.CREATOR_WORKSHOP not in exits.values()
    assert "door" not in exits
    assert cw.CREATOR_WORKSHOP not in render_room(cw.GRAND_LIBRARY)


# --- the barrier (logic) ------------------------------------------------------------------------
def test_door_destination_only_fires_in_the_library_for_the_door_word():
    assert cw.door_destination(cw.GRAND_LIBRARY, "door") == cw.CREATOR_WORKSHOP
    assert cw.door_destination(cw.GRAND_LIBRARY, "north") is None
    assert cw.door_destination("some_field", "door") is None


def test_only_the_owner_is_the_seed_owner():
    assert cw.is_seed_owner(_seat("o", "owner"))
    assert not cw.is_seed_owner(_seat("w", "wizard"))
    assert not cw.is_seed_owner(_seat("p", "player"))


# --- the barrier (engine tick) ------------------------------------------------------------------
def test_the_owner_crosses_the_barrier_into_the_workshop():
    owner = _seat("root", "owner")
    out = handle_command(owner, "go door")
    assert owner.location == cw.CREATOR_WORKSHOP
    assert "Creator's Workshop" in out


def test_a_bare_door_word_also_crosses_for_the_owner():
    owner = _seat("root", "owner")
    handle_command(owner, "door")
    assert owner.location == cw.CREATOR_WORKSHOP


def test_a_player_is_refused_at_the_barrier_and_does_not_move():
    player = _seat("nosy", "player")
    out = handle_command(player, "go door")
    assert out.startswith(cw.barrier_refusal())
    assert player.location == cw.GRAND_LIBRARY  # turned back, unmoved


def test_a_wizard_cannot_teleport_past_the_barrier():
    start = "veridia" if "veridia" in WORLD else next(iter(WORLD))
    wiz = _seat("mage", "wizard", location=start)
    out = handle_command(wiz, f"@teleport {cw.CREATOR_WORKSHOP}")
    assert cw.barrier_refusal() in out
    assert wiz.location != cw.CREATOR_WORKSHOP


def test_the_owner_may_teleport_into_the_workshop():
    owner = _seat("root", "owner", location=next(iter(WORLD)))
    handle_command(owner, f"@teleport {cw.CREATOR_WORKSHOP}")
    assert owner.location == cw.CREATOR_WORKSHOP


def test_the_owner_can_walk_back_out_to_the_library():
    owner = _seat("root", "owner", location=cw.CREATOR_WORKSHOP)
    handle_command(owner, "go out")
    assert owner.location == cw.GRAND_LIBRARY


def test_the_owner_can_walk_the_stations_and_return_to_the_hall():
    owner = _seat("root", "owner", location=cw.CREATOR_WORKSHOP)
    npc = next(s for s in cw.STATIONS if s.label == "npc_studio")
    out = handle_command(owner, f"go {npc.noun}")
    assert owner.location == "npc_studio" and "NPC Studio" in out
    handle_command(owner, "go hall")
    assert owner.location == cw.CREATOR_WORKSHOP


def test_a_wizard_cannot_teleport_into_a_station_either():
    start = "veridia" if "veridia" in WORLD else next(iter(WORLD))
    wiz = _seat("mage", "wizard", location=start)
    out = handle_command(wiz, "@teleport npc_studio")
    assert cw.barrier_refusal() in out
    assert wiz.location != "npc_studio"


# --- the Planning Table survey (first live station tool) ----------------------------------------
def test_the_owner_surveys_the_world_at_the_planning_table():
    owner = _seat("root", "owner", location=cw.PLANNING_TABLE)
    out = handle_command(owner, "survey")
    assert "The Planning Table" in out
    assert "Rooms:" in out and "Zones:" in out
    # It reads the world's scale against a Seed Package deployment tier (the two campaigns compose).
    assert "roughly a" in out


def test_survey_reports_the_real_live_room_count():
    owner = _seat("root", "owner", location=cw.PLANNING_TABLE)
    out = handle_command(owner, "survey")
    assert f"{len(WORLD):,}" in out  # the honest live count, not a canned number


def test_survey_shows_nothing_to_a_non_owner_or_away_from_the_table():
    # An owner standing elsewhere sees nothing to survey (the tool is station-gated)...
    owner_away = _seat("root", "owner", location=cw.CREATOR_WORKSHOP)
    assert "nothing here to survey" in handle_command(owner_away, "survey")
    # ...and a mere player never sees the world's shape, wherever they stand.
    player = _seat("nosy", "player", location=cw.PLANNING_TABLE)
    assert "nothing here to survey" in handle_command(player, "survey")


# --- the Statistics Wall live-activity tool -----------------------------------------------------
def test_the_owner_reads_live_activity_at_the_statistics_wall():
    owner = _seat("root", "owner", location=cw.STATISTICS_WALL)
    _seat("hero", "player", location=next(iter(WORLD)))
    out = handle_command(owner, "activity")
    assert "The Statistics Wall" in out
    assert "Players online:" in out
    assert "Hero" in out  # the live roster, by display name


def test_activity_shows_nothing_to_a_non_owner_or_away_from_the_wall():
    owner_away = _seat("root", "owner", location=cw.CREATOR_WORKSHOP)
    assert "shows you nothing" in handle_command(owner_away, "activity")
    player = _seat("nosy", "player", location=cw.STATISTICS_WALL)
    assert "shows you nothing" in handle_command(player, "activity")
