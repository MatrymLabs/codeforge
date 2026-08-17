"""Test twin for kernel/world/items.py -- containment and item commands."""

import copy

import pytest

from kernel.world import items
from kernel.world.items import carrier, drop, inventory_text, items_in, read_item, take

_ME = carrier("hero")  # one hero's per-player inventory tag


@pytest.fixture(autouse=True)
def fresh_world():
    """Snapshot ITEMS before each test, restore after. No leakage."""
    snapshot = copy.deepcopy(items.ITEMS)
    yield
    items.ITEMS.clear()
    items.ITEMS.update(snapshot)


def test_key_starts_in_library():
    assert "copper_key" in items_in("room:library")


def test_take_moves_key_to_player():
    result = take("key", "library", _ME)
    assert "take" in result
    assert items.ITEMS["copper_key"]["location"] == _ME


def test_take_fails_in_wrong_room():
    result = take("key", "forge", _ME)
    assert result == "You don't see that here."
    assert items.ITEMS["copper_key"]["location"] == "room:library"


def test_drop_returns_key_to_room():
    take("key", "library", _ME)
    result = drop("key", "cellar", _ME)
    assert "drop" in result
    assert items.ITEMS["copper_key"]["location"] == "room:cellar"


def test_read_shows_an_items_lore():
    items.ITEMS["tome"] = {
        "name": "a dusty tome",
        "keywords": ["tome"],
        "location": "room:library",
        "slot": "",
        "mods": {},
        "lore": "Once, the world was warm.",
    }
    out = read_item("tome", "library", _ME)
    assert "a dusty tome" in out and "Once, the world was warm." in out


def test_read_prefers_a_carried_item_over_one_in_the_room():
    items.ITEMS["note"] = {
        "name": "a carried note",
        "keywords": ["note"],
        "location": _ME,
        "slot": "",
        "mods": {},
        "lore": "carry me",
    }
    assert "carry me" in read_item("note", "anywhere", _ME)  # reads from the hand, no room needed


def test_read_a_thing_with_no_writing_says_so():
    out = read_item("key", "library", _ME)  # the copper key carries no lore
    assert "nothing written" in out


def test_read_a_thing_not_present_is_refused():
    assert read_item("dragon", "library", _ME) == "You don't see that to read."


def test_read_nothing_asks_what():
    assert read_item("  ", "library", _ME) == "Read what?"


def test_inventory_empty_then_full():
    assert inventory_text(_ME) == "You are carrying nothing."
    take("key", "library", _ME)
    assert "copper key" in inventory_text(_ME)


# --- object instancing: prototype + clone (Fork A, slice 1) ---------------------------
def test_a_seed_item_is_its_own_prototype():
    assert items.prototype_of("copper_key") == "copper_key"
    assert items.ITEMS["copper_key"].get("prototype") == "copper_key"


def test_clone_mints_a_distinct_instance_from_a_prototype():
    iid = items.clone("copper_key", "forge")
    assert iid != "copper_key" and iid in items.ITEMS  # a fresh instance, not the seed singleton
    inst = items.ITEMS[iid]
    assert inst["prototype"] == "copper_key"
    assert inst["location"] == "room:forge"
    assert inst["name"] == items.PROTOTYPES["copper_key"]["name"]  # template copied
    assert items.prototype_of(iid) == "copper_key"


def test_cloning_twice_yields_two_distinct_instances():
    a = items.clone("copper_key", "forge")
    b = items.clone("copper_key", "forge")
    assert a != b
    assert items.items_in("room:forge").count(a) == 1


def test_clone_accepts_a_room_label_a_tagged_room_or_player():
    assert items.ITEMS[items.clone("copper_key", "forge")]["location"] == "room:forge"
    assert items.ITEMS[items.clone("copper_key", "room:forge")]["location"] == "room:forge"
    assert items.ITEMS[items.clone("copper_key", "player")]["location"] == "player"


def test_cloning_an_unknown_prototype_fails_loud():
    with pytest.raises(items.ItemError, match="unknown item prototype"):
        items.clone("no_such_thing", "forge")


def test_prototype_of_falls_back_to_the_id_for_an_unknown_item():
    assert items.prototype_of("mystery") == "mystery"


def test_two_heroes_do_not_share_one_inventory():
    """The point of per-player inventory: each hero's carrier tag is distinct, so what one takes the
    other never sees. A shared \"player\" bucket would fail this."""
    alia, bram = carrier("alia"), carrier("bram")
    items.ITEMS["gem"] = {
        "name": "a gem",
        "keywords": ["gem"],
        "location": "room:forge",
        "slot": "",
        "mods": {},
    }
    take("gem", "forge", alia)  # alia picks it up
    assert items_in(alia) == ["gem"] and items_in(bram) == []  # bram's bag is untouched
    assert "a gem" in inventory_text(alia) and inventory_text(bram) == "You are carrying nothing."


