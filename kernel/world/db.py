"""CARD: db -- persistence through the SQLAlchemy 2.0 ORM (SQLite or PostgreSQL).

Two tables, typed rows. The rest of the engine never sees SQL:
characters.py and accounts.py keep their function signatures and swap
their insides. Two backends behind one seam:

- Default: a single SQLite file (codeforge.db), absolute-pathed to the
  repo root (CODEFORGE_DB overrides the path); tests point DB_PATH at tmp.
- Production: set DATABASE_URL (a postgresql+psycopg:// URL) and the same
  ORM speaks to PostgreSQL. Schema is managed by Alembic migrations (see
  migrations/); create_all remains a zero-config convenience for SQLite.

Why an ORM for a game this size? The same reason the seed loaders
gate YAML: schemas make bad states unrepresentable, and the skill
transfers straight to PostgreSQL when the world outgrows one file.
"""

import os
from pathlib import Path

from sqlalchemy import Engine, ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.orm import Session as SqlSession

from kernel.world.paths import resolved_path


def _default_db_path() -> Path:
    """Where the database lives. Absolute and anchored to the repo root
    (this file's grandparent) so the server opens the SAME file no matter
    which directory it is launched from -- a cwd-relative default once
    silently created a second, empty database when run from the wrong
    place. Override with CODEFORGE_DB for tests, containers, or a chosen
    data directory."""
    return resolved_path(
        "CODEFORGE_DB",
        Path(__file__).resolve().parent.parent.parent
        / "codeforge.db",  # kernel/world/ -> repo root
    )


DB_PATH = _default_db_path()

_ENGINES: dict[str, Engine] = {}


class ArchiveBase(DeclarativeBase):
    pass


class CharacterRow(ArchiveBase):
    __tablename__ = "characters"

    name: Mapped[str] = mapped_column(primary_key=True)
    job: Mapped[str] = mapped_column(default="")
    secondary_job: Mapped[str] = mapped_column(default="")  # the equipped subjob, or "" for none
    level: Mapped[int] = mapped_column(default=1)
    xp: Mapped[int] = mapped_column(default=0)
    location: Mapped[str] = mapped_column(default="forge")
    rank: Mapped[str] = mapped_column(default="player")
    account: Mapped[str] = mapped_column(default="")
    # The sworn Order (guild-allegiance), or "". The DB column is "sworn_order" because ORDER is a
    # SQL reserved word; the Python attribute stays `order` for the rest of the code.
    order: Mapped[str] = mapped_column("sworn_order", default="")
    guild: Mapped[str] = mapped_column(default="")  # the player guild this hero belongs to, or ""
    guild_rank: Mapped[str] = mapped_column(default="")  # leader | officer | member (or "")
    # Equipped gear as a JSON map {slot: prototype_label}, or "". Items are ephemeral instances, so
    # we persist the PROTOTYPE per slot and re-clone it on restore -- worn gear survives logout.
    equipped_gear: Mapped[str] = mapped_column(default="")
    # The purse: coins earned from kills, spent at shops. A simple persisted scalar.
    coins: Mapped[int] = mapped_column(default=0)
    # The current state of this seed's quest arc, or "" (still at the start / no run). Restored into
    # the quest engine on login so a story-in-progress survives a restart; ignored across seeds.
    quest_state: Mapped[str] = mapped_column(default="")
    # Daily lockouts as a JSON map {key: "YYYY-MM-DD"}, or "". The once-a-day boss/daily bonus cap
    # makes endgame a return, not a grind (kernel.world.lockouts). Persisted; "" for new heroes.
    lockouts: Mapped[str] = mapped_column(default="")
    # Allocated attribute points as a JSON map {attribute: points}, or "". Build customization the
    # `allocate` verb spends; folded onto the job's base stats on restore. Derive-don't-store holds:
    # the points spent are canonical, the resulting stats recompute.
    allocated: Mapped[str] = mapped_column(default="")
    # The maker's trades as 'trade:practice' pairs, comma-joined, or "". Profession skill the
    # `gather`/`craft` verbs earn; level recomputes from practice on restore (derive-don't-store).
    professions: Mapped[str] = mapped_column(default="")
    # Standing with each Order as 'order:standing' pairs, comma-joined, or "". The named tier
    # recomputes from the number on restore (derive-don't-store).
    reputation: Mapped[str] = mapped_column(default="")
    # This hero's friends list: lowercase labels, comma-joined, or "" (kernel.world.friends).
    friends: Mapped[str] = mapped_column(default="")
    # Integrity metadata belongs to the persistence row, not CharacterRecord. An empty default marks
    # a row written before CX-009's additive migration; the next save replaces it with a digest.
    checksum: Mapped[str] = mapped_column(default="", server_default="")
    auth_salt: Mapped[str | None] = mapped_column(default=None)  # legacy v1 char passwords
    auth_hash: Mapped[str | None] = mapped_column(default=None)


