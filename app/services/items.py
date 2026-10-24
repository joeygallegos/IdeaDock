from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models import (
    Entity,
    Epic,
    Item,
    ItemEntityLink,
    ItemStatus,
    ItemType,
    MoodBoardAsset,
    Priority,
    Tag,
)
from app.parser import parse_quick_entry
from app.schemas import EntityLinkInput, ItemCreate, ItemUpdate, ReviewSummaryOut


ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def list_items(
    session: Session,
    *,
    q: str | None = None,
    epic_id: int | None = None,
    entity_id: int | None = None,
    status: ItemStatus | None = None,
    item_type: ItemType | None = None,
    priority: Priority | None = None,
    blocking: bool | None = None,
    pinned: bool | None = None,
    archived: bool | None = False,
    active_only: bool = False,
    has_mood_board: bool | None = None,
    due_state: str | None = None,
) -> list[Item]:
    statement = select(Item).options(*item_loader_options())
    today = date.today()

    if q:
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(Item.title.ilike(pattern), Item.details.ilike(pattern)))
    if epic_id is not None:
        statement = statement.where(or_(Item.epic_id == epic_id, Item.epics.any(Epic.id == epic_id)))
    if entity_id is not None:
        statement = statement.where(Item.entity_links.any(ItemEntityLink.entity_id == entity_id))
    if status is not None:
        statement = statement.where(Item.status == status)
    if item_type is not None:
        statement = statement.where(Item.item_type == item_type)
    if priority is not None:
        statement = statement.where(Item.priority == priority)
    if blocking is True:
        statement = statement.where(Item.entity_links.any(ItemEntityLink.is_blocking.is_(True)))
    if blocking is False:
        statement = statement.where(~Item.entity_links.any(ItemEntityLink.is_blocking.is_(True)))
    if pinned is not None:
        statement = statement.where(Item.is_pinned.is_(pinned))
    if archived is not None:
        statement = statement.where(Item.is_archived.is_(archived))
    if active_only:
        statement = statement.where(Item.status != ItemStatus.done)
    if has_mood_board is True:
        statement = statement.where(Item.mood_board_assets.any())
    if has_mood_board is False:
        statement = statement.where(~Item.mood_board_assets.any())
    if due_state == "overdue":
        statement = statement.where(
            Item.due_date.is_not(None),
            Item.due_date < today,
            Item.status != ItemStatus.done,
        )
    if due_state == "scheduled":
        statement = statement.where(Item.due_date.is_not(None))
    if due_state == "unscheduled":
        statement = statement.where(Item.due_date.is_(None))

    statement = statement.order_by(Item.is_pinned.desc(), Item.updated_at.desc(), Item.created_at.desc())

    return list(session.execute(statement).scalars().unique().all())


def get_item(session: Session, item_id: int) -> Item | None:
    statement = select(Item).where(Item.id == item_id).options(*item_loader_options())
    return session.execute(statement).scalars().unique().one_or_none()


def create_item(session: Session, payload: ItemCreate) -> Item:
    raw_input = clean_raw_input(payload.raw_input)
    parsed = parse_quick_entry(raw_input) if raw_input else None

    title = clean_optional_text(payload.title) or (parsed.title if parsed else None)
    if not title:
        raise ValueError("Item title is required.")

    item = Item(
        title=title,
        details=clean_multiline_text(payload.details),
        raw_input=raw_input,
        item_type=payload.item_type or (parsed.item_type if parsed else None) or ItemType.idea,
        status=payload.status or ItemStatus.inbox,
        priority=payload.priority or (parsed.priority if parsed else None),
        due_date=payload.due_date or (parsed.due_date if parsed else None),
        is_pinned=bool(payload.is_pinned),
        is_archived=bool(payload.is_archived),
    )

    session.add(item)
    replace_epics(session, item, select_create_epic_names(payload, parsed))

    entity_links = payload.entity_links
    if not entity_links and parsed:
        entity_links = [EntityLinkInput(name=name) for name in parsed.entity_names]
    replace_entity_links(session, item, entity_links)
    replace_tags(session, item, payload.tag_names)
    sync_completed_at(item)

    session.commit()
    return get_required_item(session, item.id)


