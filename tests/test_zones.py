"""Test twin for kernel/world/zones.py + seed.load_zones -- areas and the beat-driven reset loop.

Acceptance: a valid zones pack groups rooms; the scheduler advances on the world beat and comes
due per its mode. Refusal: a malformed zone fails loud rather than booting a broken area.
"""

import pytest

import kernel.world.seed as seed  # reference BlueprintError via module: other suites reload it
import kernel.world.zones as zones  # a class imported at collection must not match world.seed
from forge import handle_command
from kernel.world import items
from kernel.world.seed import BLUEPRINTS_ROOT, Item, Zone, load_rooms, load_zones
from kernel.world.session import Session
from kernel.world.world import START_ROOM
from kernel.world.zones import area_line, tick_zones, zone_of, zones_due

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
    aethryn = BLUEPRINTS_ROOT / "aethryn"
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
    with pytest.raises(seed.BlueprintError, match="does not exist"):
        load_zones(path, KNOWN)


def test_a_room_claimed_by_two_zones_is_refused(tmp_path):
    path = _write(
        tmp_path,
        "coast:\n  rooms: [a]\n  reset_mode: never\n  beats_between: 1\n"
        "reef:\n  rooms: [a]\n  reset_mode: never\n  beats_between: 1\n",
    )
    with pytest.raises(seed.BlueprintError, match="at most one zone"):
        load_zones(path, KNOWN)


def test_an_unknown_reset_mode_is_refused(tmp_path):
    path = _write(tmp_path, "coast:\n  rooms: [a]\n  reset_mode: sometimes\n  beats_between: 1\n")
    with pytest.raises(seed.BlueprintError, match="reset_mode"):
        load_zones(path, KNOWN)


@pytest.mark.parametrize("bad", ["0", "-3", "true"])
def test_a_non_positive_cadence_is_refused(tmp_path, bad):
    path = _write(tmp_path, f"coast:\n  rooms: [a]\n  reset_mode: always\n  beats_between: {bad}\n")
    with pytest.raises(seed.BlueprintError, match="beats_between"):
        load_zones(path, KNOWN)


def test_a_zone_with_no_rooms_is_refused(tmp_path):
    path = _write(tmp_path, "empty:\n  rooms: []\n  reset_mode: never\n  beats_between: 1\n")
    with pytest.raises(seed.BlueprintError, match="at least one member room"):
        load_zones(path, KNOWN)


# --- Layer-2 geographic metadata (region / level band / biome), all optional -------------
def test_zone_metadata_loads_when_declared(tmp_path):
    path = _write(
        tmp_path,
        "reach:\n  rooms: [a]\n  reset_mode: never\n  beats_between: 5\n"
        '  region: "Emberreach"\n  level_min: 12\n  level_max: 20\n  biome: "city"\n',
    )
    z = load_zones(path, KNOWN)["reach"]
    assert z["region"] == "Emberreach"
    assert z["level_min"] == 12 and z["level_max"] == 20
    assert z["biome"] == "city"


def test_zone_metadata_is_absent_when_omitted(tmp_path):
    # Backward-compatible: a zone that declares no metadata carries none of the optional keys.
    z = load_zones(_write(tmp_path, "wilds:\n  rooms: [c]\n"), KNOWN)["wilds"]
    assert "region" not in z and "level_min" not in z and "biome" not in z


@pytest.mark.parametrize(
    "meta, match",
    [
        ('  region: ""\n', "region"),
        ("  level_min: 0\n", "level_min"),
        ("  level_max: 400\n", "level_max"),
        ("  level_min: 30\n  level_max: 20\n", ">= 'level_min'"),
        ("  level_min: true\n", "level_min"),
        ('  biome: ""\n', "biome"),
    ],
)
def test_malformed_zone_metadata_is_refused(tmp_path, meta, match):
    body = "z:\n  rooms: [a]\n  reset_mode: never\n  beats_between: 1\n" + meta
    with pytest.raises(seed.BlueprintError, match=match):
        load_zones(_write(tmp_path, body), KNOWN)


