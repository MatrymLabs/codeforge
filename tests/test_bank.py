"""Test twin for kernel/world/bank.py -- a hero's personal vault.

Acceptance: deposit takes a carried item out of the world into storage; the vault lists it; withdraw
brings it back with its rolled affix intact; a deposited item survives a save+restore in
the vault (not the bag). Refusal / safety: depositing nothing or a worn item is refused, withdrawing
from an empty vault or a bad match is refused, and one hero's vault is scoped to them alone. Real
store, quarantined to tmp by conftest.
"""

from __future__ import annotations

import copy

import pytest

from kernel.world import bank, items, loose_store
from kernel.world.characters import load_character, restore_character, save_character
from kernel.world.items import ITEMS, carrier, items_in, prototype_of
from kernel.world.jobs import bind_calling
from kernel.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def _fresh_items():
    """Snapshot ITEMS so a test's clones never leak into the next (conftest quarantines the DB
    and SESSIONS, not the in-memory item map)."""
    snap = copy.deepcopy(items.ITEMS)
    yield
    items.ITEMS.clear()
    items.ITEMS.update(snap)


def _hero(name: str = "ada") -> Session:
    s = SESSIONS[name] = Session(player_id=name, location="courtyard", named=True)
    bind_calling(s, "vanguard")
    return s


def _teardown() -> None:
    for name in list(SESSIONS):
        SESSIONS.pop(name, None)


# --- acceptance -------------------------------------------------------------------------------
def test_deposit_moves_a_carried_item_into_the_vault():
    try:
        ada = _hero()
        iid = items.clone("forge_wrench", carrier("ada"))
        out = bank.deposit(ada, "wrench")
        assert "deposit" in out.lower()
        assert iid not in ITEMS  # it left the world, into storage
        assert len(loose_store.contents("vault:ada")) == 1
    finally:
        _teardown()


def test_withdraw_brings_it_back_with_its_affix():
    try:
        ada = _hero()
        iid = items.clone("forge_wrench", carrier("ada"))
        ITEMS[iid]["name"] = "a Cruel forge wrench [rare]"
        ITEMS[iid]["mods"] = {"ATK": 6}
        ITEMS[iid]["rarity"] = "rare"
        bank.deposit(ada, "wrench")
        out = bank.withdraw(ada, "1")  # by list number
        assert "withdraw" in out.lower()
        back = [ITEMS[i] for i in items_in(carrier("ada")) if prototype_of(i) == "forge_wrench"]
        assert len(back) == 1
        assert back[0]["name"] == "a Cruel forge wrench [rare]" and back[0]["mods"] == {"ATK": 6}
        assert loose_store.contents("vault:ada") == []  # gone from the vault
    finally:
        _teardown()


def test_the_vault_survives_a_save_and_restore():
    try:
        ada = _hero()
        items.clone("forge_wrench", carrier("ada"))
        bank.deposit(ada, "wrench")
        save_character(ada)
        # a fresh login: the vault is storage, so it is NOT in the reloaded bag, but IS still banked
        reborn = SESSIONS["ada"] = Session(player_id="ada", named=True)
        restore_character(reborn, load_character("ada"))
        assert [prototype_of(i) for i in items_in(carrier("ada"))].count("forge_wrench") == 0
        assert len(loose_store.contents("vault:ada")) == 1  # still safe in the vault
    finally:
        _teardown()


def test_render_numbers_the_contents():
    try:
        ada = _hero()
        items.clone("forge_wrench", carrier("ada"))
        bank.deposit(ada, "wrench")
        listing = bank.render(ada)
        assert "Your vault (1)" in listing and "1." in listing
    finally:
        _teardown()


# --- refusal / safety --------------------------------------------------------------------------
def test_depositing_nothing_or_an_uncarried_item_is_refused():
    try:
        ada = _hero()
        assert "deposit what" in bank.deposit(ada, "").lower()
        assert "aren't carrying" in bank.deposit(ada, "dragon").lower()
    finally:
        _teardown()


def test_a_worn_item_cannot_be_banked():
    try:
        ada = _hero()
        iid = items.clone("forge_wrench", carrier("ada"))
        ada.equipped["weapon"] = iid  # worn
        assert "worn" in bank.deposit(ada, "wrench").lower()
        assert iid in ITEMS  # still on the hero, not stored
    finally:
        _teardown()


def test_withdrawing_from_an_empty_vault_or_a_bad_match_is_refused():
    try:
        ada = _hero()
        assert "empty" in bank.withdraw(ada, "1").lower()
        items.clone("forge_wrench", carrier("ada"))
        bank.deposit(ada, "wrench")
        assert "nothing like that" in bank.withdraw(ada, "dragon").lower()
    finally:
        _teardown()


def test_the_vault_is_scoped_to_its_owner():
    try:
        ada = _hero("ada")
        bram = _hero("bram")
        items.clone("forge_wrench", carrier("ada"))
        items.clone("rusty_lantern", carrier("bram"))
        bank.deposit(ada, "wrench")
        bank.deposit(bram, "lantern")
        # bram cannot withdraw ada's wrench: his vault holds only his own lantern
        assert len(loose_store.contents("vault:ada")) == 1
        assert len(loose_store.contents("vault:bram")) == 1
        bram_out = bank.withdraw(bram, "1")
        assert "lantern" in bram_out.lower()
    finally:
        _teardown()


# --- the verb is reachable through the engine tick --------------------------------------------
def test_the_bank_verb_is_reachable():
    import forge  # noqa: PLC0415

    try:
        ada = _hero()
        items.clone("forge_wrench", carrier("ada"))
        assert "deposit" in forge.handle_command(ada, "bank deposit wrench").lower()
        assert "vault" in forge.handle_command(ada, "bank").lower()
    finally:
        _teardown()
