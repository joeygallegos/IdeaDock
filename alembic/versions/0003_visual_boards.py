"""Project visual boards, independent project uploads, and protected source references."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import LONGTEXT

revision = "0003_visual_boards"
down_revision = "0002_item_epics_many_to_many"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("project_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("epics.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("file_path", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("caption", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_project_assets_project_id", "project_assets", ["project_id"])
    op.create_table("visual_boards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("epics.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("layout", sa.Text().with_variant(LONGTEXT(), "mysql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_visual_boards_project_id", "visual_boards", ["project_id"])
    op.create_table("board_asset_references",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("board_id", sa.Integer(), sa.ForeignKey("visual_boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_asset_id", sa.Integer(), sa.ForeignKey("mood_board_assets.id", ondelete="RESTRICT")),
        sa.Column("project_asset_id", sa.Integer(), sa.ForeignKey("project_assets.id", ondelete="RESTRICT")),
        sa.UniqueConstraint("board_id", "item_asset_id", name="uq_board_item_asset"),
        sa.UniqueConstraint("board_id", "project_asset_id", name="uq_board_project_asset"))
    for column in ("board_id", "item_asset_id", "project_asset_id"):
        op.create_index(f"ix_board_asset_references_{column}", "board_asset_references", [column])
    # Historical permission supports safe local copies after a source moves and a
    # remote tab removes its placement; it never blocks permanent source deletion.
    op.create_table("board_asset_access",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("board_id", sa.Integer(), sa.ForeignKey("visual_boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_asset_id", sa.Integer(), sa.ForeignKey("mood_board_assets.id", ondelete="CASCADE")),
        sa.Column("project_asset_id", sa.Integer(), sa.ForeignKey("project_assets.id", ondelete="CASCADE")),
        sa.UniqueConstraint("board_id", "item_asset_id", name="uq_access_item_asset"),
        sa.UniqueConstraint("board_id", "project_asset_id", name="uq_access_project_asset"))
    for column in ("board_id", "item_asset_id", "project_asset_id"):
        op.create_index(f"ix_board_asset_access_{column}", "board_asset_access", [column])


def downgrade():
    op.drop_table("board_asset_access")
    op.drop_table("board_asset_references")
    op.drop_table("visual_boards")
    op.drop_table("project_assets")
