"""Test twin for parts/world/zone_story.py -- the Zone Story Framework.

Acceptance: a zone's story composes its filed pieces (place, tale, warden, lore, work) and renders
a dossier; the `region` view names the player's zone or the wilds. Completeness (governance):
on the live world, a dungeon zone reports its full depths (a warden implies its inscription).
"""

from __future__ import annotations

from parts.world.session import Session
from parts.world.zone_story import ZoneStory, assemble, region_view, render

_FULL = ZoneStory(
    label="vale",
    name="The Vale",
    region="Vale",
    biome="wild-forest",
    level_min=20,
    level_max=50,
    rooms=5,
    tale="A tale of the Vale: its hollow festers.",
    warden="the Warden of the Hollow",
    inscription="Carved below: beware.",
    landmark="A weathered monument.",
    culls=45,
    forages=2,
)


def test_render_composes_the_dossier():
    out = render(_FULL)
    assert "The Vale" in out and "level 20-50" in out and "5 rooms" in out
    assert "A tale of the Vale" in out
    assert "the Warden of the Hollow" in out and "beware" in out and "monument" in out
    assert "45 cull-contracts" in out and "2 forage-contracts" in out


def test_a_place_with_no_content_still_names_itself():
    bare = ZoneStory("z", "Emptyreach", "Empty", "", 1, 1, 0, None, None, None, None, 0, 0)
    out = render(bare)
    assert "Emptyreach" in out
    assert "cull-contracts" not in out and "Its tale" not in out


def test_region_view_names_the_untracked_wilds():
    s = Session(player_id="wanderer")
    s.location = "a_room_in_no_zone"
    assert "untracked wilds" in region_view(s)


def test_assemble_returns_none_for_an_unknown_zone():
    assert assemble("no_such_zone") is None


def test_a_dungeon_zone_on_the_live_world_reports_its_full_depths():
    from parts.world.zones import ZONES

    for label in ZONES:
        story = assemble(label)
        assert story is not None and story.name, f"{label} has no story"
        if story.warden:  # a dungeon zone: its depths lore must be filed too
            assert story.inscription, f"{label} has a warden but no inscription"