class JobProgressRow(ArchiveBase):
    """One character's progress in ONE job. A character has many of these, one per job they
    have taken up -- so changing jobs never erases a prior job's level (derive-don't-store:
    stats recompute, but the job's earned rank is a canonical fact worth keeping)."""

    __tablename__ = "job_progress"

    character_name: Mapped[str] = mapped_column(ForeignKey("characters.name"), primary_key=True)
    job_id: Mapped[str] = mapped_column(primary_key=True)
    job_level: Mapped[int] = mapped_column(default=1)
    jp: Mapped[int] = mapped_column(default=0)  # job points available in this job
    tp: Mapped[int] = mapped_column(default=0)  # training progress toward the next milestone


class AccountRow(ArchiveBase):
    __tablename__ = "accounts"

    name: Mapped[str] = mapped_column(primary_key=True)
    auth_salt: Mapped[str] = mapped_column()
    auth_hash: Mapped[str] = mapped_column()


class GuildRow(ArchiveBase):
    """A guild's own record: guild-LEVEL state (its shared treasury), distinct from the per-member
    guild columns on characters. One row per guild, created on found, dropped on disband."""

    __tablename__ = "guilds"

    name: Mapped[str] = mapped_column(primary_key=True)
    coins: Mapped[int] = mapped_column(default=0)  # the shared treasury: deposited by members


class MailRow(ArchiveBase):
    """One stored letter: an asynchronous message a hero sent to another (who may be offline). The
    recipient reads their inbox on their own time; a letter is a row until they delete it."""

    __tablename__ = "mail"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    recipient: Mapped[str] = mapped_column(index=True)  # whose inbox it lands in
    sender: Mapped[str] = mapped_column()
    body: Mapped[str] = mapped_column()
    sent_utc: Mapped[str] = mapped_column()
    read: Mapped[bool] = mapped_column(default=False)
    # An optional attached item (a gift/parcel): a snapshot, like a vaulted item. attach_proto == ""
    # means no attachment. Cleared to "" once claimed, so an item is never claimed twice.
    attach_proto: Mapped[str] = mapped_column(default="")
    attach_name: Mapped[str] = mapped_column(default="")
    attach_mods: Mapped[str] = mapped_column(default="{}")
    attach_rarity: Mapped[str] = mapped_column(default="common")


class LooseItemRow(ArchiveBase):
    """One loose (non-worn) item a hero carries, persisted so bags survive logout. A snapshot of the
    instance: its prototype (the seed label to re-clone) plus the rolled name/mods/rarity. Equipped
    gear is NOT here (it rides the character row's equipped_gear); this is only the bag. Keyed by
    owner so a whole bag loads in one query. The keystone the auction house, mail attachments,
    and a guild item-vault build on (items with a non-player owner)."""

    __tablename__ = "loose_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner: Mapped[str] = mapped_column(index=True)  # the carrier: a player id today
    prototype: Mapped[str] = mapped_column()  # the seed label to re-clone
    name: Mapped[str] = mapped_column()  # the rolled display name
    mods: Mapped[str] = mapped_column(default="{}")  # the rolled stat modifiers, JSON
    rarity: Mapped[str] = mapped_column(default="common")


class BanRow(ArchiveBase):
    """One banned character: moderation state, checked at the login gate. Keyed by character name;
    a row means that hero is refused entry with the stored reason until an admin lifts it."""

    __tablename__ = "bans"

    name: Mapped[str] = mapped_column(primary_key=True)  # the banned character
    reason: Mapped[str] = mapped_column(default="")
    moderator: Mapped[str] = mapped_column(default="")  # who imposed it
    created_utc: Mapped[str] = mapped_column(default="")


class RewardGrantRow(ArchiveBase):
    """One payout that has already been made, so it can never be made twice.

    Keyed by the whole grant identity: the same character, the same source, the same occurrence
    is one grant. A respawning foe killed again is a NEW occurrence and gets its own row, because
    a farmable foe is meant to pay every time. See `kernel/world/reward_ledger.py`.

    This is a RECORD, not a wallet. The purse stays authoritative about what a player owns; this
    table only answers "was this grant already applied".
    """

    __tablename__ = "reward_grants"

    character: Mapped[str] = mapped_column(primary_key=True)  # the recipient
    source: Mapped[str] = mapped_column(primary_key=True)  # what paid, e.g. npc:training_dummy
    occurrence: Mapped[int] = mapped_column(primary_key=True)  # which payout from that source
    granted_utc: Mapped[str] = mapped_column(default="")  # when, for audit only


