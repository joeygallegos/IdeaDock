from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.parser import parse_quick_entry
from app import schemas
from app.services import items as item_service
from app.services.boards import BoardError


router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/parser/preview", response_model=schemas.ParserPreviewOut)
def parser_preview(payload: schemas.ParserPreviewRequest) -> schemas.ParserPreviewOut:
    parsed = parse_quick_entry(payload.raw_input)
    return schemas.ParserPreviewOut.model_validate(parsed.__dict__)


@router.get("/items", response_model=list[schemas.ItemOut])
def list_items(
    q: str | None = None,
    epic_id: int | None = None,
    entity_id: int | None = None,
    status_filter: schemas.ItemStatus | None = None,
    item_type: schemas.ItemType | None = None,
    priority: schemas.Priority | None = None,
    blocking: bool | None = None,
    pinned: bool | None = None,
    archived: bool | None = False,
    active_only: bool = False,
    has_mood_board: bool | None = None,
    due_state: str | None = None,
    db: Session = Depends(get_db),
) -> list[schemas.ItemOut]:
    return item_service.list_items(
        db,
        q=q,
        epic_id=epic_id,
        entity_id=entity_id,
        status=status_filter,
        item_type=item_type,
        priority=priority,
        blocking=blocking,
        pinned=pinned,
        archived=archived,
        active_only=active_only,
        has_mood_board=has_mood_board,
        due_state=due_state,
    )


@router.post("/items", response_model=schemas.ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(payload: schemas.ItemCreate, db: Session = Depends(get_db)) -> schemas.ItemOut:
    try:
        return item_service.create_item(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/items/{item_id}", response_model=schemas.ItemOut)
def get_item(item_id: int, db: Session = Depends(get_db)) -> schemas.ItemOut:
    item = item_service.get_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    return item


@router.patch("/items/{item_id}", response_model=schemas.ItemOut)
def update_item(
    item_id: int,
    payload: schemas.ItemUpdate,
    db: Session = Depends(get_db),
) -> schemas.ItemOut:
    try:
        return item_service.update_item(db, item_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Item not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/epics", response_model=list[schemas.EpicOut])
def list_epics(db: Session = Depends(get_db)) -> list[schemas.EpicOut]:
    return item_service.list_epics(db)


@router.get("/entities", response_model=list[schemas.EntityOut])
def list_entities(db: Session = Depends(get_db)) -> list[schemas.EntityOut]:
    return item_service.list_entities(db)


@router.get("/tags", response_model=list[schemas.TagOut])
def list_tags(db: Session = Depends(get_db)) -> list[schemas.TagOut]:
    return item_service.list_tags(db)


@router.get("/review-summary", response_model=schemas.ReviewSummaryOut)
def review_summary(db: Session = Depends(get_db)) -> schemas.ReviewSummaryOut:
    return item_service.build_review_summary(db)


@router.post("/items/{item_id}/assets", response_model=schemas.AssetUploadOut, status_code=201)
async def upload_asset(
    item_id: int,
    file: UploadFile = File(...),
    caption: str | None = Form(None),
    sort_order: int = Form(0),
    db: Session = Depends(get_db),
) -> schemas.AssetUploadOut:
    try:
        content = await file.read()
        return item_service.add_mood_board_asset(
            db,
            item_id=item_id,
            original_filename=file.filename or "upload",
            content=content,
            caption=caption,
            sort_order=sort_order,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Item not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: int, db: Session = Depends(get_db)) -> None:
    try:
        deleted = item_service.delete_mood_board_asset(db, asset_id)
    except BoardError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not deleted:
        raise HTTPException(status_code=404, detail="Asset not found.")
