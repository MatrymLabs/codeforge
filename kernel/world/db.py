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

from sqlalchemy import (
    CheckConstraint,
    Engine,
    ForeignKey,
    LargeBinary,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.engine import make_url
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
    appearance: Mapped[str] = mapped_column(default="")  # JSON presentation choices
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


class OutboxRow(ArchiveBase):
    """Durable message staged with a state change and drained by the world-beat relay."""

    __tablename__ = "outbox"

    id: Mapped[str] = mapped_column(primary_key=True)
    topic: Mapped[str] = mapped_column(index=True)
    payload: Mapped[bytes] = mapped_column(LargeBinary())
    status: Mapped[str] = mapped_column(default="pending", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[float] = mapped_column(default=0.0)


class SeedRegistryRow(ArchiveBase):
    """The relational projection of one generic Seed identity and lifecycle record.

    The Seed Kernel remains the domain owner; this row is a durable SQL-backed implementation of
    its existing ``SeedStore`` protocol. JSON is limited to the versioned audit trail and selected
    domain-module names so the registry keeps typed identity/lifecycle fields without inventing a
    second generic entity store.
    """

    __tablename__ = "seed_registry"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'running', 'stopped', 'archived')",
            name="ck_seed_registry_status",
        ),
    )

    seed_id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    owner: Mapped[str] = mapped_column(index=True)
    purpose: Mapped[str] = mapped_column(default="")
    version: Mapped[str] = mapped_column(default="0.1.0")
    created_at: Mapped[str] = mapped_column(default="")
    product_type: Mapped[str] = mapped_column(default="")
    domain_modules: Mapped[str] = mapped_column(Text(), default="[]")
    status: Mapped[str] = mapped_column(default="created", index=True)
    started_at: Mapped[str] = mapped_column(default="")
    stopped_at: Mapped[str] = mapped_column(default="")
    audit: Mapped[str] = mapped_column(Text(), default="[]")


class SeedModelRow(ArchiveBase):
    """One versioned ProjectModel owned by one Seed."""

    __tablename__ = "seed_models"

    seed_id: Mapped[str] = mapped_column(primary_key=True)
    model_id: Mapped[str] = mapped_column(primary_key=True)
    model_json: Mapped[str] = mapped_column(Text())


class SeedRunRow(ArchiveBase):
    """One append-only controlled tool-run evidence record owned by one Seed."""

    __tablename__ = "seed_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    seed_id: Mapped[str] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(index=True)
    run_json: Mapped[str] = mapped_column(Text())


class SeedArtifactRow(ArchiveBase):
    """One governed generated-artifact metadata record owned by one Seed."""

    __tablename__ = "seed_artifacts"

    seed_id: Mapped[str] = mapped_column(primary_key=True)
    artifact_id: Mapped[str] = mapped_column(primary_key=True)
    artifact_json: Mapped[str] = mapped_column(Text())


class SeedManifestEvidenceRow(ArchiveBase):
    """One immutable manifest-test evidence record owned by one Seed."""

    __tablename__ = "seed_manifest_evidence"

    seed_id: Mapped[str] = mapped_column(primary_key=True)
    evidence_id: Mapped[str] = mapped_column(primary_key=True)
    evidence_json: Mapped[str] = mapped_column(Text())


class SeedSourceRow(ArchiveBase):
    """One immutable registered source snapshot owned by one Seed."""

    __tablename__ = "seed_sources"

    seed_id: Mapped[str] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(primary_key=True)
    source_json: Mapped[str] = mapped_column(Text())


class SeedConnectorRow(ArchiveBase):
    """One durable connector lifecycle snapshot owned by one Seed."""

    __tablename__ = "seed_connectors"

    seed_id: Mapped[str] = mapped_column(primary_key=True)
    registration_id: Mapped[str] = mapped_column(primary_key=True)
    registration_json: Mapped[str] = mapped_column(Text())


