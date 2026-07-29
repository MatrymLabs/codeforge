"""CARD: mail_store -- persistence for asynchronous player-to-player letters.

The storage half of mail: send a letter (a row), read a hero's inbox newest-first, mark one read,
delete one. A `Letter` value object crosses the boundary so callers never touch an ORM row.
SQLAlchemy and parts.world.db are imported LAZILY inside the functions so this adapter never pulls
the ORM onto the hot `import forge` path (EXP-003).

Delete is scoped to the recipient: a letter can only be removed from the inbox it belongs to, so one
hero can never delete another's mail by guessing an id. No auth is stored here; a message body is
plain text a caller has already sanitized for its transport.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Letter:
    """One delivered letter as plain data (no ORM leak)."""

    id: int
    sender: str
    body: str
    sent_utc: str
    read: bool


def send(recipient: str, sender: str, body: str, *, sent_utc: str) -> None:
    """Deliver a letter into `recipient`'s inbox."""
    from parts.world.db import MailRow, open_archive_session

    with open_archive_session() as db:
        db.add(
            MailRow(recipient=recipient, sender=sender, body=body, sent_utc=sent_utc, read=False)
        )
        db.commit()


def inbox(recipient: str) -> list[Letter]:
    """A hero's inbox, newest first (highest id = most recent)."""
    from sqlalchemy import select

    from parts.world.db import MailRow, open_archive_session

    with open_archive_session() as db:
        rows = db.scalars(
            select(MailRow).where(MailRow.recipient == recipient).order_by(MailRow.id.desc())
        )
        return [Letter(r.id, r.sender, r.body, r.sent_utc, r.read) for r in rows]


def count(recipient: str) -> int:
    """How many letters sit in a hero's inbox (used to bound its growth)."""
    from sqlalchemy import func, select

    from parts.world.db import MailRow, open_archive_session

    with open_archive_session() as db:
        return (
            db.scalar(
                select(func.count()).select_from(MailRow).where(MailRow.recipient == recipient)
            )
            or 0
        )


def mark_read(letter_id: int) -> None:
    """Mark one letter read. A no-op if it no longer exists."""
    from parts.world.db import MailRow, open_archive_session

    with open_archive_session() as db:
        row = db.get(MailRow, letter_id)
        if row is not None:
            row.read = True
            db.commit()


def delete(letter_id: int, recipient: str) -> bool:
    """Delete a letter, but ONLY from its own recipient's inbox. Returns True if one was removed,
    False if there was none with that id for that recipient (so no one deletes another's mail)."""
    from parts.world.db import MailRow, open_archive_session

    with open_archive_session() as db:
        row = db.get(MailRow, letter_id)
        if row is None or row.recipient != recipient:
            return False
        db.delete(row)
        db.commit()
        return True
