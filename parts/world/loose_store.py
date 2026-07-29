"""CARD: loose_store -- persistence for a hero's loose inventory (their bag survives logout).

The storage half of Keystone A. Equipped gear already survives logout on the character row; this
persists the REST of the bag, so a looted sword you did not equip is still yours next login. A row
is a snapshot (prototype + rolled name/mods/rarity); the domain layer (characters.py) turns a live
item into a snapshot on save and re-clones it on restore.

save() replaces a hero's whole bag at once (delete-then-insert), so it always mirrors the live
inventory exactly, with no drift from partial updates. SQLAlchemy and parts.world.db are imported
LAZILY inside the functions so this adapter never pulls the ORM onto the hot `import forge` path
(EXP-003). No auth is stored here; an item is gameplay data with no secret to protect.
"""

from __future__ import annotations

import json
from typing import Any


def save(owner: str, snapshots: list[dict[str, Any]]) -> None:
    """Replace `owner`'s entire loose bag with `snapshots` (each {prototype, name, mods, rarity}).
    Delete-then-insert under one commit, so the stored bag is always exactly the live one."""
    from sqlalchemy import delete

    from parts.world.db import LooseItemRow, open_archive_session

    with open_archive_session() as db:
        db.execute(delete(LooseItemRow).where(LooseItemRow.owner == owner))
        for snap in snapshots:
            db.add(
                LooseItemRow(
                    owner=owner,
                    prototype=str(snap["prototype"]),
                    name=str(snap.get("name", "")),
                    mods=json.dumps(snap.get("mods", {}), sort_keys=True),
                    rarity=str(snap.get("rarity", "common")),
                )
            )
        db.commit()


def _row_snapshot(row: Any) -> dict[str, Any]:
    """One stored row as a re-clone-ready snapshot; a malformed mods blob decodes to {}."""
    try:
        mods = json.loads(row.mods)
    except (ValueError, TypeError):
        mods = {}
    return {
        "prototype": row.prototype,
        "name": row.name,
        "mods": mods if isinstance(mods, dict) else {},
        "rarity": row.rarity,
    }


def stow(owner: str, snapshot: dict[str, Any]) -> int:
    """Add ONE item to an owner's storage (a bank vault, a guild vault) and return its new row id.
    The item-level complement to save(): where save() mirrors a whole live bag, stow() puts a single
    item away to sit in storage until it is taken back out."""
    from parts.world.db import LooseItemRow, open_archive_session

    with open_archive_session() as db:
        row = LooseItemRow(
            owner=owner,
            prototype=str(snapshot["prototype"]),
            name=str(snapshot.get("name", "")),
            mods=json.dumps(snapshot.get("mods", {}), sort_keys=True),
            rarity=str(snapshot.get("rarity", "common")),
        )
        db.add(row)
        db.commit()
        return row.id


def take(row_id: int, owner: str) -> dict[str, Any] | None:
    """Remove ONE stored item by id and return its snapshot, but ONLY from its own owner's storage,
    so no one withdraws another's goods by guessing an id. None if there is no such row for that
    owner (already taken, or not theirs)."""
    from parts.world.db import LooseItemRow, open_archive_session

    with open_archive_session() as db:
        row = db.get(LooseItemRow, row_id)
        if row is None or row.owner != owner:
            return None
        snapshot = _row_snapshot(row)
        db.delete(row)
        db.commit()
        return snapshot


def contents(owner: str) -> list[tuple[int, dict[str, Any]]]:
    """An owner's stored items as (row_id, snapshot) pairs, oldest first, so a client or a verb can
    list them and refer to one by id. Empty for empty storage."""
    from sqlalchemy import select

    from parts.world.db import LooseItemRow, open_archive_session

    with open_archive_session() as db:
        rows = db.scalars(
            select(LooseItemRow).where(LooseItemRow.owner == owner).order_by(LooseItemRow.id)
        )
        return [(row.id, _row_snapshot(row)) for row in rows]


def load(owner: str) -> list[dict[str, Any]]:
    """A hero's persisted loose bag as snapshots ready to re-clone. Empty for a hero who carried
    nothing. A malformed mods blob (should not happen) decodes to {} rather than crash login."""
    from sqlalchemy import select

    from parts.world.db import LooseItemRow, open_archive_session

    with open_archive_session() as db:
        rows = db.scalars(select(LooseItemRow).where(LooseItemRow.owner == owner))
        return [_row_snapshot(row) for row in rows]