class AuditEventRow(ArchiveBase):
    """One append-only hash-chain audit event in the platform SQL boundary."""

    __tablename__ = "audit_events"

    sequence: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    payload_json: Mapped[str] = mapped_column(Text())
    prior_hash: Mapped[str] = mapped_column()
    content_hash: Mapped[str] = mapped_column()


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


class EconomyTransactionRow(ArchiveBase):
    """One idempotent value movement, retained for replay and reconciliation."""

    __tablename__ = "economy_transactions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_economy_transaction_idempotency"),
    )

    transaction_id: Mapped[str] = mapped_column(primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(index=True)
    request_hash: Mapped[str] = mapped_column()
    actor: Mapped[str] = mapped_column(index=True)
    source: Mapped[str] = mapped_column()
    destination: Mapped[str] = mapped_column(default="")
    currency_amount: Mapped[int] = mapped_column(default=0)
    item_ids: Mapped[str] = mapped_column(Text(), default="[]")
    reason: Mapped[str] = mapped_column(default="")
    status: Mapped[str] = mapped_column(default="committed")
    created_at: Mapped[str] = mapped_column(default="")


class CurrencyLedgerRow(ArchiveBase):
    """One signed currency ledger entry attached to an economy transaction."""

    __tablename__ = "currency_ledger"

    entry_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(index=True)
    account: Mapped[str] = mapped_column(index=True)
    delta: Mapped[int] = mapped_column()
    balance_after: Mapped[int] = mapped_column()
    source: Mapped[str] = mapped_column()
    destination: Mapped[str] = mapped_column(default="")
    reason: Mapped[str] = mapped_column(default="")


def engine_url() -> str:
    """The SQLAlchemy URL in force. DATABASE_URL wins (PostgreSQL in production);
    otherwise CODEFORGE_DB may select a SQLite file for a deployment or test, falling back to
    DB_PATH (the zero-config default for dev and tests). Resolving the environment at call time
    keeps every compatibility import path on one configurable database boundary."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url
    configured = os.environ.get("CODEFORGE_DB", "").strip()
    path = Path(configured).expanduser().resolve() if configured else DB_PATH
    return f"sqlite:///{path}"


def _sqlite_path(url: str | None = None) -> Path:
    """Resolve the active SQLite file, including ``CODEFORGE_DB`` overrides.

    Recovery must operate on the same backend selected for ORM sessions.  Using the import-time
    ``DB_PATH`` here silently backed up the repository default when a deployment selected another
    file through ``CODEFORGE_DB``.
    """
    parsed = make_url(url or engine_url())
    if parsed.get_backend_name() != "sqlite" or not parsed.database:
        raise RuntimeError("the active backend is not a file-backed SQLite database")
    if parsed.database == ":memory:":
        raise RuntimeError("an in-memory SQLite database cannot be backed up or restored")
    return Path(parsed.database).expanduser().resolve()


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
    from datetime import UTC, datetime

    url = engine_url()
    if not url.startswith("sqlite"):
        raise RuntimeError(
            f"backup_db supports SQLite only; the backend is {url.split(':', 1)[0]}. "
            "For PostgreSQL use pg_dump (see docs/database.md)."
        )
    live = _sqlite_path(url)
    if not live.exists():
        raise FileNotFoundError(f"no database to back up at {live}")
    base = dest_dir if dest_dir is not None else live.parent / "backups"
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    dest = base / f"{live.stem}-{stamp}.db"
    with sqlite3.connect(live) as src, sqlite3.connect(dest) as dst:
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
    target = Path(dest).expanduser().resolve() if dest is not None else _sqlite_path(url)
    target.parent.mkdir(parents=True, exist_ok=True)
    dead = _ENGINES.pop(f"sqlite:///{target}", None)  # drop the stale engine on the target URL
    if dead is not None:
        dead.dispose()
    shutil.copy2(src, target)
    return target


# Register the world-owned SQL model behind the shelf-owned outbox contract. The dependency points
# from the engine toward the reusable shelf; the shelf never imports this module.
from kernel.shelf.outbox import register_sql_backend  # noqa: E402

register_sql_backend(OutboxRow, open_archive_session)
