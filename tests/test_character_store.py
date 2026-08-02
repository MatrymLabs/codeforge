"""Contract tests for the CharacterStore port -- the keel persistence seam, proven clean.

One behavioral contract, run against BOTH adapters: the pure in-memory store (the contract test) and
the SQLAlchemy store over the quarantined tmp database (the integration test). Both must satisfy the
same port, so a hero's saved row can be persisted without characters.py touching a framework
(docs/persistence_ports.md). The end-to-end save/restore behaviour stays pinned by the wider suite;
this file pins the storage boundary -- above all the MERGE-SAVE LAW: a gameplay save never rewrites
the auth columns, so it can never blank a stored password (architecture law #6).
"""

from __future__ import annotations

import pytest

from kernel.world.character_store import (
    CharacterRecord,
    CharacterStore,
    InMemoryCharacterStore,
)
from kernel.world.character_store_sql import SqlCharacterStore


@pytest.fixture(params=["memory", "sql"])
def store(request):
    if request.param == "memory":
        return InMemoryCharacterStore()
    return SqlCharacterStore()


def test_an_unknown_character_is_not_found(store):
    assert store.find("nobody_here") is None


def test_upsert_full_then_find_round_trips_every_column(store):
    record = CharacterRecord(
        name="matrym",
        job="engineer",
        secondary_job="scout",
        level=7,
        xp=420,
        location="courtyard",
        rank="wizard",
        account="matlabs",
        order="forge",
        equipped_gear='{"hand": {"prototype": "blade"}}',
        coins=99,
        quest_state="chapter_2",
        auth_salt="aa11",
        auth_hash="beefcafe",
    )
    store.upsert_full(record)
    assert store.find("matrym") == record


def test_upsert_gameplay_saves_state_but_never_blanks_the_password(store):
    # the merge-save law: seed a password via a full write, then a gameplay save must preserve it
    store.upsert_full(CharacterRecord(name="matrym", auth_salt="aa11", auth_hash="beefcafe"))
    store.upsert_gameplay(CharacterRecord(name="matrym", level=5, location="deep_road", coins=12))
    saved = store.find("matrym")
    assert saved is not None
    assert saved.level == 5 and saved.location == "deep_road" and saved.coins == 12  # state saved
    assert saved.auth_salt == "aa11" and saved.auth_hash == "beefcafe"  # password survived


def test_upsert_gameplay_on_a_brand_new_row_stores_no_auth(store):
    store.upsert_gameplay(CharacterRecord(name="drifter", level=3))
    saved = store.find("drifter")
    assert saved is not None
    assert saved.level == 3
    assert saved.auth_salt is None and saved.auth_hash is None


def test_set_rank_updates_only_the_rank(store):
    store.upsert_full(CharacterRecord(name="matrym", level=4, rank="player", auth_salt="aa11"))
    assert store.set_rank("matrym", "owner") is True
    saved = store.find("matrym")
    assert saved is not None
    assert saved.rank == "owner"
    assert saved.level == 4 and saved.auth_salt == "aa11"  # nothing else disturbed


def test_set_rank_on_a_missing_character_is_refused(store):
    assert store.set_rank("ghost", "owner") is False


def test_both_adapters_satisfy_the_port():
    assert isinstance(InMemoryCharacterStore(), CharacterStore)
    assert isinstance(SqlCharacterStore(), CharacterStore)


# --- the domain doors run over an injected store, no database touched ------------------


def test_the_character_doors_run_on_an_injected_store():
    """load_character / put_record / save_character / set_rank over a pure in-memory store, and the
    merge-save law holds through the public doors too: a save never wipes a stored password."""
    from kernel.world.characters import load_character, put_record, save_character, set_rank
    from kernel.world.session import Session

    mem = InMemoryCharacterStore()
    put_record("matrym", {"level": 2, "auth": {"salt": "aa11", "hash": "beefcafe"}}, store=mem)
    assert load_character("matrym", store=mem)["level"] == 2
    assert load_character("stranger", store=mem) is None

    hero = Session(player_id="matrym", named=True, location="deep_road")
    hero.level = 6
    save_character(hero, store=mem)  # a gameplay save
    reloaded = load_character("matrym", store=mem)
    assert reloaded["level"] == 6 and reloaded["location"] == "deep_road"  # state saved
    assert reloaded["auth"] == {"salt": "aa11", "hash": "beefcafe"}  # password preserved

    assert set_rank("matrym", "owner", store=mem) == "matrym is now rank: owner."
    assert "No saved character" in set_rank("ghost", "owner", store=mem)
