"""Alembic environment: migrations run against the same models and URL the engine uses.

The URL comes from `parts.db.engine_url()` (DATABASE_URL for PostgreSQL, else the SQLite
file), so `alembic upgrade head` targets whatever backend the app targets. The target
metadata is `ArchiveBase.metadata`, so autogenerate sees the real ORM tables.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from parts.db import ArchiveBase, engine_url

config = context.config
# Feed the live URL in, overriding the placeholder in alembic.ini.
config.set_main_option("sqlalchemy.url", engine_url())

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = ArchiveBase.metadata


def run_migrations_offline() -> None:
    """Emit SQL without a live connection (`alembic upgrade --sql`)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite-safe ALTERs; harmless on PostgreSQL
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