def update_item(session: Session, item_id: int, payload: ItemUpdate) -> Item:
    item = get_required_item(session, item_id)
    changes = payload.model_dump(exclude_unset=True)

    if "title" in changes:
        title = clean_optional_text(payload.title)
        if not title:
            raise ValueError("Title cannot be empty.")
        item.title = title
    if "details" in changes:
        item.details = clean_multiline_text(payload.details)
    if "raw_input" in changes:
        item.raw_input = clean_raw_input(payload.raw_input)
    if "item_type" in changes and payload.item_type is not None:
        item.item_type = payload.item_type
    if "status" in changes and payload.status is not None:
        item.status = payload.status
    if "priority" in changes:
        item.priority = payload.priority
    if "due_date" in changes:
        item.due_date = payload.due_date
    if "is_pinned" in changes and payload.is_pinned is not None:
        item.is_pinned = payload.is_pinned
    if "is_archived" in changes and payload.is_archived is not None:
        item.is_archived = payload.is_archived
    if "epic_name" in changes or "epic_names" in changes:
        replace_epics(session, item, select_update_epic_names(payload, changes))
    if "entity_links" in changes:
        replace_entity_links(session, item, payload.entity_links)
    if "tag_names" in changes:
        replace_tags(session, item, payload.tag_names)

    sync_completed_at(item)
    session.commit()
    return get_required_item(session, item.id)


def list_epics(session: Session) -> list[Epic]:
    return list(session.scalars(select(Epic).order_by(Epic.normalized_name)).all())


def list_entities(session: Session) -> list[Entity]:
    return list(session.scalars(select(Entity).order_by(Entity.normalized_name)).all())


def list_tags(session: Session) -> list[Tag]:
    return list(session.scalars(select(Tag).order_by(Tag.normalized_name)).all())


def build_review_summary(session: Session) -> ReviewSummaryOut:
    today = date.today()
    stale_cutoff = datetime.now(UTC) - timedelta(days=settings.stale_after_days)

    inbox_count = count_items(session, Item.status == ItemStatus.inbox, Item.is_archived.is_(False))
    waiting_count = count_items(
        session,
        Item.is_archived.is_(False),
        Item.status != ItemStatus.done,
        or_(
            Item.status == ItemStatus.waiting,
            Item.entity_links.any(ItemEntityLink.is_blocking.is_(True)),
        ),
    )
    overdue_count = count_items(
        session,
        Item.is_archived.is_(False),
        Item.status != ItemStatus.done,
        Item.due_date.is_not(None),
        Item.due_date < today,
    )
    unassigned_count = count_items(
        session,
        Item.is_archived.is_(False),
        Item.epic_id.is_(None),
        ~Item.epics.any(),
    )
    stale_count = count_items(
        session,
        Item.is_archived.is_(False),
        Item.status != ItemStatus.done,
        Item.updated_at < stale_cutoff,
    )
    mood_board_item_count = count_items(session, Item.is_archived.is_(False), Item.mood_board_assets.any())

    return ReviewSummaryOut(
        inbox_count=inbox_count,
        waiting_count=waiting_count,
        overdue_count=overdue_count,
        unassigned_count=unassigned_count,
        stale_count=stale_count,
        mood_board_item_count=mood_board_item_count,
    )