# --- numbered-target disambiguation (target_disambig shelf-part consumer) ------------------------
def _two_keys() -> tuple[str, str]:
    """Two identical items (both answer to 'key') in one room, so 'key' alone is ambiguous."""
    first = items.clone("copper_key", "forge")
    second = items.clone("copper_key", "forge")
    return first, second


def test_trace_all_items_returns_every_match_in_order():
    first, second = _two_keys()
    assert items.trace_all_items("key", "room:forge") == [first, second]
    # trace_item still returns just the first, unchanged
    assert items.trace_item("key", "room:forge") == first


def test_bare_name_resolves_to_the_first_match():
    first, _second = _two_keys()
    # a plain name is ordinal 1: identical to the old first-match behavior
    assert items.resolve_item_target("key", "room:forge") == first


def test_ordinal_picks_the_nth_identical_item():
    first, second = _two_keys()
    assert items.resolve_item_target("2-key", "room:forge") == second
    assert items.resolve_item_target("key-2", "room:forge") == second  # trailing ordinal too
    assert items.resolve_item_target("1-key", "room:forge") == first


def test_take_can_reach_the_second_identical_item():
    """The defect this fixes: first-match-only trace made a second identical item un-takeable."""
    first, second = _two_keys()
    result = take("2-key", "forge", _ME)
    assert "take" in result
    assert items.ITEMS[second]["location"] == _ME  # the SECOND moved
    assert items.ITEMS[first]["location"] == "room:forge"  # the first stayed


def test_take_overshoot_is_refused_with_an_honest_count():
    _two_keys()
    result = take("3-key", "forge", _ME)
    assert result == "You don't see that here (no target #3: only 2 here)."


def test_resolve_unknown_name_is_none_not_an_error():
    _two_keys()
    assert items.resolve_item_target("2-dagger", "room:forge") is None


def test_a_hyphenated_keyword_is_not_mistaken_for_an_ordinal():
    """A hyphen that is not a numeric ordinal ('war-hammer') stays part of the name."""
    items.ITEMS["wh"] = {
        "name": "a war-hammer",
        "keywords": ["war-hammer"],
        "location": "room:forge",
        "slot": "weapon",
        "mods": {},
    }
    assert items.resolve_item_target("war-hammer", "room:forge") == "wh"


def test_take_ordinal_reaches_through_the_engine_tick():
    """A verb is not wired until handle_command proves it reachable: the `take 2-<kw>` ordinal path
    must survive the tick, not just a direct call to take()."""
    from forge import handle_command  # noqa: PLC0415
    from kernel.world.session import Session  # noqa: PLC0415

    room = "forge"
    first = items.clone("copper_key", room)
    second = items.clone("copper_key", room)
    session = Session(player_id="ticker", location=room)
    out = handle_command(session, "take 2-key")
    assert "take" in out.lower()
    assert items.ITEMS[second]["location"] == carrier("ticker")  # the second one moved
    assert items.ITEMS[first]["location"] == f"room:{room}"  # the first stayed put


# --- the purse is carried, so it shows in the carried view ---------------------------------------


def test_an_empty_purse_stays_silent() -> None:
    """Nobody who has never earned a coin should be told they have 0 of them."""
    assert inventory_text(_ME) == "You are carrying nothing."
    assert inventory_text(_ME, 0) == "You are carrying nothing."


def test_coin_shows_even_when_nothing_else_is_carried() -> None:
    """Money IS something you are carrying; an empty pack with coin is not 'carrying nothing'."""
    out = inventory_text(_ME, 3)
    assert "carrying nothing" not in out
    assert "cinder" in out


def test_coin_shows_alongside_items() -> None:
    take("key", "library", _ME)
    out = inventory_text(_ME, 3)
    assert "copper key" in out and "cinder" in out


def test_coin_is_rendered_in_its_denominations_not_as_a_raw_count() -> None:
    """1234 is '12 sparks, 34 cinders' to a player. A raw integer is an implementation detail."""
    out = inventory_text(_ME, 1234)
    assert "1234" not in out
    assert "spark" in out and "cinder" in out


def test_the_default_keeps_every_older_caller_rendering_as_before() -> None:
    """`coins` defaults to 0, so a caller that knows nothing about the purse is unchanged."""
    take("key", "library", _ME)
    assert inventory_text(_ME) == inventory_text(_ME, 0)


def test_the_tick_shows_the_purse_a_kill_announced() -> None:
    """The reward line says '(purse: 3 cinders)'. Something must then be able to show it.

    Before this, no verb in the game could: not inventory, not score, and `purse` is not a
    command. The only `coins` in the parser is `trade coins`, which offers money rather than
    counting it.
    """
    import forge  # noqa: PLC0415
    from kernel.world.session import Session  # noqa: PLC0415

    s = Session(player_id="rich")
    forge.handle_command(s, "job vanguard")
    s.coins = 3
    assert "cinder" in forge.handle_command(s, "inventory")
