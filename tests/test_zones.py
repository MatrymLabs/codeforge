"""Test twin for parts/world/zones.py + seed.load_zones -- areas and the beat-driven reset loop.

Acceptance: a valid zones pack groups rooms; the scheduler advances on the world beat and comes
due per its mode. Refusal: a malformed zone fails loud rather than booting a broken area.
"""

import pytest

import parts.world.seed as seed  # reference SeedError via the module: other suites importlib.reload
import parts.world.zones as zones  # parts.world.seed, so a class imported at collection won't match
from forge import handle_command
from parts.world import items
from parts.world.seed import SEEDS_ROOT, Item, Zone, load_rooms, load_zones
from parts.world.session import Session
from parts.world.world import START_ROOM
from parts.world.zones import area_line, tick_zones, zone_of, zones_due

KNOWN = {"a", "b", "c"}


def _write(tmp_path, text: str):
    path = tmp_path / "zones.yaml"
    path.write_text(text)
    return path


# --- loader: acceptance -----------------------------------------------------------------
def test_a_valid_zone_groups_its_rooms(tmp_path):
    path = _write(
        tmp_path,
        "coast:\n  name: The Coast\n  rooms: [a, b]\n  reset_mode: always\n  beats_between: 5\n",
    )
    zmap = load_zones(path, KNOWN)
    assert zmap["coast"]["name"] == "The Coast"
    assert zmap["coast"]["rooms"] == ["a", "b"]
    assert zmap["coast"]["reset_mode"] == "always"
    assert zmap["coast"]["beats_between"] == 5


def test_an_absent_zones_file_is_empty_not_an_error(tmp_path):
    assert load_zones(tmp_path / "nope.yaml", KNOWN) == {}


def test_zone_fields_default_when_omitted(tmp_path):
    path = _write(tmp_path, "wilds:\n  rooms: [c]\n")
    z = load_zones(path, KNOWN)["wilds"]
    assert z["reset_mode"] == "never"  # grouping only, unless a mode is declared
    assert z["beats_between"] == 10
    assert z["name"] == "Wilds"


def test_the_shipped_aethryn_seed_declares_valid_areas():
    aethryn = SEEDS_ROOT / "aethryn"
    rooms = set(load_rooms(aethryn / "rooms.yaml"))
    zmap = load_zones(aethryn / "zones.yaml", rooms)
    assert zmap, "aethryn should ship areas"
    claimed = [room for zone in zmap.values() for room in zone["rooms"]]
    assert len(claimed) == len(set(claimed))  # no room claimed by two areas
    assert all(room in rooms for room in claimed)  # every member room exists


# --- loader: refusal (fail loud) --------------------------------------------------------
def test_a_zone_naming_a_missing_room_is_refused(tmp_path):
    path = _write(
        tmp_path, "coast:\n  rooms: [a, nowhere]\n  reset_mode: never\n  beats_between: 1\n"
    )
    with pytest.raises(seed.SeedError, match="does not exist"):
        load_zones(path, KNOWN)


def test_a_room_claimed_by_two_zones_is_refused(tmp_path):
    path = _write(
        tmp_path,
        "coast:\n  rooms: [a]\n  reset_mode: never\n  beats_between: 1\n"
        "reef:\n  rooms: [a]\n  reset_mode: never\n  beats_between: 1\n",
    )
    with pytest.raises(seed.SeedError, match="at most one zone"):
        load_zones(path, KNOWN)


def test_an_unknown_reset_mode_is_refused(tmp_path):
    path = _write(tmp_path, "coast:\n  rooms: [a]\n  reset_mode: sometimes\n  beats_between: 1\n")
    with pytest.raises(seed.SeedError, match="reset_mode"):
        load_zones(path, KNOWN)


@pytest.mark.parametrize("bad", ["0", "-3", "true"])
def test_a_non_positive_cadence_is_refused(tmp_path, bad):
    path = _write(tmp_path, f"coast:\n  rooms: [a]\n  reset_mode: always\n  beats_between: {bad}\n")
    with pytest.raises(seed.SeedError, match="beats_between"):
        load_zones(path, KNOWN)


def test_a_zone_with_no_rooms_is_refused(tmp_path):
    path = _write(tmp_path, "empty:\n  rooms: []\n  reset_mode: never\n  beats_between: 1\n")
    with pytest.raises(seed.SeedError, match="at least one member room"):
        load_zones(path, KNOWN)


# --- grouping queries -------------------------------------------------------------------
def _install(monkeypatch, zmap: dict[str, Zone]) -> None:
    monkeypatch.setattr(zones, "ZONES", zmap)
    monkeypatch.setattr(zones, "_beats", {label: 0 for label in zmap})