class AuctionRow(ArchiveBase):
    """One item listed for sale on the auction house. The item is ESCROWED here (an item snapshot,
    like a vaulted item) from the moment it is listed until it is bought or expires, so it is out of
    the world and cannot be double-sold. Priced in coin; expires at a world beat, when a scheduler
    sweep mails it back to the seller. The economy's marketplace, built on the persistent items
    table."""

    __tablename__ = "auction_listings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    seller: Mapped[str] = mapped_column(index=True)  # who listed it (paid when it sells)
    price: Mapped[int] = mapped_column()  # coin the buyer pays, the seller receives
    expiry_beat: Mapped[int] = mapped_column(index=True)  # the world beat it lapses at
    prototype: Mapped[str] = mapped_column()  # the escrowed item snapshot (re-clone on buy/return)
    name: Mapped[str] = mapped_column()
    mods: Mapped[str] = mapped_column(default="{}")
    rarity: Mapped[str] = mapped_column(default="common")


def engine_url() -> str:
    """The SQLAlchemy URL in force. DATABASE_URL wins (PostgreSQL in production);
    otherwise a SQLite file at DB_PATH (the zero-config default for dev and tests)."""
    url = os.environ.get("DATABASE_URL", "").strip()
    return url or f"sqlite:///{DB_PATH}"


def open_archive_session() -> SqlSession:
    """A working archive session on the current backend. Engines are cached per URL.
    For SQLite the tables are created on first contact (idempotent); for PostgreSQL
    Alembic owns the schema, but create_all is a harmless checkfirst no-op if migrated."""
    url = engine_url()
    engine = _ENGINES.get(url)
    if engine is None:
        engine = create_engine(url)
        ArchiveBase.metadata.create_all(engine)  # checkfirst=True: a no-op once migrated
        _ENGINES[url] = engine
    return SqlSession(engine)


def backup_db(dest_dir: Path | None = None) -> Path:
    """Make a consistent, online copy of the SQLite database (safe while the server runs) under
    a timestamped file, and return its path. The live public demo had no recovery path; `make
    backup` files a snapshot. Refuses loud on a non-SQLite backend (use pg_dump for PostgreSQL)."""
    import sqlite3
    from contextlib import closing
    from datetime import UTC, datetime

    url = engine_url()
    if not url.startswith("sqlite"):
        raise RuntimeError(
            f"backup_db supports SQLite only; the backend is {url.split(':', 1)[0]}. "
            "For PostgreSQL use pg_dump (see docs/database.md)."
        )
    if not Path(DB_PATH).exists():
        raise FileNotFoundError(f"no database to back up at {DB_PATH}")
    base = dest_dir if dest_dir is not None else Path(DB_PATH).parent / "backups"
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    dest = base / f"{Path(DB_PATH).stem}-{stamp}.db"
    # closing(), because a sqlite3.Connection used as a bare context manager COMMITS but never
    # CLOSES. Without this, every backup leaks two open handles on the database file: invisible on
    # POSIX (which unlinks open files happily) and fatal on Windows, which refuses to remove or
    # replace a file that any handle still holds - so the recovery path itself could not restore.
    with closing(sqlite3.connect(DB_PATH)) as src, closing(sqlite3.connect(dest)) as dst:
        src.backup(dst)  # online snapshot: consistent even under concurrent writes
    return dest


def restore_db(backup_path: Path, dest: Path | None = None) -> Path:
    """Restore a SQLite backup file over the live database (or a given dest) and return the restored
    path -- the recovery half of backup_db. Disposes any cached engine on the target so the next
    session opens the RESTORED file, not a pre-restore connection. Refuses loud on a missing backup
    or a non-SQLite backend."""
    import shutil

    url = engine_url()
    if not url.startswith("sqlite"):
        raise RuntimeError(
            f"restore_db supports SQLite only; the backend is {url.split(':', 1)[0]}. "
            "For PostgreSQL use pg_restore (see docs/database.md)."
        )
    src = Path(backup_path)
    if not src.exists():
        raise FileNotFoundError(f"no backup to restore at {src}")
    target = Path(dest) if dest is not None else Path(DB_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    dead = _ENGINES.pop(f"sqlite:///{target}", None)  # drop the stale engine on the target URL
    if dead is not None:
        dead.dispose()
    shutil.copy2(src, target)
    return target
