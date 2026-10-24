from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


item_type_enum = sa.Enum("task", "idea", "note", "someday", name="item_type", native_enum=False)
item_status_enum = sa.Enum("inbox", "next", "doing", "waiting", "done", name="item_status", native_enum=False)
priority_enum = sa.Enum("low", "med", "high", name="priority", native_enum=False)
entity_type_enum = sa.Enum(
    "person",
    "family",
    "friend",
    "vendor",
    "company",
    "service",
    "team",
    "other",
    name="entity_type",
    native_enum=False,
)
item_entity_role_enum = sa.Enum(
    "waiting_on",
    "involved",
    "reference",
    name="item_entity_role",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "epics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("normalized_name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_epics_normalized_name", "epics", ["normalized_name"], unique=True)

    op.create_table(
        "entities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("normalized_name", sa.String(length=120), nullable=False),
        sa.Column("entity_type", entity_type_enum, server_default="other", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_entities_normalized_name", "entities", ["normalized_name"], unique=True)

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("normalized_name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_tags_normalized_name", "tags", ["normalized_name"], unique=True)

    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("raw_input", sa.Text(), nullable=True),
        sa.Column("item_type", item_type_enum, server_default="idea", nullable=False),
        sa.Column("status", item_status_enum, server_default="inbox", nullable=False),
        sa.Column("priority", priority_enum, nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("epic_id", sa.Integer(), sa.ForeignKey("epics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_items_item_type", "items", ["item_type"])
    op.create_index("ix_items_status", "items", ["status"])
    op.create_index("ix_items_priority", "items", ["priority"])
    op.create_index("ix_items_due_date", "items", ["due_date"])
    op.create_index("ix_items_is_pinned", "items", ["is_pinned"])
    op.create_index("ix_items_is_archived", "items", ["is_archived"])
    op.create_index("ix_items_epic_id", "items", ["epic_id"])

    op.create_table(
        "item_tags",
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "item_entity_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", sa.Integer(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", item_entity_role_enum, server_default="involved", nullable=False),
        sa.Column("is_blocking", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("item_id", "entity_id", name="uq_item_entity_link"),
    )
    op.create_index("ix_item_entity_links_item_id", "item_entity_links", ["item_id"])
    op.create_index("ix_item_entity_links_entity_id", "item_entity_links", ["entity_id"])

    op.create_table(
        "mood_board_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_path", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("caption", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_mood_board_assets_item_id", "mood_board_assets", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_mood_board_assets_item_id", table_name="mood_board_assets")
    op.drop_table("mood_board_assets")

    op.drop_index("ix_item_entity_links_entity_id", table_name="item_entity_links")
    op.drop_index("ix_item_entity_links_item_id", table_name="item_entity_links")
    op.drop_table("item_entity_links")

    op.drop_table("item_tags")

    op.drop_index("ix_items_epic_id", table_name="items")
    op.drop_index("ix_items_is_archived", table_name="items")
    op.drop_index("ix_items_is_pinned", table_name="items")
    op.drop_index("ix_items_due_date", table_name="items")
    op.drop_index("ix_items_priority", table_name="items")
    op.drop_index("ix_items_status", table_name="items")
    op.drop_index("ix_items_item_type", table_name="items")
    op.drop_table("items")

    op.drop_index("ix_tags_normalized_name", table_name="tags")
    op.drop_table("tags")

    op.drop_index("ix_entities_normalized_name", table_name="entities")
    op.drop_table("entities")

    op.drop_index("ix_epics_normalized_name", table_name="epics")
    op.drop_table("epics")
