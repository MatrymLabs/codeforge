"""Test twin for parts/store.py -- the two-shelf hardware store inventory."""

from pathlib import Path

from parts.store import hardware_store_catalog, inspect_card, public_interface


def test_store_stocks_every_built_engine_card():
    out = hardware_store_catalog()
    for card in ("world", "items", "doors", "save", "seed", "catalog", "store"):
        assert card in out


def test_store_lists_the_reusable_shelf_cores_and_their_interface():
    out = hardware_store_catalog()
    # the physically-extracted cores are back in the catalog, under the reusable section
    assert "Reusable cores (parts/shelf/" in out and "Engine parts (parts/" in out
    assert "token_bucket" in out and "retry" in out
    # the shelf section shows each core's public interface (a real spec sheet)
    assert "TokenBucket" in out and "-> " in out


def test_the_two_shelves_are_counted():
    out = hardware_store_catalog()
    assert "reusable cores +" in out and "engine parts stocked." in out


def test_read_card_parses_the_card_convention(tmp_path: Path):
    mod = tmp_path / "widget.py"
    mod.write_text('"""CARD: widget -- spins the flux.\n\nDetails.\n"""\n')
    assert inspect_card(mod) == ("widget", "spins the flux")


def test_modules_without_a_card_are_not_stocked(tmp_path: Path):
    mod = tmp_path / "helper.py"
    mod.write_text('"""Just a helper, not a card."""\n')
    assert inspect_card(mod) is None


def test_public_interface_lists_only_public_top_level_names(tmp_path: Path):
    mod = tmp_path / "core.py"
    mod.write_text(
        "class Widget:\n    pass\n\n\ndef spin():\n    pass\n\n\ndef _private():\n    pass\n\n\n"
        "X = 1\n"
    )
    assert public_interface(mod) == ("Widget", "spin")
