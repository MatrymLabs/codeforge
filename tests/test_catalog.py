"""Test twin for parts/catalog.py -- the numbered filing view."""

from parts.catalog import room_catalog
from parts.seed import Room


def test_catalog_numbers_rooms_alphabetically():
    rooms: dict[str, Room] = {
        "zeta": Room(name="Zeta", desc="z", exits={}),
        "alpha": Room(name="Alpha", desc="a", exits={"up": "zeta"}),
    }
    out = room_catalog(rooms)
    alpha_line = next(line for line in out.splitlines() if line.split()[1:2] == ["alpha"])
    zeta_line = next(line for line in out.splitlines() if line.split()[1:2] == ["zeta"])
    assert alpha_line.startswith("1")
    assert zeta_line.startswith("2")
    assert "up->zeta" in alpha_line


def test_catalog_reads_the_shipped_world_by_default():
    out = room_catalog()
    assert "forge" in out
    assert "rooms filed." in out


def test_catalog_shows_none_for_dead_ends():
    rooms: dict[str, Room] = {"pit": Room(name="The Pit", desc="deep", exits={})}
    assert "(none)" in room_catalog(rooms)


def test_catalog_columns_do_not_collide_on_a_long_label():
    """Hostile case: a seed label wider than the old fixed :<14 column (e.g. the flagship's
    'cinderhearth_square', 19 chars) once ran straight into the NAME column. Widths are computed
    now, so the NAME column starts at the SAME position on every row, short label or long."""
    rooms: dict[str, Room] = {
        "cinderhearth_square": Room(name="Cinderhearth Square", desc="d", exits={}),
        "pit": Room(name="The Pit", desc="d", exits={}),
    }
    lines = room_catalog(rooms).splitlines()
    name_columns = set()
    for label, name in (("cinderhearth_square", "Cinderhearth Square"), ("pit", "The Pit")):
        row = next(ln for ln in lines if label in ln and name in ln)
        name_columns.add(row.index(name))
    assert len(name_columns) == 1  # both NAME cells start at the same column; no collision


def test_npc_catalog_files_the_librarian():
    from parts.catalog import npc_catalog

    out = npc_catalog()
    assert "librarian" in out
    assert "library" in out
    assert "npcs filed." in out


def test_item_catalog_files_the_copper_key():
    from parts.catalog import item_catalog

    out = item_catalog()
    assert "copper_key" in out
    assert "library" in out
    assert "items filed." in out
