"""CARD: character_store_sql -- the SQLAlchemy adapter for the CharacterStore port.

The framework kept behind the character-persistence boundary. `character_store` (the domain) names
the `CharacterStore` port; this adapter is the only place the `characters` table is read or written
for a hero's saved row. It preserves the merge-save law exactly: `upsert_gameplay` sets the gameplay
columns and leaves auth_salt/auth_hash alone, so a gameplay save can never blank a stored password;
`upsert_full` writes the auth columns too.

SQLAlchemy and parts.world.db are imported LAZILY inside the methods, so importing this adapter (and
so characters.py, which lazily reaches it) never triggers the ~400ms SQLAlchemy import on the hot
`import forge` path (EXP-003).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from parts.world.character_store import CharacterRecord

if TYPE_CHECKING:
    from parts.world.db import CharacterRow


class SqlCharacterStore:
    """A CharacterStore backed by the SQL `characters` table (one row per named hero)."""

    def find(self, name: str) -> CharacterRecord | None:
        from parts.world.db import CharacterRow, open_archive_session

        with open_archive_session() as db:
            row = db.get(CharacterRow, name)
            if row is None:
                return None
            return CharacterRecord(
                name=row.name,
                job=row.job,
                secondary_job=row.secondary_job,
                level=row.level,
                xp=row.xp,
                location=row.location,
                rank=row.rank,
                account=row.account,
                order=row.order,
                guild=row.guild,
                guild_rank=row.guild_rank,
                equipped_gear=row.equipped_gear,
                coins=row.coins,
                quest_state=row.quest_state,
                allocated=row.allocated,
                professions=row.professions,
                reputation=row.reputation,
                friends=row.friends,
                auth_salt=row.auth_salt,
                auth_hash=row.auth_hash,
            )

    def upsert_full(self, record: CharacterRecord) -> None:
        from parts.world.db import CharacterRow, open_archive_session

        with open_archive_session() as db:
            row = db.get(CharacterRow, record.name) or CharacterRow(name=record.name)
            _apply_gameplay(row, record)
            row.auth_salt = record.auth_salt
            row.auth_hash = record.auth_hash
            db.add(row)
            db.commit()

    def upsert_gameplay(self, record: CharacterRecord) -> None:
        from parts.world.db import CharacterRow, open_archive_session

        with open_archive_session() as db:
            row = db.get(CharacterRow, record.name) or CharacterRow(name=record.name)
            _apply_gameplay(row, record)
            # auth columns deliberately untouched -- the merge-save law (architecture law #6)
            db.add(row)
            db.commit()

    def set_rank(self, name: str, rank: str) -> bool:
        from parts.world.db import CharacterRow, open_archive_session

        with open_archive_session() as db:
            row = db.get(CharacterRow, name)
            if row is None:
                return False
            row.rank = rank
            db.commit()
            return True

    def members_of_guild(self, guild: str) -> list[str]:
        if not guild:
            return []
        from sqlalchemy import select

        from parts.world.db import CharacterRow, open_archive_session

        with open_archive_session() as db:
            rows = db.scalars(select(CharacterRow.name).where(CharacterRow.guild == guild))
            return sorted(rows)

    def set_guild(self, name: str, guild: str, guild_rank: str) -> bool:
        from parts.world.db import CharacterRow, open_archive_session

        with open_archive_session() as db:
            row = db.get(CharacterRow, name)
            if row is None:
                return False
            row.guild = guild
            row.guild_rank = guild_rank
            db.commit()  # gameplay columns only; auth untouched (the merge-save law)
            return True


def _apply_gameplay(row: CharacterRow, record: CharacterRecord) -> None:
    """Copy the gameplay columns (everything but auth) from a record onto an ORM row."""
    row.job = record.job
    row.secondary_job = record.secondary_job
    row.level = record.level
    row.xp = record.xp
    row.location = record.location
    row.rank = record.rank
    row.account = record.account
    row.order = record.order
    row.guild = record.guild
    row.guild_rank = record.guild_rank
    row.equipped_gear = record.equipped_gear
    row.coins = record.coins
    row.quest_state = record.quest_state
    row.allocated = record.allocated
    row.professions = record.professions
    row.reputation = record.reputation
    row.friends = record.friends
