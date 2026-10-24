from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import EntityType, ItemEntityRole, ItemStatus, ItemType, Priority


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EpicOut(ORMModel):
    id: int
    name: str


class TagOut(ORMModel):
    id: int
    name: str


class EntityOut(ORMModel):
    id: int
    name: str
    entity_type: EntityType
    is_active: bool


class MoodBoardAssetOut(ORMModel):
    id: int
    file_path: str
    file_url: str
    original_filename: str
    sort_order: int
    caption: str | None
    created_at: datetime


class ItemEntityLinkOut(ORMModel):
    id: int
    role: ItemEntityRole
    is_blocking: bool
    created_at: datetime
    entity: EntityOut


class EntityLinkInput(BaseModel):
    name: str
    entity_type: EntityType = EntityType.other
    role: ItemEntityRole = ItemEntityRole.involved
    is_blocking: bool = False


class ItemBase(BaseModel):
    title: str | None = None
    details: str | None = None
    raw_input: str | None = None
    item_type: ItemType | None = None
    status: ItemStatus | None = None
    priority: Priority | None = None
    due_date: date | None = None
    is_pinned: bool | None = None
    is_archived: bool | None = None
    epic_name: str | None = None
    epic_names: list[str] | None = None
    entity_links: list[EntityLinkInput] | None = None
    tag_names: list[str] | None = None


class ItemCreate(ItemBase):
    status: ItemStatus = ItemStatus.inbox
    entity_links: list[EntityLinkInput] = Field(default_factory=list)
    tag_names: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_title_or_raw_input(self) -> "ItemCreate":
        has_title = bool(self.title and self.title.strip())
        has_raw_input = bool(self.raw_input and self.raw_input.strip())
        if not has_title and not has_raw_input:
            raise ValueError("Provide title or raw_input.")
        return self


class ItemUpdate(ItemBase):
    pass


class ItemOut(ORMModel):
    id: int
    title: str
    details: str | None
    raw_input: str | None
    item_type: ItemType
    status: ItemStatus
    priority: Priority | None
    due_date: date | None
    is_pinned: bool
    is_archived: bool
    is_blocked: bool
    has_mood_board: bool
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    epic: EpicOut | None
    epics: list[EpicOut]
    entity_links: list[ItemEntityLinkOut]
    tags: list[TagOut]
    mood_board_assets: list[MoodBoardAssetOut]


class ParserPreviewRequest(BaseModel):
    raw_input: str


class ParserPreviewOut(BaseModel):
    raw_input: str
    title: str
    epic_name: str | None
    epic_names: list[str]
    item_type: ItemType | None
    priority: Priority | None
    due_date: date | None
    entity_names: list[str]
    warnings: list[str]


class ReviewSummaryOut(BaseModel):
    inbox_count: int
    waiting_count: int
    overdue_count: int
    unassigned_count: int
    stale_count: int
    mood_board_item_count: int


class AssetUploadOut(MoodBoardAssetOut):
    pass

class BoardInput(BaseModel):
    # Reject unknown UI state and non-finite coordinates before persistence.
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class CanvasView(BoardInput):
    x: float = 0
    y: float = 0
    zoom: float = Field(default=1, gt=0)


class BoardObjectBase(BoardInput):
    id: str = Field(min_length=1, max_length=100)
    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class BoardImage(BoardObjectBase):
    type: Literal["image"]
    asset_key: str = Field(pattern=r"^(item|project):[1-9][0-9]*$")


class BoardText(BoardObjectBase):
    type: Literal["text"]
    text: str = Field(max_length=10000)


class BoardSwatch(BoardObjectBase):
    type: Literal["swatch"]
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class BoardCreate(BoardInput):
    name: str = Field(min_length=1, max_length=120)
    objects: list[
        Annotated[BoardImage | BoardText | BoardSwatch, Field(discriminator="type")]
    ] = Field(default_factory=list)
    view: CanvasView = Field(default_factory=CanvasView)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Board name cannot be empty.")
        return value.strip()

    @field_validator("objects")
    @classmethod
    def unique_object_ids(cls, value):
        if len({obj.id for obj in value}) != len(value):
            raise ValueError("Object IDs must be unique within a board.")
        return value


class BoardSave(BoardCreate):
    revision: int = Field(ge=1)
