"""Test twin for parts/repository.py -- the in-memory Repository and its Protocol boundary."""

from dataclasses import dataclass

import pytest
from hypothesis import given
from hypothesis import strategies as st

from parts.repository import (
    DuplicateKey,
    InMemoryRepository,
    NotFound,
    Repository,
)


@dataclass(frozen=True)
class Widget:
    id: str
    name: str


def _repo() -> InMemoryRepository[Widget, str]:
    return InMemoryRepository(lambda w: w.id)


def test_add_then_get_round_trips_the_entity():
    repo = _repo()
    w = Widget("a", "Anvil")
    assert repo.add(w) is w
    assert repo.get("a") == w
    assert repo.count() == 1


def test_get_of_a_missing_key_is_none_but_require_raises():
    repo = _repo()
    assert repo.get("nope") is None
    with pytest.raises(NotFound):
        repo.require("nope")


def test_adding_a_duplicate_key_fails_loud():
    repo = _repo()
    repo.add(Widget("a", "Anvil"))
    with pytest.raises(DuplicateKey):
        repo.add(Widget("a", "Anchor"))


def test_update_replaces_and_refuses_an_absent_entity():
    repo = _repo()
    repo.add(Widget("a", "Anvil"))
    repo.update(Widget("a", "Anvil Mk2"))
    assert repo.require("a").name == "Anvil Mk2"
    with pytest.raises(NotFound):
        repo.update(Widget("z", "Ghost"))


def test_remove_reports_whether_it_deleted():
    repo = _repo()
    repo.add(Widget("a", "Anvil"))
    assert repo.remove("a") is True
    assert repo.remove("a") is False  # already gone
    assert repo.count() == 0


def test_the_in_memory_repo_satisfies_the_repository_protocol():
    assert isinstance(_repo(), Repository)  # runtime_checkable Protocol


def test_it_is_identity_agnostic_and_works_with_int_keys():
    # No base class, no `.id` assumption: the key function decides identity.
    repo: InMemoryRepository[int, int] = InMemoryRepository(lambda n: n % 10)
    repo.add(5)
    assert repo.get(5) == 5
    with pytest.raises(DuplicateKey):
        repo.add(15)  # 15 % 10 == 5, same key


@pytest.mark.property
@given(keys=st.lists(st.text(min_size=1, max_size=6), unique=True, max_size=40))
def test_no_accidental_data_loss_add_all_get_all_remove_all(keys):
    repo = _repo()
    for k in keys:
        repo.add(Widget(k, f"w-{k}"))
    assert repo.count() == len(keys)
    for k in keys:  # every added entity is retrievable, unchanged
        assert repo.get(k) == Widget(k, f"w-{k}")
    for k in keys:
        assert repo.remove(k) is True
    assert repo.count() == 0
