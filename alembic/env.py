from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, event, pool

from app.config import settings
from app.db import Base
from app import models  # noqa: F401


config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    if connectable.dialect.name == "sqlite":
        @event.listens_for(connectable, "connect")
        def sqlite_migration_connection(dbapi_connection, _record):
            # Batch rebuilds must not trigger incoming CASCADE/RESTRICT actions.
            # Explicit BEGIN below makes SQLite DDL and data changes atomic;
            # foreign_key_check validates the complete result before commit.
            dbapi_connection.isolation_level = None
            dbapi_connection.execute("PRAGMA foreign_keys=OFF")

        @event.listens_for(connectable, "begin")
        def sqlite_begin(connection):
            connection.exec_driver_sql("BEGIN")

    with connectable.connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        context.configure(connection=connection, target_metadata=target_metadata,
                          **({"transactional_ddl": True} if sqlite else {}))
        try:
            with context.begin_transaction():
                context.run_migrations()
                if sqlite and connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
                    raise ValueError("Migration produced invalid foreign keys; changes were rolled back.")
        finally:
            if sqlite:
                # Use the DBAPI cursor to avoid opening another transaction
                # before restoring enforcement on this migration connection.
                connection.connection.driver_connection.execute("PRAGMA foreign_keys=ON")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