def add_mood_board_asset(
    session: Session,
    *,
    item_id: int,
    original_filename: str,
    content: bytes,
    caption: str | None = None,
    sort_order: int = 0,
) -> MoodBoardAsset:
    if len(content) > settings.max_upload_bytes:
        raise ValueError("Uploaded file is too large.")

    item = get_required_item(session, item_id)
    suffix = Path(original_filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_SUFFIXES:
        raise ValueError("Unsupported image type.")

    safe_stem = sanitize_filename_stem(Path(original_filename).stem)
    unique_name = f"{safe_stem}-{uuid4().hex[:10]}{suffix}"
    target_dir = settings.upload_path / f"item-{item.id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / unique_name
    target_path.write_bytes(content)

    asset = MoodBoardAsset(
        item=item,
        file_path=target_path.relative_to(settings.upload_path).as_posix(),
        original_filename=original_filename,
        sort_order=sort_order,
        caption=clean_optional_text(caption),
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


def delete_mood_board_asset(session: Session, asset_id: int) -> bool:
    from app.services.boards import delete_source_asset

    if session.get(MoodBoardAsset, asset_id) is None:
        return False
    # Existing item deletion shares the board-aware lifetime check.
    delete_source_asset(session, "item", asset_id)
    return True


def item_loader_options():
    return (
        selectinload(Item.epic),
        selectinload(Item.epics),
        selectinload(Item.tags),
        selectinload(Item.entity_links).selectinload(ItemEntityLink.entity),
        selectinload(Item.mood_board_assets),
    )


def get_required_item(session: Session, item_id: int) -> Item:
    item = get_item(session, item_id)
    if item is None:
        raise LookupError(f"Item {item_id} was not found.")
    return item


def get_or_create_epic(session: Session, name: str | None) -> Epic | None:
    cleaned_name = clean_optional_text(name)
    if not cleaned_name:
        return None

    normalized_name = normalize_lookup_name(cleaned_name)
    epic = session.scalar(select(Epic).where(Epic.normalized_name == normalized_name))
    if epic is not None:
        return epic
    if not settings.auto_create_epics:
        return None

    epic = Epic(name=cleaned_name, normalized_name=normalized_name)
    session.add(epic)
    session.flush()
    return epic


def get_or_create_entity(session: Session, name: str, entity_type) -> Entity | None:
    cleaned_name = clean_optional_text(name)
    if not cleaned_name:
        return None

    normalized_name = normalize_lookup_name(cleaned_name)
    entity = session.scalar(select(Entity).where(Entity.normalized_name == normalized_name))
    if entity is not None:
        return entity
    if not settings.auto_create_entities:
        return None

    entity = Entity(name=cleaned_name, normalized_name=normalized_name, entity_type=entity_type)
    session.add(entity)
    session.flush()
    return entity


def get_or_create_tag(session: Session, name: str) -> Tag | None:
    cleaned_name = clean_optional_text(name)
    if not cleaned_name:
        return None

    normalized_name = normalize_lookup_name(cleaned_name)
    tag = session.scalar(select(Tag).where(Tag.normalized_name == normalized_name))
    if tag is not None:
        return tag
    if not settings.auto_create_tags:
        return None

    tag = Tag(name=cleaned_name, normalized_name=normalized_name)
    session.add(tag)
    session.flush()
    return tag


def replace_entity_links(session: Session, item: Item, entity_links: list[EntityLinkInput] | None) -> None:
    if entity_links is None:
        return

    item.entity_links.clear()
    for link in entity_links:
        entity = get_or_create_entity(session, link.name, link.entity_type)
        if entity is None:
            continue
        item.entity_links.append(
            ItemEntityLink(
                entity=entity,
                role=link.role,
                is_blocking=link.is_blocking,
            )
        )


def replace_epics(session: Session, item: Item, epic_names: list[str] | None) -> None:
    if epic_names is None:
        return

    epics: list[Epic] = []
    seen: set[str] = set()
    for raw_name in epic_names:
        cleaned_name = clean_optional_text(raw_name)
        if not cleaned_name:
            continue
        key = normalize_lookup_name(cleaned_name)
        if key in seen:
            continue
        seen.add(key)
        epic = get_or_create_epic(session, cleaned_name)
        if epic is not None:
            epics.append(epic)

    item.epics = epics
    item.epic = epics[0] if epics else None


def replace_tags(session: Session, item: Item, tag_names: list[str] | None) -> None:
    if tag_names is None:
        return

    tags: list[Tag] = []
    seen: set[str] = set()
    for raw_name in tag_names:
        cleaned_name = clean_optional_text(raw_name)
        if not cleaned_name:
            continue
        key = normalize_lookup_name(cleaned_name)
        if key in seen:
            continue
        seen.add(key)
        tag = get_or_create_tag(session, cleaned_name)
        if tag is not None:
            tags.append(tag)
    item.tags = tags


def sync_completed_at(item: Item) -> None:
    if item.status == ItemStatus.done and item.completed_at is None:
        item.completed_at = datetime.now(UTC)
    if item.status != ItemStatus.done:
        item.completed_at = None


def clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split()).strip()
    return cleaned or None


def clean_multiline_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def clean_raw_input(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def select_create_epic_names(payload: ItemCreate, parsed) -> list[str] | None:
    if payload.epic_names is not None:
        return payload.epic_names
    if payload.epic_name is not None:
        return [payload.epic_name] if clean_optional_text(payload.epic_name) else []
    if parsed is not None:
        return parsed.epic_names
    return []


def select_update_epic_names(payload: ItemUpdate, changes: dict[str, object]) -> list[str] | None:
    if "epic_names" in changes:
        return payload.epic_names or []
    if "epic_name" in changes:
        return [payload.epic_name] if clean_optional_text(payload.epic_name) else []
    return None


def normalize_lookup_name(value: str) -> str:
    return clean_optional_text(value).casefold()


def sanitize_filename_stem(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return cleaned or "asset"


def count_items(session: Session, *conditions) -> int:
    statement = select(func.count(Item.id)).where(*conditions)
    return int(session.scalar(statement) or 0)
