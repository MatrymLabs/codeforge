"""Test twin for parts/store.py -- the hardware store inventory."""

from parts.store import hardware_store_catalog, inspect_card


def test_store_stocks_every_built_card():
    out = hardware_store_catalog()
    for card in ("world", "items", "doors", "save", "seed", "catalog", "store"):
        assert card in out


def test_read_card_parses_the_card_convention(tmp_path):
    mod = tmp_path / "widget.py"
    mod.write_text('"""CARD: widget -- spins the flux.\n\nDetails.\n"""\n')
    assert inspect_card(mod) == ("widget", "spins the flux")


def test_modules_without_a_card_are_not_stocked(tmp_path):
    mod = tmp_path / "helper.py"
    mod.write_text('"""Just a helper, not a card."""\n')
    assert inspect_card(mod) is None
