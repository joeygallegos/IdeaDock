"""Upgrade storage, recognizing only the two documented unversioned SQLite schemas."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine


ROOT = Path(__file__).resolve().parent.parent
BASELINES = ("0001_initial_schema", "0002_item_epics_many_to_many")


def _default(value: str | None) -> str | None:
    # SQLite reflects equivalent SQLAlchemy/Alembic defaults with different quoting.
    if value is None:
        return None
    normalized = value.strip("()'\"")
    return "CURRENT_TIMESTAMP" if normalized.upper() == "CURRENT_TIMESTAMP" else normalized


def _schema(inspector) -> dict:
    """Compare structural constraints, not generated constraint/index names."""
    result = {}
    for table in sorted(set(inspector.get_table_names()) - {"alembic_version"}):
        columns = tuple(sorted(
            (
                column["name"],
                str(column["type"]).upper(),
                column["nullable"],
                _default(column["default"]),
            )
            for column in inspector.get_columns(table)
        ))
        foreign_keys = tuple(sorted(
            (
                tuple(key["constrained_columns"]),
                key["referred_table"],
                tuple(key["referred_columns"]),
                key.get("options", {}).get("ondelete", "").upper(),
                key.get("options", {}).get("onupdate", "").upper(),
            )
            for key in inspector.get_foreign_keys(table)
        ))
        indexes = tuple(sorted(
            (tuple(index["column_names"]), bool(index["unique"]))
            for index in inspector.get_indexes(table)
        ))
        unique_constraints = tuple(sorted(
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(table)
        ))
        checks = tuple(sorted(
            constraint["sqltext"] for constraint in inspector.get_check_constraints(table)
        ))
        result[table] = (
            columns,
            tuple(inspector.get_pk_constraint(table)["constrained_columns"]),
            foreign_keys,
            indexes,
            unique_constraints,
            checks,
        )
    return result


def _known_schemas() -> dict:
    # Derive historical shapes from their immutable migration files rather than
    # current ORM models, which will evolve independently of legacy installations.
    engine = create_engine("sqlite:///:memory:")
    schemas = {}
    try:
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                for revision in BASELINES:
                    path = ROOT / "alembic" / "versions" / f"{revision}.py"
                    spec = importlib.util.spec_from_file_location(revision, path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    module.upgrade()
                    schemas[revision] = _schema(inspect(connection))
    finally:
        engine.dispose()
    return schemas


def detect_baseline(engine: Engine) -> str | None:
    """Read-only: identify a safe stamp, or return None for normal Alembic upgrade."""
    with engine.connect() as connection:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        if "alembic_version" in tables:
            # A crashed/abandoned migration may leave an empty version table. Its
            # mere existence is not evidence that a legacy schema was migrated.
            versions = connection.execute(text("SELECT version_num FROM alembic_version")).all()
            if versions:
                return None
        if not tables - {"alembic_version"}:
            return None
        if engine.dialect.name != "sqlite":
            raise ValueError(
                "Existing unversioned database is not SQLite. Review its schema and "
                "migration baseline manually; no revision has been recorded."
            )
        actual = _schema(inspector)
        for revision, expected in _known_schemas().items():
            if actual == expected:
                return revision
    raise ValueError(
        "Unversioned SQLite schema does not exactly match the supported 0001 or 0002 "
        "baseline. Stop and review the schema before migrating; no revision has been recorded."
    )


def migrate_database() -> None:
    from app.config import settings

    engine = create_engine(settings.database_url, future=True)
    try:
        baseline = detect_baseline(engine)
    finally:
        engine.dispose()
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    if baseline is not None:
        # Both verified shapes contain the complete 0001 schema. Replay idempotent
        # 0002 even when item_epics exists, repairing missing legacy memberships.
        # Never stamp head: that would skip creation of the new board tables.
        print(f"Recognized unversioned SQLite baseline {baseline}; replaying upgrades from 0001.")
        command.stamp(config, BASELINES[0])
    command.upgrade(config, "head")


if __name__ == "__main__":
    try:
        migrate_database()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
