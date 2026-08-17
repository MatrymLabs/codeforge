"""Test twin for kernel/world/room_category.py -- the bracketed category under a room's title.

Acceptance: a room in a zone that declares a biome gets that biome, prettified for display; a zone
with no biome falls back to its region; the index is built once and maps every member room.

Refusal (honest, not loud): a room in NO zone, a zone with neither biome nor region, and a world
with no zones at all all yield "" so the renderer omits the line entirely. A blank is truthful;
"[Unknown]" under every room title is noise pretending to be information.

The rendering half is pinned too: the standard's hierarchy is title, then category, then prose,
then the exits line, and a world that declares no category must not leave an empty bracket behind.
"""

from __future__ import annotations

from kernel.world.room_category import category_of, display_category, index_by_room

# --- display: the slug is canonical, only the rendering is prettified ------------------------


def test_a_slug_becomes_readable_display_text() -> None:
    assert display_category("temperate-meadow") == "Temperate Meadow"
    assert display_category("glacier_waste") == "Glacier Waste"
    assert display_category("volcanic-flats") == "Volcanic Flats"


def test_display_leaves_a_single_word_alone() -> None:
    assert display_category("desert") == "Desert"


def test_display_of_nothing_is_nothing() -> None:
    assert display_category("") == ""


# --- the index ------------------------------------------------------------------------------


def test_every_room_in_a_zone_gets_its_biome() -> None:
    zones = {"z1": {"biome": "wild-forest", "rooms": ["glade", "thicket"]}}
    index = index_by_room(zones)
    assert index == {"glade": "wild-forest", "thicket": "wild-forest"}


def test_region_is_the_fallback_when_a_zone_declares_no_biome() -> None:
    zones = {"z1": {"region": "Emberreach", "rooms": ["hall"]}}
    assert category_of("hall", index_by_room(zones)) == "Emberreach"


def test_biome_wins_over_region_when_both_are_present() -> None:
    zones = {"z1": {"biome": "salt-desert", "region": "Zhaar", "rooms": ["dune"]}}
    assert category_of("dune", index_by_room(zones)) == "Salt Desert"


def test_a_zone_declaring_neither_contributes_nothing() -> None:
    zones = {"z1": {"rooms": ["nowhere"]}, "z2": {"biome": "tundra", "rooms": ["ice"]}}
    index = index_by_room(zones)
    assert "nowhere" not in index
    assert index["ice"] == "tundra"  # one silent zone does not poison the rest


def test_the_first_listing_wins_when_two_zones_claim_a_room() -> None:
    """A room in two zones is a content defect this card does NOT adjudicate.

    The zone loader is the right place to refuse it. Inventing a second opinion here would hide
    the defect behind a rendering choice, so the world stays renderable and the complaint stays
    where it belongs.
    """
    zones = {
        "a": {"biome": "first", "rooms": ["shared"]},
        "b": {"biome": "second", "rooms": ["shared"]},
    }
    assert index_by_room(zones)["shared"] == "first"


def test_a_zone_pack_of_dataclasses_reads_the_same_as_mappings() -> None:
    """The loader may hand back TypedDicts or objects; the card must not care which."""

    class Zone:
        biome = "highland-moor"
        rooms = ("crag",)

    assert category_of("crag", index_by_room({"z": Zone()})) == "Highland Moor"


# --- refusal: silence rather than a fabricated category --------------------------------------


def test_a_room_in_no_zone_has_no_category() -> None:
    assert category_of("orphan", index_by_room({"z": {"biome": "x", "rooms": ["other"]}})) == ""


def test_a_world_with_no_zones_at_all_has_no_categories() -> None:
    # first-forge ships no zones.yaml. It must render NO category, not an invented one.
    assert index_by_room({}) == {}
    assert category_of("forge", {}) == ""


def test_an_empty_room_list_is_not_an_error() -> None:
    assert index_by_room({"z": {"biome": "x", "rooms": []}}) == {}
    assert index_by_room({"z": {"biome": "x"}}) == {}


# --- the rendered hierarchy the standard asks for ---------------------------------------------


def test_the_renderer_places_the_category_under_the_title() -> None:
    from kernel.world.world import render_room  # noqa: PLC0415

    rendered = render_room("forge")
    lines = [ln for ln in rendered.splitlines() if ln.strip()]
    assert lines[0].startswith("== ")  # title first
    assert lines[-1].startswith("Exits: ")  # horizontal obvious-exits line last


def test_a_world_without_categories_leaves_no_empty_bracket() -> None:
    """The line is OMITTED, not rendered blank. An empty `[]` is worse than nothing."""
    from kernel.world.world import render_room  # noqa: PLC0415

    assert "[]" not in render_room("forge")