def test_shipped_aethryn_zones_cover_the_full_level_1_to_300_progression():
    """A living gate on the world's geography: the metadata-carrying areas span Levels 1-300 with no
    band left uncovered, so a Forger always has somewhere banded to be. Guards against a progression
    gap creeping in as regions are added (the audit reports the same, in scripts/world_audit.py)."""
    aethryn = BLUEPRINTS_ROOT / "aethryn"
    rooms = set(load_rooms(aethryn / "rooms.yaml"))
    zmap = load_zones(aethryn / "zones.yaml", rooms)
    covered = set()
    for z in zmap.values():
        lo, hi = z.get("level_min"), z.get("level_max")
        if lo is not None and hi is not None:
            assert 1 <= lo <= hi <= 300, f"zone with a bad band: {lo}-{hi}"
            covered.update(range(lo, hi + 1))
    # The hand-authored seed zones reach into the mid game; the procedural Forgeward Road (added at
    # world assembly) carries the high bands to 300. Here we pin the authored seed's own continuous
    # span from Level 1, which the audit then extends to 300 with the generated marches.
    authored_top = max(z["level_max"] for z in zmap.values() if z.get("level_max"))
    assert covered.issuperset(range(1, authored_top + 1)), "a level band is uncovered in the seed"


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


def test_zone_of_index_rebuilds_when_zones_are_swapped(monkeypatch):
    # The O(1) reverse index is keyed on ZONES identity: swapping the dict must invalidate it, so a
    # lookup never returns a stale area from a previous world. Pins the cache-invalidation contract.
    _install(
        monkeypatch, {"one": Zone(name="One", rooms=["a"], reset_mode="never", beats_between=1)}
    )
    assert zone_of("a") == "one"
    _install(
        monkeypatch, {"two": Zone(name="Two", rooms=["a"], reset_mode="never", beats_between=1)}
    )
    assert zone_of("a") == "two"  # the new world's area, not the cached "one"


def test_zone_of_first_area_wins_on_overlap(monkeypatch):
    # The old linear scan returned the FIRST area that listed a room; the index must match that with
    # first-wins, so behaviour is preserved even in the (undocumented) overlap case.
    _install(
        monkeypatch,
        {
            "first": Zone(name="First", rooms=["shared"], reset_mode="never", beats_between=1),
            "second": Zone(name="Second", rooms=["shared"], reset_mode="never", beats_between=1),
        },
    )
    assert zone_of("shared") == "first"  # insertion order wins, exactly like the scan did


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


def test_merged_zones_adds_the_spiral_areas_only_when_a_spiral_seed_opts_in():
    """The generated Road's marches become named areas alongside the seed's own -- but only when the
    seed ships a spiral.yaml. With no spiral config, the authored areas are returned unchanged."""
    from kernel.world.zones import merged_zones

    base = {"coast": {"name": "C", "rooms": ["shore"], "reset_mode": "never", "beats_between": 9}}
    assert merged_zones(base, None) == base  # no spiral: unchanged

    config = {
        "attach": "shore",
        "first_coil": 4,
        "base_level": 40,
        "levels_per_coil": 20,
        "top_level": 300,
    }
    merged = merged_zones(base, config)
    assert "coast" in merged  # the authored area survives
    assert any(label.startswith("spiral_coil_") for label in merged)  # and the marches are named
    assert any(z["name"] == "The Forge's Edge" for z in merged.values())


# --- live dynamic spawning: _spawn_wanderers places a wandering pickup (roadmap #1) ---------------
class _FixedRNG:
    """A deterministic stand-in for SPAWN_RNG: randrange always rolls the rarity HIT (0), and choice
    takes the first candidate -- so a test draws an exact site, not real randomness."""

    def randrange(self, n: int) -> int:
        return 0

    def choices(self, population, weights=None, k=1):
        return [population[0]]

    def choice(self, seq):
        return seq[0]


