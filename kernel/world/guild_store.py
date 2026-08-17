"""CARD: guild_store -- persistence for a guild's own record (its shared treasury).

The guild's per-member state lives as columns on characters (character_store); this is the other
half: the guild-LEVEL record, one row per guild, holding the shared treasury. Kept small and
deliberate, like the guild it serves: create a row when a guild is founded, read/adjust its coins as
members bank, drop it on disband. SQLAlchemy and kernel.world.db are imported LAZILY inside the
methods so this adapter never pulls the ORM onto the hot `import forge` path (EXP-003).

A guild coin balance is a gameplay fact with no auth to protect, so there is no merge-save law here:
one simple table, read and written directly.
"""

from __future__ import annotations


def ensure(name: str) -> None:
    """Create a guild's treasury row (at zero) if it does not exist yet. Called on found()."""
    from kernel.world.db import GuildRow, open_archive_session

    with open_archive_session() as db:
        if db.get(GuildRow, name) is None:
            db.add(GuildRow(name=name, coins=0))
            db.commit()


def remove(name: str) -> None:
    """Delete a guild's treasury row (on disband). A no-op if it is already gone."""
    from kernel.world.db import GuildRow, open_archive_session

    with open_archive_session() as db:
        row = db.get(GuildRow, name)
        if row is not None:
            db.delete(row)
            db.commit()


def coins(name: str) -> int:
    """The guild's current treasury balance (0 if it has no row)."""
    from kernel.world.db import GuildRow, open_archive_session

    with open_archive_session() as db:
        row = db.get(GuildRow, name)
        return row.coins if row is not None else 0


def adjust(name: str, delta: int) -> int:
    """Add `delta` (may be negative) to a guild's treasury and return the new balance. Creates the
    row at zero first if needed. Never lets the balance go below zero (a withdrawal is checked by
    the caller against the balance; this is the storage floor, not the rule)."""
    from kernel.world.db import GuildRow, open_archive_session

    with open_archive_session() as db:
        row = db.get(GuildRow, name) or GuildRow(name=name, coins=0)
        row.coins = max(0, row.coins + delta)
        db.add(row)
        db.commit()
        return row.coins
