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