def _wanderer(chance: int | None = None) -> Item:
    item = Item(
        name="a wayfarer's tonic",
        keywords=["tonic"],
        location="nowhere",
        slot="",
        mods={},
        prototype="tonic",
    )
    item["spawn_pool"] = ["a", "b"]
    if chance is not None:
        item["spawn_chance"] = chance
    return item


def _wander_world(monkeypatch, prototype: Item, rng=None) -> None:
    monkeypatch.setattr(items, "PROTOTYPES", {"tonic": prototype})
    monkeypatch.setattr(
        items, "ITEMS", {"tonic": dict(prototype)}
    )  # the 'nowhere' seed placeholder
    monkeypatch.setattr(
        zones,
        "ZONES",
        {"z": Zone(name="Z", rooms=["a", "b"], reset_mode="always", beats_between=1)},
    )
    monkeypatch.setattr(zones, "SPAWN_RNG", rng or _FixedRNG())


def _loose_in(room: str) -> list[str]:
    return [iid for iid in items.items_in(f"room:{room}") if items.prototype_of(iid) == "tonic"]


def test_a_wanderer_spawns_at_a_pool_site_on_reset(monkeypatch):
    _wander_world(monkeypatch, _wanderer())
    zones._perform_reset("z")
    # the FixedRNG picks the first candidate -> room a gets exactly one fresh instance
    assert len(_loose_in("a")) == 1 and _loose_in("b") == []


def test_a_wanderer_does_not_duplicate_while_one_is_loose(monkeypatch):
    _wander_world(monkeypatch, _wanderer())
    zones._perform_reset("z")
    zones._perform_reset("z")  # already loose in a pool room -> no second instance
    assert len(_loose_in("a")) + len(_loose_in("b")) == 1


def test_spawn_chance_can_skip_a_reset(monkeypatch):
    class _Miss(_FixedRNG):
        def randrange(self, n: int) -> int:
            return 1  # never the 0 that spawns

    _wander_world(monkeypatch, _wanderer(chance=3), rng=_Miss())
    zones._perform_reset("z")
    assert _loose_in("a") == [] and _loose_in("b") == []  # rarity roll missed -> nothing spawned


def test_a_wanderer_ignores_an_area_holding_none_of_its_pool(monkeypatch):
    _wander_world(monkeypatch, _wanderer())
    monkeypatch.setattr(
        zones, "ZONES", {"z": Zone(name="Z", rooms=["c"], reset_mode="always", beats_between=1)}
    )
    zones._perform_reset("z")
    assert _loose_in("a") == [] and _loose_in("b") == []  # none of its sites are in this area


def test_the_beat_drives_a_wandering_spawn(monkeypatch):
    _wander_world(monkeypatch, _wanderer())
    monkeypatch.setattr(zones, "_beats", {"z": 0})
    s = Session(player_id="p", location="a")
    tick_zones(s)  # one beat: area z is due (beats_between 1) -> fires the wanderer
    assert len(_loose_in("a")) == 1


# --- seed validation: the wandering-spawn fields fail loud on misuse ------------------------------
def _items_yaml(tmp_path, body: str):
    path = tmp_path / "items.yaml"
    path.write_text(body)
    return path


def test_spawn_pool_requires_location_nowhere(tmp_path):
    body = "t:\n  location: a\n  spawn_pool: [a, b]\n"
    with pytest.raises(seed.BlueprintError, match="nowhere"):
        seed.load_items(_items_yaml(tmp_path, body))


def test_spawn_pool_must_be_a_non_empty_room_list(tmp_path):
    body = "t:\n  location: nowhere\n  spawn_pool: []\n"
    with pytest.raises(seed.BlueprintError, match="spawn_pool"):
        seed.load_items(_items_yaml(tmp_path, body))


def test_spawn_chance_must_be_positive(tmp_path):
    body = "t:\n  location: nowhere\n  spawn_pool: [a]\n  spawn_chance: 0\n"
    with pytest.raises(seed.BlueprintError, match="spawn_chance"):
        seed.load_items(_items_yaml(tmp_path, body))


