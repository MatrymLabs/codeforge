"""CARD: bans -- moderation: a banned character is refused at the login gate.

Phase 3 ops. Where the login-failure ledger bars an ADDRESS after too many bad passwords and
maintenance mode closes the door to everyone, a ban is a deliberate, persisted block on ONE
character: an admin imposes it with a reason, and that hero is turned away at the front desk until
an admin lifts it. Persisted (a bans row) so it survives a restart; keyed by name for a fast check.

Direct SQL on the bans table (ArchiveBase), lazy-imported off the hot `import forge` path, like the
guild and mail stores. No auth here; a ban is a moderation fact. The `@ban` verb records each ban
and unban to the audit log, so moderation is itself accountable.
"""

from __future__ import annotations

from datetime import UTC, datetime


def ban(name: str, reason: str, moderator: str) -> None:
    """Impose (or update) a ban on `name` with a reason and the moderator who set it."""
    from kernel.world.db import BanRow, open_archive_session  # noqa: PLC0415

    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open_archive_session() as db:
        row = db.get(BanRow, name) or BanRow(name=name)
        row.reason = reason
        row.moderator = moderator
        row.created_utc = stamp
        db.add(row)
        db.commit()


def unban(name: str) -> bool:
    """Lift a ban. True if there was one to lift, False if the hero was not banned."""
    from kernel.world.db import BanRow, open_archive_session  # noqa: PLC0415

    with open_archive_session() as db:
        row = db.get(BanRow, name)
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True


def is_banned(name: str) -> bool:
    """True if `name` is currently banned (the login-gate check)."""
    from kernel.world.db import BanRow, open_archive_session  # noqa: PLC0415

    with open_archive_session() as db:
        return db.get(BanRow, name) is not None


def reason(name: str) -> str:
    """The stored ban reason for `name`, or "" if not banned."""
    from kernel.world.db import BanRow, open_archive_session  # noqa: PLC0415

    with open_archive_session() as db:
        row = db.get(BanRow, name)
        return row.reason if row is not None else ""


def all_bans() -> list[tuple[str, str, str]]:
    """Every ban as (name, reason, moderator), for the moderation roster."""
    from sqlalchemy import select  # noqa: PLC0415

    from kernel.world.db import BanRow, open_archive_session  # noqa: PLC0415

    with open_archive_session() as db:
        rows = db.scalars(select(BanRow).order_by(BanRow.name))
        return [(row.name, row.reason, row.moderator) for row in rows]
