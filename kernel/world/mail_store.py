"""CARD: mail_store -- persistence for asynchronous player-to-player letters.

The storage half of mail: send a letter (a row), read a hero's inbox newest-first, mark one read,
delete one. A `Letter` value object crosses the boundary so callers never touch an ORM row.
SQLAlchemy and kernel.world.db are imported LAZILY inside the functions so this adapter never pulls
the ORM onto the hot `import forge` path (EXP-003).

Delete is scoped to the recipient: a letter can only be removed from the inbox it belongs to, so one
hero can never delete another's mail by guessing an id. No auth is stored here; a message body is
plain text a caller has already sanitized for its transport.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Letter:
    """One delivered letter as plain data (no ORM leak). `attachment` is an unclaimed item snapshot
    (prototype + rolled name/mods/rarity) or None when the letter carries no parcel."""

    id: int
    sender: str
    body: str
    sent_utc: str
    read: bool
    attachment: dict[str, Any] | None = None


def _attachment_of(row: Any) -> dict[str, Any] | None:
    """A row's unclaimed item attachment as a re-clone snapshot, or None if it carries none."""
    if not row.attach_proto:
        return None
    try:
        mods = json.loads(row.attach_mods)
    except (ValueError, TypeError):
        mods = {}
    return {
        "prototype": row.attach_proto,
        "name": row.attach_name,
        "mods": mods if isinstance(mods, dict) else {},
        "rarity": row.attach_rarity,
    }


def send(
    recipient: str,
    sender: str,
    body: str,
    *,
    sent_utc: str,
    attachment: dict[str, Any] | None = None,
) -> None:
    """Deliver a letter into `recipient`'s inbox, optionally carrying an item snapshot parcel."""
    from kernel.world.db import MailRow, open_archive_session  # noqa: PLC0415

    with open_archive_session() as db:
        row = MailRow(recipient=recipient, sender=sender, body=body, sent_utc=sent_utc, read=False)
        if attachment is not None:
            row.attach_proto = str(attachment["prototype"])
            row.attach_name = str(attachment.get("name", ""))
            row.attach_mods = json.dumps(attachment.get("mods", {}), sort_keys=True)
            row.attach_rarity = str(attachment.get("rarity", "common"))
        db.add(row)
        db.commit()


def claim(letter_id: int, recipient: str) -> dict[str, Any] | None:
    """Take a letter's attached item (scoped to its recipient), returning its snapshot and clearing
    the attachment so it can never be claimed twice. None if there is no such letter for that
    recipient, or it carries nothing to claim."""
    from kernel.world.db import MailRow, open_archive_session  # noqa: PLC0415

    with open_archive_session() as db:
        row = db.get(MailRow, letter_id)
        if row is None or row.recipient != recipient or not row.attach_proto:
            return None
        snapshot = _attachment_of(row)
        row.attach_proto = ""  # consumed: the letter keeps its text, the parcel is gone
        db.commit()
        return snapshot


def inbox(recipient: str) -> list[Letter]:
    """A hero's inbox, newest first (highest id = most recent)."""
    from sqlalchemy import select  # noqa: PLC0415

    from kernel.world.db import MailRow, open_archive_session  # noqa: PLC0415

    with open_archive_session() as db:
        rows = db.scalars(
            select(MailRow).where(MailRow.recipient == recipient).order_by(MailRow.id.desc())
        )
        return [Letter(r.id, r.sender, r.body, r.sent_utc, r.read, _attachment_of(r)) for r in rows]


def count(recipient: str) -> int:
    """How many letters sit in a hero's inbox (used to bound its growth)."""
    from sqlalchemy import func, select  # noqa: PLC0415

    from kernel.world.db import MailRow, open_archive_session  # noqa: PLC0415

    with open_archive_session() as db:
        return (
            db.scalar(
                select(func.count()).select_from(MailRow).where(MailRow.recipient == recipient)
            )
            or 0
        )


def unread_count(recipient: str) -> int:
    """How many UNREAD letters wait in a hero's inbox (for a client's mail badge). A COUNT query, so
    it stays cheap enough to read on the state tick without fetching every letter."""
    from sqlalchemy import func, select  # noqa: PLC0415

    from kernel.world.db import MailRow, open_archive_session  # noqa: PLC0415

    with open_archive_session() as db:
        return (
            db.scalar(
                select(func.count())
                .select_from(MailRow)
                .where(MailRow.recipient == recipient, MailRow.read.is_(False))
            )
            or 0
        )


def mark_read(letter_id: int) -> None:
    """Mark one letter read. A no-op if it no longer exists."""
    from kernel.world.db import MailRow, open_archive_session  # noqa: PLC0415

    with open_archive_session() as db:
        row = db.get(MailRow, letter_id)
        if row is not None:
            row.read = True
            db.commit()


def delete(letter_id: int, recipient: str) -> bool:
    """Delete a letter, but ONLY from its own recipient's inbox. Returns True if one was removed,
    False if there was none with that id for that recipient (so no one deletes another's mail)."""
    from kernel.world.db import MailRow, open_archive_session  # noqa: PLC0415

    with open_archive_session() as db:
        row = db.get(MailRow, letter_id)
        if row is None or row.recipient != recipient:
            return False
        db.delete(row)
        db.commit()
        return True