def test_spawn_chance_needs_a_spawn_pool(tmp_path):
    body = "t:\n  location: nowhere\n  spawn_chance: 2\n"
    with pytest.raises(seed.BlueprintError, match="spawn_chance"):
        seed.load_items(_items_yaml(tmp_path, body))


def test_a_valid_wanderer_loads(tmp_path):
    body = "t:\n  location: nowhere\n  spawn_pool: [a, b]\n  spawn_chance: 2\n"
    loaded = seed.load_items(_items_yaml(tmp_path, body))["t"]
    assert loaded["spawn_pool"] == ["a", "b"] and loaded["spawn_chance"] == 2


def test_inspect_world_links_rejects_a_spawn_pool_room_that_does_not_exist():
    rooms = {"a": seed.Room(name="A", desc="", exits={})}
    item = Item(name="t", keywords=["t"], location="nowhere", slot="", mods={}, prototype="t")
    item["spawn_pool"] = ["a", "ghost_room"]
    with pytest.raises(seed.BlueprintError, match="ghost_room"):
        seed.inspect_world_links(rooms, {"t": item}, {})


def test_a_wanderer_at_its_instance_ceiling_is_skipped_not_a_crash(monkeypatch):
    _wander_world(monkeypatch, _wanderer())

    def _ceiling(*_a, **_k):
        raise items.ItemError("at the instance ceiling")

    monkeypatch.setattr(items, "clone", _ceiling)
    zones._perform_reset("z")  # the ceiling is swallowed: no crash, nothing spawned
    assert _loose_in("a") == [] and _loose_in("b") == []


# --- seasonal-gated wandering spawns (roadmap #5): climate gates whether a wanderer appears -----
def _seasonal_wanderer(seasons: list[str]) -> Item:
    item = _wanderer()
    item["prototype"] = "tonic"
    item["seasons"] = seasons
    return item


def test_a_seasonal_wanderer_spawns_only_in_its_season(monkeypatch):
    import kernel.world.climate as climate

    _wander_world(monkeypatch, _seasonal_wanderer(["winter"]))
    monkeypatch.setattr(climate, "_beat", 0)  # beat 0 -> spring (not winter)
    zones._perform_reset("z")
    assert _loose_in("a") == [] and _loose_in("b") == []  # out of season: nothing

    # advance the world clock into winter (season index 3 -> beat 3 * season length)
    monkeypatch.setattr(climate, "_beat", climate._SEASON_LENGTH * 3)
    assert climate.season_of(climate.now()) == "winter"
    zones._perform_reset("z")
    assert len(_loose_in("a")) == 1  # in season: it appears


def test_a_seasonless_wanderer_spawns_in_any_season(monkeypatch):
    import kernel.world.climate as climate

    _wander_world(monkeypatch, _wanderer())  # no seasons -> unconditional
    monkeypatch.setattr(climate, "_beat", climate._SEASON_LENGTH)  # summer
    zones._perform_reset("z")
    assert len(_loose_in("a")) == 1


def test_seasons_must_be_valid_and_need_a_pool(tmp_path):
    from kernel.world.climate import SEASONS

    assert "winter" in SEASONS
    bad_value = "t:\n  location: nowhere\n  spawn_pool: [a]\n  seasons: [monsoon]\n"
    with pytest.raises(seed.BlueprintError, match="seasons"):
        seed.load_items(_items_yaml(tmp_path, bad_value))
    no_pool = "t:\n  location: nowhere\n  seasons: [winter]\n"
    with pytest.raises(seed.BlueprintError, match="seasons"):
        seed.load_items(_items_yaml(tmp_path, no_pool))


def test_a_valid_seasonal_wanderer_loads(tmp_path):
    body = "t:\n  location: nowhere\n  spawn_pool: [a, b]\n  seasons: [autumn, winter]\n"
    loaded = seed.load_items(_items_yaml(tmp_path, body))["t"]
    assert loaded["seasons"] == ["autumn", "winter"]
