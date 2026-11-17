"""Attach boards and their direct uploads to explicitly chosen Item owners."""
import json
from pathlib import Path

from alembic import context, op
import sqlalchemy as sa


revision = "0004_item_board_ownership"
down_revision = "0003_visual_boards"
branch_labels = None
depends_on = None


def _owner_mapping(connection):
    owners = set(connection.execute(sa.text(
        "SELECT project_id FROM visual_boards UNION SELECT project_id FROM project_assets"
    )).scalars())
    path = context.config.attributes.get("board_owner_map") or context.get_x_argument(as_dictionary=True).get("board_owner_map")
    if not path:
        if owners:
            raise ValueError("Existing boards/uploads require an explicit Epic-to-Item JSON mapping. "
                             "Use --board-owner-map PATH or alembic -x board_owner_map=PATH upgrade head.")
        return {}
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Could not read board owner mapping JSON file.") from exc
    if not isinstance(value, dict) or any(
        not isinstance(key, str) or not key.isdecimal() or int(key) <= 0
        or type(item_id) is not int or item_id <= 0 for key, item_id in value.items()
    ):
        raise ValueError("Board owner mapping must be a JSON object of positive Epic ID keys and positive Item ID values.")
    mapping = {int(key): item_id for key, item_id in value.items()}
    if len(mapping) != len(value):
        raise ValueError("Board owner mapping contains duplicate numeric Epic IDs.")
    missing = owners - mapping.keys()
    if missing:
        raise ValueError(f"Board owner mapping is missing Epic IDs: {', '.join(map(str, sorted(missing)))}.")
    items = set(connection.execute(sa.text("SELECT id FROM items")).scalars())
    invalid = set(mapping.values()) - items
    if invalid:
        raise ValueError(f"Board owner mapping references nonexistent Item IDs: {', '.join(map(str, sorted(invalid)))}.")
    return mapping


def upgrade():
    connection = op.get_bind()
    # Resolve all ambiguous owners before any DDL; matching numeric IDs is not
    # evidence that an Epic and an Item represent the same project.
    mapping = _owner_mapping(connection)
    naming = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
    for name in ("project_assets", "visual_boards"):
        op.add_column(name, sa.Column("item_id", sa.Integer(), nullable=True))
        table = sa.table(name, sa.column("project_id", sa.Integer()), sa.column("item_id", sa.Integer()))
        for epic_id, item_id in mapping.items():
            connection.execute(table.update().where(table.c.project_id == epic_id).values(item_id=item_id))
        foreign_key = next(key for key in sa.inspect(connection).get_foreign_keys(name)
                           if key["constrained_columns"] == ["project_id"])
        # SQLite recreates the table; env.py temporarily suspends FK actions
        # inside a real transaction so incoming board references survive intact.
        with op.batch_alter_table(name, naming_convention=naming) as batch:
            batch.drop_constraint(foreign_key["name"] or f"fk_{name}_project_id_epics", type_="foreignkey")
            batch.drop_index(f"ix_{name}_project_id")
            batch.drop_column("project_id")
            batch.alter_column("item_id", existing_type=sa.Integer(), nullable=False)
            batch.create_foreign_key(f"fk_{name}_item_id_items", "items", ["item_id"], ["id"], ondelete="RESTRICT")
            batch.create_index(f"ix_{name}_item_id", ["item_id"])


def downgrade():
    # Item-to-Epic conversion is ambiguous after users change memberships. A
    # backup restore is safer than silently assigning boards to another owner.
    raise ValueError("Item-owned boards cannot be downgraded automatically; restore a pre-migration backup.")
