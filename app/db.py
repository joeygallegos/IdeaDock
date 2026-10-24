from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _sqlite_db_path(database_url: str) -> Path | None:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return None

    database = url.database or ""
    if not database or database == ":memory:" or database.startswith("file:"):
        return None

    path = Path(database)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _prepare_sqlite_path() -> None:
    sqlite_path = _sqlite_db_path(settings.database_url)
    if sqlite_path is not None:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)


def _create_engine():
    connect_args: dict[str, object] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(settings.database_url, future=True, connect_args=connect_args)


_prepare_sqlite_path()
engine = _create_engine()


if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def bootstrap_database() -> None:
    from app import models  # noqa: F401

    if should_create_all():
        Base.metadata.create_all(bind=engine)
    backfill_legacy_item_epics()


def should_create_all() -> bool:
    try:
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
    except SQLAlchemyError:
        return True

    if not table_names:
        return True

    managed_tables = set(Base.metadata.tables.keys())
    return not bool(table_names & managed_tables) and "alembic_version" not in table_names


def backfill_legacy_item_epics() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "items" not in table_names or "item_epics" not in table_names:
        return

    item_columns = {column["name"] for column in inspector.get_columns("items")}
    if "epic_id" not in item_columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO item_epics (item_id, epic_id)
                SELECT items.id, items.epic_id
                FROM items
                LEFT JOIN item_epics
                    ON item_epics.item_id = items.id
                    AND item_epics.epic_id = items.epic_id
                WHERE items.epic_id IS NOT NULL
                    AND item_epics.item_id IS NULL
                """
            )
        )
