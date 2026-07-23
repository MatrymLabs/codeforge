# Persistence: SQLite by default, PostgreSQL for production

CodeForge persists through the SQLAlchemy 2.0 ORM behind one seam (`parts/world/db.py`). The rest
of the engine never sees SQL. Two backends live behind that seam:

| Backend | When | Config | Schema |
|---|---|---|---|
| **SQLite** (default) | dev, tests, offline play, the container demo | none - a file at the repo root (`CODEFORGE_DB` overrides the path) | `create_all` (zero-config) |
| **PostgreSQL** | production-shaped runs | `DATABASE_URL=postgresql+psycopg://...` | **Alembic migrations** (`migrations/`) |

`engine_url()` chooses: `DATABASE_URL` wins; otherwise a SQLite file at `DB_PATH`. The same
typed models (`CharacterRow`, `AccountRow`) run on both.

## Run against PostgreSQL locally

```bash
make db-up          # start Postgres via docker-compose (data in a named volume)
export DATABASE_URL=postgresql+psycopg://codeforge:codeforge@localhost:5432/codeforge  # pragma: allowlist secret
make db-migrate     # alembic upgrade head -> builds the schema
codeforge api       # the app now speaks to Postgres; GET / dashboard, /characters, ...
make db-down        # stop it
```

Install the driver with the optional extra: `pip install "codeforge[postgres]"` (psycopg 3).
SQLite needs nothing extra.

## Migrations (Alembic)

The schema is versioned. `migrations/env.py` reads the live URL from `engine_url()` and the
target metadata from `ArchiveBase.metadata`, so `alembic` targets whatever backend the app
targets and autogenerate sees the real ORM tables.

```bash
make db-migrate                                   # apply migrations (upgrade head)
alembic revision --autogenerate -m "add a column" # draft the next migration from a model change
alembic downgrade -1                              # step back one
```

`create_all` remains the zero-config convenience for the SQLite dev path; Alembic is the
source of truth for evolving a real (Postgres) schema.

## How it stays honest / safe

- **Tests never touch a real database.** The `conftest` autouse fixture quarantines every
  unit test onto a fresh tmp SQLite file *and clears any ambient `DATABASE_URL`*, so a
  developer's shell can never redirect the suite at production.
- **The Postgres proof is real but isolated.** `tests/test_postgres_integration.py` builds
  its own engine from `POSTGRES_TEST_URL` and round-trips the ORM on a real Postgres. It is
  skipped unless that URL is set; a dedicated (non-required) CI job runs it against a Postgres
  service container, after `alembic upgrade head`.
- **The driver is an optional extra**, folded into the dependency gate (`make deps`) and
  justified in the ledger. codeforge core runs on stdlib `sqlite3` with no extra installed.

## Backup and restore

The live demo persists to a SQLite file (`codeforge.db`) and, before this, had no recovery path.

**Back up** (safe while the server is running - it uses SQLite's online `.backup`):

```
make backup          # -> backups/codeforge-<UTC-timestamp>.db (git-ignored, reproducible)
```

`parts.world.db.backup_db()` files a consistent snapshot even under concurrent writes. On a PostgreSQL
backend (`DATABASE_URL` set) it refuses loud and points you to `pg_dump`.

**Restore** (SQLite):

1. Stop the server (`make ritual-down`, or kill the `spark`/gateway process; `lsof -i :4000`).
2. Copy a snapshot over the live file: `cp backups/codeforge-<stamp>.db codeforge.db`.
3. Restart.

**Schema-drift caveat.** `open_archive_session` runs `create_all(checkfirst=True)`, which creates
missing *tables* but never missing *columns*. So if the ORM gains a column, a plain restart yields
a silent "no such column" at runtime. After any model change, run the migration, not just a
restart:

```
alembic upgrade head
```