def test_zone_of_and_area_line(monkeypatch):
    _install(
        monkeypatch,
        {"coast": Zone(name="The Coast", rooms=["a", "b"], reset_mode="never", beats_between=10)},
    )
    assert zone_of("a") == "coast"
    assert zone_of("z") is None
    assert area_line("a") == "[Area: The Coast]"
    assert area_line("z") == ""  # a room in no area renders unchanged


# --- scheduler: due detection per mode --------------------------------------------------
def test_zones_due_respects_mode_cadence_and_occupancy(monkeypatch):
    _install(
        monkeypatch,
        {
            "never_z": Zone(name="N", rooms=["a"], reset_mode="never", beats_between=1),
            "empty_z": Zone(name="E", rooms=["b"], reset_mode="empty_only", beats_between=2),
            "always_z": Zone(name="A", rooms=["c"], reset_mode="always", beats_between=2),
        },
    )
    zones._beats.update({"never_z": 9, "empty_z": 9, "always_z": 9})
    assert "never_z" not in zones_due("x")  # never resets, however many beats pass
    assert "always_z" in zones_due("c")  # always due once past cadence
    assert "empty_z" not in zones_due("b")  # player stands in it -> occupied -> waits
    assert "empty_z" in zones_due("x")  # player elsewhere -> due


def test_below_cadence_is_not_yet_due(monkeypatch):
    _install(monkeypatch, {"z": Zone(name="Z", rooms=["a"], reset_mode="always", beats_between=5)})
    zones._beats["z"] = 4
    assert zones_due("x") == []


# --- scheduler: the beat advances and a due area resets ---------------------------------
def test_the_beat_advances_the_clock_and_a_due_area_resets(monkeypatch):
    _install(
        monkeypatch, {"pit": Zone(name="Pit", rooms=["a"], reset_mode="always", beats_between=3)}
    )
    outside = Session(player_id="p", location="b")
    assert tick_zones(outside) == ""  # the beat is silent to the player
    assert zones._beats["pit"] == 1
    tick_zones(outside)
    assert zones._beats["pit"] == 2  # still climbing, not yet due
    tick_zones(outside)  # third beat: due -> reset -> counter returns to zero
    assert zones._beats["pit"] == 0


# --- wiring: reachable through the engine tick ------------------------------------------
def test_look_shows_the_area_and_the_tick_advances_the_clock(monkeypatch):
    _install(
        monkeypatch,
        {"home": Zone(name="Home Ward", rooms=[START_ROOM], reset_mode="always", beats_between=2)},
    )
    session = Session(player_id="tester", location=START_ROOM)
    out = handle_command(session, "look")
    assert "[Area: Home Ward]" in out  # the area banner reaches the player
    assert zones._beats["home"] == 1  # the same command advanced the area clock (one door)


# --- repop: _perform_reset restocks resettable items (Tier 1, #1) ----------------------
def _shard(resettable: bool) -> Item:
    item = Item(
        name="a shard of ember",
        keywords=["shard"],
        location="room:a",
        slot="",
        mods={},
        prototype="shard",
    )
    if resettable:
        item["resettable"] = True
    return item


def _repop_world(monkeypatch, prototype: Item, present: bool) -> None:
    monkeypatch.setattr(items, "PROTOTYPES", {"shard": prototype})
    live = {"shard": dict(prototype)} if present else {}
    monkeypatch.setattr(items, "ITEMS", live)
    monkeypatch.setattr(
        zones, "ZONES", {"z": Zone(name="Z", rooms=["a"], reset_mode="always", beats_between=1)}
    )


def _shards_home() -> list[str]:
    return [iid for iid in items.items_in("room:a") if items.prototype_of(iid) == "shard"]


def test_reset_restocks_a_missing_resettable_item(monkeypatch):
    _repop_world(monkeypatch, _shard(resettable=True), present=False)  # taken -> absent from room a
    assert _shards_home() == []
    zones._perform_reset("z")
    assert len(_shards_home()) == 1  # a fresh instance respawned in its home room


def test_reset_leaves_a_non_resettable_item_absent(monkeypatch):
    _repop_world(monkeypatch, _shard(resettable=False), present=False)  # a quest item / key
    zones._perform_reset("z")
    assert _shards_home() == []  # opt-in: never respawns


def test_reset_does_not_pile_up_when_the_item_is_already_home(monkeypatch):
    _repop_world(monkeypatch, _shard(resettable=True), present=True)  # already in room a
    zones._perform_reset("z")
    assert len(_shards_home()) == 1  # idempotent: still exactly one, no duplicate


def test_reset_only_touches_its_own_area(monkeypatch):
    # the shard's home (room a) is NOT in this zone's rooms -> not restocked
    _repop_world(monkeypatch, _shard(resettable=True), present=False)
    monkeypatch.setattr(
        zones, "ZONES", {"z": Zone(name="Z", rooms=["b"], reset_mode="always", beats_between=1)}
    )
    zones._perform_reset("z")
    assert _shards_home() == []
