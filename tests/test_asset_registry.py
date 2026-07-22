"""Test twin for parts/asset_registry.py -- the practical adapter + the one-core proof."""

import pytest

from parts.asset_registry import Asset, AssetRegistry
from parts.shelf.repository import DuplicateKey, InMemoryRepository, NotFound


def test_register_find_and_list():
    reg = AssetRegistry()
    reg.register(Asset("A-1", "Laptop"))
    reg.register(Asset("A-2", "Monitor"))
    assert reg.find("A-1") == Asset("A-1", "Laptop")
    assert reg.count() == 2
    assert {a.name for a in reg.all()} == {"Laptop", "Monitor"}


def test_a_duplicate_asset_id_is_refused():
    reg = AssetRegistry()
    reg.register(Asset("A-1", "Laptop"))
    with pytest.raises(DuplicateKey):
        reg.register(Asset("A-1", "Other"))


def test_retire_flips_the_status_and_refuses_an_unknown_asset():
    reg = AssetRegistry()
    reg.register(Asset("A-1", "Laptop"))
    retired = reg.retire("A-1")
    assert retired.status == "retired"
    assert reg.find("A-1").status == "retired"
    with pytest.raises(NotFound):
        reg.retire("ghost")


def test_one_core_powers_both_the_game_logbook_and_the_practical_registry():
    import parts.logbook as game

    reg = AssetRegistry()
    reg.register(Asset("A-1", "Laptop"))
    assert isinstance(reg._repo, InMemoryRepository)  # the practical registry uses the core
    game.reset_logbooks()
    from parts.session import SESSIONS, Session

    s = Session(player_id="scribe", location="courtyard")
    SESSIONS["scribe"] = s
    game.journal(s, "an entry")
    assert isinstance(game._REPOS["scribe"], InMemoryRepository)  # the game logbook, same core
