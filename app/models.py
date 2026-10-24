from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.mysql import LONGTEXT

from app.db import Base


class ItemType(str, Enum):
    task = "task"
    idea = "idea"
    note = "note"
    someday = "someday"


class ItemStatus(str, Enum):
    inbox = "inbox"
    next = "next"
    doing = "doing"
    waiting = "waiting"
    done = "done"


class Priority(str, Enum):
    low = "low"
    med = "med"
    high = "high"


class EntityType(str, Enum):
    person = "person"
    family = "family"
    friend = "friend"
    vendor = "vendor"
    company = "company"
    service = "service"
    team = "team"
    other = "other"


class ItemEntityRole(str, Enum):
    waiting_on = "waiting_on"
    involved = "involved"
    reference = "reference"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


item_tags = Table(
    "item_tags",
    Base.metadata,
    Column("item_id", ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

item_epics = Table(
    "item_epics",
    Base.metadata,
    Column("item_id", ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
    Column("epic_id", ForeignKey("epics.id", ondelete="CASCADE"), primary_key=True),
)


class Epic(TimestampMixin, Base):
    __tablename__ = "epics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)

    primary_items: Mapped[list["Item"]] = relationship(back_populates="epic")
    items: Mapped[list["Item"]] = relationship(secondary=item_epics, back_populates="epics")


class Entity(TimestampMixin, Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    entity_type: Mapped[EntityType] = mapped_column(
        SqlEnum(EntityType, name="entity_type", native_enum=False),
        default=EntityType.other,
        server_default=EntityType.other.value,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)

    item_links: Mapped[list["ItemEntityLink"]] = relationship(back_populates="entity")


class Tag(TimestampMixin, Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)

    items: Mapped[list["Item"]] = relationship(secondary=item_tags, back_populates="tags")


class Item(TimestampMixin, Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    raw_input: Mapped[str | None] = mapped_column(Text)
    item_type: Mapped[ItemType] = mapped_column(
        SqlEnum(ItemType, name="item_type", native_enum=False),
        default=ItemType.idea,
        server_default=ItemType.idea.value,
        nullable=False,
        index=True,
    )
    status: Mapped[ItemStatus] = mapped_column(
        SqlEnum(ItemStatus, name="item_status", native_enum=False),
        default=ItemStatus.inbox,
        server_default=ItemStatus.inbox.value,
        nullable=False,
        index=True,
    )
    priority: Mapped[Priority | None] = mapped_column(
        SqlEnum(Priority, name="priority", native_enum=False),
        nullable=True,
        index=True,
    )
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False, index=True)
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    epic_id: Mapped[int | None] = mapped_column(ForeignKey("epics.id", ondelete="SET NULL"), index=True)

    epic: Mapped["Epic | None"] = relationship(back_populates="primary_items")
    epics: Mapped[list["Epic"]] = relationship(secondary=item_epics, back_populates="items")
    tags: Mapped[list["Tag"]] = relationship(secondary=item_tags, back_populates="items")
    entity_links: Mapped[list["ItemEntityLink"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
    )
    mood_board_assets: Mapped[list["MoodBoardAsset"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="MoodBoardAsset.sort_order",
    )

    @property
    def is_blocked(self) -> bool:
        return any(link.is_blocking for link in self.entity_links)

    @property
    def has_mood_board(self) -> bool:
        return bool(self.mood_board_assets)


class ItemEntityLink(Base):
    __tablename__ = "item_entity_links"
    __table_args__ = (
        UniqueConstraint("item_id", "entity_id", name="uq_item_entity_link"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[ItemEntityRole] = mapped_column(
        SqlEnum(ItemEntityRole, name="item_entity_role", native_enum=False),
        default=ItemEntityRole.involved,
        server_default=ItemEntityRole.involved.value,
        nullable=False,
    )
    is_blocking: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    item: Mapped["Item"] = relationship(back_populates="entity_links")
    entity: Mapped["Entity"] = relationship(back_populates="item_links")


class MoodBoardAsset(Base):
    __tablename__ = "mood_board_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    caption: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    item: Mapped["Item"] = relationship(back_populates="mood_board_assets")

    @property
    def file_url(self) -> str:
        return f"/uploads/{self.file_path.replace('\\', '/')}"

class ProjectAsset(Base):
    __tablename__ = "project_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("epics.id", ondelete="RESTRICT"), index=True)
    file_path: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    caption: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def file_url(self) -> str:
        return f"/uploads/{self.file_path.replace(chr(92), '/')}"


class VisualBoard(TimestampMixin, Base):
    __tablename__ = "visual_boards"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("epics.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    # Layout is independent of item records; references below enforce asset lifetime.
    layout: Mapped[str] = mapped_column(Text().with_variant(LONGTEXT(), "mysql"))


class BoardAssetReference(Base):
    __tablename__ = "board_asset_references"
    __table_args__ = (
        UniqueConstraint("board_id", "item_asset_id", name="uq_board_item_asset"),
        UniqueConstraint("board_id", "project_asset_id", name="uq_board_project_asset"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("visual_boards.id", ondelete="CASCADE"), index=True)
    item_asset_id: Mapped[int | None] = mapped_column(ForeignKey("mood_board_assets.id", ondelete="RESTRICT"), index=True)
    project_asset_id: Mapped[int | None] = mapped_column(ForeignKey("project_assets.id", ondelete="RESTRICT"), index=True)


class BoardAssetAccess(Base):
    """Prior source access survives remote layout edits for safe local recovery."""

    __tablename__ = "board_asset_access"
    __table_args__ = (
        UniqueConstraint("board_id", "item_asset_id", name="uq_access_item_asset"),
        UniqueConstraint("board_id", "project_asset_id", name="uq_access_project_asset"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("visual_boards.id", ondelete="CASCADE"), index=True)
    # Unlike current placements, history must not prevent source deletion. Cascading
    # also prevents a recycled source ID from inheriting an obsolete access grant.
    item_asset_id: Mapped[int | None] = mapped_column(ForeignKey("mood_board_assets.id", ondelete="CASCADE"), index=True)
    project_asset_id: Mapped[int | None] = mapped_column(ForeignKey("project_assets.id", ondelete="CASCADE"), index=True)
