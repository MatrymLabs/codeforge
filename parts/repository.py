"""CARD: repository -- the Repository pattern: a collection-like boundary over stored entities.

A repository hides how entities are stored behind a small collection-like interface (add, get,
list, remove), so domain code never touches raw storage. `Repository` is a typed `Protocol` (the
replaceable boundary); `InMemoryRepository` is the dependency-free, dict-backed implementation for
tests, prototypes, and demos. A real database repository is a later adapter that satisfies the same
Protocol; the domain code does not change. This is the standard Repository pattern (Fowler),
reimplemented from the concept -- no code copied.

Framework-free and identity-agnostic: entities carry no base class and need no `.id`; an injected
`key_of` reads each entity's identity, so the same repository stores anything. One core, two lives:
a per-player logbook in the game (`parts/logbook`) and a records/asset registry in a practical app
(`parts/asset_registry`).

Provenance: independently_implemented_pattern (Repository pattern, Fowler). No code copied.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

_MISSING = object()  # sentinel so remove() is correct even if an entity is itself None


class RepositoryError(Exception):
    """Base for repository lookup errors."""


class DuplicateKey(RepositoryError):
    """Tried to add an entity whose key is already present."""


class NotFound(RepositoryError):
    """No entity exists for the requested key."""


@runtime_checkable
class Repository[E, K](Protocol):
    """The replaceable storage boundary: a typed, collection-like interface over entities."""

    def add(self, entity: E) -> E: ...
    def get(self, key: K) -> E | None: ...
    def require(self, key: K) -> E: ...
    def update(self, entity: E) -> E: ...
    def remove(self, key: K) -> bool: ...
    def list(self) -> list[E]: ...
    def count(self) -> int: ...


class InMemoryRepository[E, K]:
    """A dict-backed Repository. Dependency-free; identity comes from an injected `key_of`."""

    def __init__(self, key_of: Callable[[E], K]) -> None:
        self._key_of = key_of
        self._items: dict[K, E] = {}

    def add(self, entity: E) -> E:
        """Store a new entity. Raises DuplicateKey if its key is already present."""
        key = self._key_of(entity)
        if key in self._items:
            raise DuplicateKey(f"an entity with key {key!r} already exists")
        self._items[key] = entity
        return entity

    def get(self, key: K) -> E | None:
        """The entity for `key`, or None."""
        return self._items.get(key)

    def require(self, key: K) -> E:
        """The entity for `key`, or raise NotFound."""
        try:
            return self._items[key]
        except KeyError:
            raise NotFound(f"no entity with key {key!r}") from None

    def update(self, entity: E) -> E:
        """Replace an existing entity (matched by its key). Raises NotFound if absent."""
        key = self._key_of(entity)
        if key not in self._items:
            raise NotFound(f"cannot update: no entity with key {key!r}")
        self._items[key] = entity
        return entity

    def remove(self, key: K) -> bool:
        """Delete the entity for `key`. Returns True if one was removed."""
        return self._items.pop(key, _MISSING) is not _MISSING

    def list(self) -> list[E]:
        """Every stored entity, in insertion order."""
        return list(self._items.values())

    def count(self) -> int:
        """How many entities are stored."""
        return len(self._items)
