"""CARD: character_store -- the persistence PORT for a named hero's saved row.

The domain side of character persistence, framework-free: a `CharacterRecord` value object (the
saved columns as plain data), the `CharacterStore` PORT, and a pure in-memory adapter. The SQL
adapter is character_store_sql. characters.py builds records from a Session or a casefile and reads
them back; it no longer touches an ORM row. See docs/persistence_ports.md.

The port keeps TWO upserts on purpose, because a hero's password must survive a gameplay save (the
merge-save law, architecture law #6):
  - `upsert_full` writes every column INCLUDING the auth salt/hash (the full door, put_record).
  - `upsert_gameplay` writes the gameplay columns and NEVER the auth columns, so saving a hero's
    position/level/gear can never blank their stored password. A security invariant, pinned by the
    contract test and the auth suite; do not collapse the two.

The module imports only stdlib (dataclasses, typing), so it stays engine-free on the hot
`import forge` path (EXP-003); the SQLAlchemy adapter is reached only through character_store_sql.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class CharacterRecord:
    """One saved hero as plain data: the canonical facts, derive-don't-store. auth_salt/auth_hash
    are the account-less v1 per-character credential (usually None); they ride along on reads and on
    a full write, but a gameplay save leaves them untouched."""

    name: str
    job: str = ""
    secondary_job: str = ""
    level: int = 1
    xp: int = 0
    location: str = ""
    rank: str = "player"
    account: str = ""
    order: str = ""
    equipped_gear: str = ""
    coins: int = 0
    quest_state: str = ""
    allocated: str = ""  # JSON: attribute -> allocated points (build customization)
    professions: str = ""  # 'trade:practice' pairs, comma-joined (the maker's trade skills)
    auth_salt: str | None = None
    auth_hash: str | None = None


@runtime_checkable
class CharacterStore(Protocol):
    """The persistence boundary for saved heroes. Any adapter (SQL, in-memory) satisfies this narrow
    contract; the domain depends on it, not on a framework."""

    def find(self, name: str) -> CharacterRecord | None:
        """The saved record for a name, or None if no such character exists."""
        ...

    def upsert_full(self, record: CharacterRecord) -> None:
        """Write every column, including the auth salt/hash (the full-casefile door)."""
        ...

    def upsert_gameplay(self, record: CharacterRecord) -> None:
        """Write the gameplay columns only; NEVER the auth columns (the merge-save law -- a gameplay
        save must not blank a stored password)."""
        ...

    def set_rank(self, name: str, rank: str) -> bool:
        """Set only the rank column. False if no such character exists."""
        ...


class InMemoryCharacterStore:
    """A dict-backed CharacterStore: dependency-free and deterministic, for the contract tests and a
    save-less world. Honors the merge-save law -- a gameplay upsert preserves the existing auth."""

    def __init__(self) -> None:
        self._rows: dict[str, CharacterRecord] = {}

    def find(self, name: str) -> CharacterRecord | None:
        return self._rows.get(name)

    def upsert_full(self, record: CharacterRecord) -> None:
        self._rows[record.name] = record

    def upsert_gameplay(self, record: CharacterRecord) -> None:
        from dataclasses import replace

        existing = self._rows.get(record.name)
        # carry the stored auth forward; a gameplay save never rewrites it
        self._rows[record.name] = replace(
            record,
            auth_salt=existing.auth_salt if existing else None,
            auth_hash=existing.auth_hash if existing else None,
        )

    def set_rank(self, name: str, rank: str) -> bool:
        from dataclasses import replace

        existing = self._rows.get(name)
        if existing is None:
            return False
        self._rows[name] = replace(existing, rank=rank)
        return True
