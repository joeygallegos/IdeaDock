from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.schemas import BoardCreate, BoardSave
from app.services import boards as service

router = APIRouter()


def run(action):
    try:
        return action()
    except service.BoardError as exc:
        raise HTTPException(exc.status, detail=jsonable_encoder(exc.detail)) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@router.get("/items/{item_id}/boards")
def list_boards(item_id: int, db: Session = Depends(get_db)):
    return run(lambda: service.list_boards(db, item_id))


@router.post("/items/{item_id}/boards", status_code=201)
def create_board(item_id: int, payload: BoardCreate, db: Session = Depends(get_db)):
    return run(lambda: service.create_board(db, item_id, payload))


@router.get("/items/{item_id}/boards/{board_id}")
def get_board(item_id: int, board_id: int, db: Session = Depends(get_db)):
    return run(lambda: service.board_dict(db, service.require_board(db, item_id, board_id)))


@router.put("/items/{item_id}/boards/{board_id}")
def save_board(item_id: int, board_id: int, payload: BoardSave, db: Session = Depends(get_db)):
    return run(lambda: service.save_board(db, item_id, board_id, payload))


@router.post("/items/{item_id}/boards/{board_id}/copy", status_code=201)
def copy_board(item_id: int, board_id: int, payload: BoardCreate, db: Session = Depends(get_db)):
    return run(lambda: service.create_board(db, item_id, payload, source_id=board_id))


@router.delete("/items/{item_id}/boards/{board_id}", status_code=204)
def delete_board(item_id: int, board_id: int, revision: int = Query(ge=1), db: Session = Depends(get_db)):
    return run(lambda: service.delete_board(db, item_id, board_id, revision))


@router.get("/items/{item_id}/board-assets")
def item_assets(item_id: int, db: Session = Depends(get_db)):
    return run(lambda: service.item_assets(db, item_id))


@router.post("/items/{item_id}/board-assets", status_code=201)
async def upload(item_id: int, file: UploadFile = File(...), caption: str | None = Form(None), db: Session = Depends(get_db)):
    # Read at most one byte beyond the limit rather than materializing an unbounded upload.
    content = await file.read(settings.max_upload_bytes + 1)
    return run(lambda: service.upload_board_asset(db, item_id, file.filename or "upload", content, caption))


@router.delete("/items/{item_id}/board-assets/{asset_id}", status_code=204)
def delete_asset(item_id: int, asset_id: int, db: Session = Depends(get_db)):
    return run(lambda: service.delete_source_asset(db, "project", asset_id, item_id))


@router.get("/boards")
def search_boards(q: str = "", db: Session = Depends(get_db)):
    return run(lambda: service.search_boards(db, q))


@router.api_route("/projects/{project_id}/{legacy_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def retired_project_boards(project_id: int, legacy_path: str):
    # Epic and Item IDs can collide; redirecting would silently select a new owner.
    raise HTTPException(410, detail="Visual Boards now belong to items. Use /api/items/{item_id}/boards and /board-assets after migrating ownership.")
