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
from parts.world.items import ITEMS, items_in
from parts.world.npcs import NPCS, npcs_in, reindex_npcs
from parts.world.session import SESSIONS, Session
from parts.world.world import WORLD, render_room


@pytest.fixture(autouse=True)
def fresh_sessions():
    SESSIONS.clear()
    events.SHUTDOWN["hook"] = None
    cw._DRAFTS.clear()
    # Any NPC/item a publish adds is removed after, so the shared world stays clean.
    npc_snapshot, item_snapshot = set(NPCS), set(ITEMS)
    yield
    for label in set(NPCS) - npc_snapshot:
        del NPCS[label]
    for label in set(ITEMS) - item_snapshot:
        del ITEMS[label]
    reindex_npcs()
    cw._DRAFTS.clear()
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


# --- the change buffer + NPC Studio (first mutating tool) ---------------------------------------
def _real_room() -> str:
    return next(iter(WORLD))


def test_create_stages_an_npc_and_preview_shows_it_but_the_world_is_untouched():
    room = _real_room()
    owner = _seat("root", "owner", location=cw.NPC_STUDIO)
    out = handle_command(owner, f"create npc Old Marta at {room}")
    assert "Staged" in out and "Old Marta" in out
    # It is only STAGED: nothing is live in the room yet.
    assert not any(NPCS[n]["name"] == "Old Marta" for n in npcs_in(room))
    preview = handle_command(owner, "preview")
    assert "Old Marta" in preview and "not yet live" in preview


def test_publish_at_the_portal_makes_the_staged_npc_live():
    room = _real_room()
    owner = _seat("root", "owner", location=cw.NPC_STUDIO)
    handle_command(owner, f"create npc Old Marta at {room}")
    owner.location = cw.PUBLISHING_PORTAL  # walk to the portal
    out = handle_command(owner, "publish")
    assert "Published" in out
    # Now she really stands in the room, and the draft is empty.
    assert any(NPCS[n]["name"] == "Old Marta" for n in npcs_in(room))
    assert "Nothing is staged" in handle_command(owner, "preview")


def test_create_refuses_an_unreal_room_and_stages_nothing():
    owner = _seat("root", "owner", location=cw.NPC_STUDIO)
    out = handle_command(owner, "create npc Ghost at nowhere_at_all")
    assert "no room labelled" in out
    assert "Nothing is staged" in handle_command(owner, "preview")


def test_create_is_owner_and_studio_gated():
    room = _real_room()
    # A player in the studio cannot create...
    player = _seat("nosy", "player", location=cw.NPC_STUDIO)
    assert "cannot make a person" in handle_command(player, f"create npc X at {room}")
    # ...and the owner cannot create from the wrong station.
    owner = _seat("root", "owner", location=cw.CREATOR_WORKSHOP)
    assert "at the NPC Studio" in handle_command(owner, f"create npc X at {room}")


def test_publish_only_works_at_the_publishing_portal():
    room = _real_room()
    owner = _seat("root", "owner", location=cw.NPC_STUDIO)
    handle_command(owner, f"create npc Senna at {room}")
    # Standing in the studio, publish sends the owner to the portal instead of firing.
    assert "Publishing Portal" in handle_command(owner, "publish")
    assert not any(NPCS[n]["name"] == "Senna" for n in npcs_in(room))


def test_rollback_discards_the_draft_without_publishing():
    room = _real_room()
    owner = _seat("root", "owner", location=cw.NPC_STUDIO)
    handle_command(owner, f"create npc Doomed at {room}")
    owner.location = cw.PUBLISHING_PORTAL
    out = handle_command(owner, "rollback")
    assert "Rolled back" in out
    assert not any(NPCS[n]["name"] == "Doomed" for n in npcs_in(room))
    assert "Nothing is staged" in handle_command(owner, "preview")


def test_the_full_create_loop_through_the_tick():
    # The whole beginner journey: walk into the world's spawn, into the studio, create, publish.
    room = _real_room()
    owner = _seat("root", "owner", location=cw.NPC_STUDIO)
    handle_command(owner, f"create npc Torvald the Smith at {room}")
    handle_command(owner, "go hall")
    handle_command(owner, "go publish")  # the Publishing Portal
    assert owner.location == cw.PUBLISHING_PORTAL
    handle_command(owner, "publish")
    assert any(NPCS[n]["name"] == "Torvald the Smith" for n in npcs_in(room))


def test_the_item_forge_creates_and_publishes_an_item():
    room = _real_room()
    owner = _seat("root", "owner", location=cw.ITEM_FORGE)
    out = handle_command(owner, f"create item Rusty Lantern at {room}")
    assert "Staged" in out and "Rusty Lantern" in out
    assert not any(ITEMS[i]["name"] == "Rusty Lantern" for i in items_in(f"room:{room}"))
    owner.location = cw.PUBLISHING_PORTAL
    handle_command(owner, "publish")
    assert any(ITEMS[i]["name"] == "Rusty Lantern" for i in items_in(f"room:{room}"))


def test_creating_an_item_is_gated_to_the_item_forge():
    room = _real_room()
    owner = _seat("root", "owner", location=cw.NPC_STUDIO)  # wrong station for an item
    assert "at the Item Forge" in handle_command(owner, f"create item Torch at {room}")


def test_create_rejects_an_unknown_kind():
    owner = _seat("root", "owner", location=cw.NPC_STUDIO)
    assert "npc or an item" in handle_command(owner, "create dragon Smaug at nowhere")
