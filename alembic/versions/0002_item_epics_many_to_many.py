from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_item_epics_many_to_many"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "item_epics" not in inspector.get_table_names():
        op.create_table(
            "item_epics",
            sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("epic_id", sa.Integer(), sa.ForeignKey("epics.id", ondelete="CASCADE"), primary_key=True),
        )

    item_columns = {column["name"] for column in inspector.get_columns("items")}
    if "epic_id" in item_columns:
        op.execute(
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


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "item_epics" in inspector.get_table_names():
        op.drop_table("item_epics")
