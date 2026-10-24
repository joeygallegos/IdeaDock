from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.schemas import BoardCreate, BoardSave
from app.services import boards as service

router = APIRouter(prefix="/projects/{project_id}")


def run(action):
    try:
        return action()
    except service.BoardError as exc:
        raise HTTPException(exc.status, detail=jsonable_encoder(exc.detail)) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@router.get("/boards")
def list_boards(project_id: int, db: Session = Depends(get_db)):
    return run(lambda: service.list_boards(db, project_id))


@router.post("/boards", status_code=201)
def create_board(project_id: int, payload: BoardCreate, db: Session = Depends(get_db)):
    return run(lambda: service.create_board(db, project_id, payload))


@router.get("/boards/{board_id}")
def get_board(project_id: int, board_id: int, db: Session = Depends(get_db)):
    return run(lambda: service.board_dict(db, service.require_board(db, project_id, board_id)))


@router.put("/boards/{board_id}")
def save_board(project_id: int, board_id: int, payload: BoardSave, db: Session = Depends(get_db)):
    return run(lambda: service.save_board(db, project_id, board_id, payload))


@router.post("/boards/{board_id}/copy", status_code=201)
def copy_board(project_id: int, board_id: int, payload: BoardCreate, db: Session = Depends(get_db)):
    return run(lambda: service.create_board(db, project_id, payload, source_id=board_id))


@router.delete("/boards/{board_id}", status_code=204)
def delete_board(project_id: int, board_id: int, revision: int = Query(ge=1), db: Session = Depends(get_db)):
    return run(lambda: service.delete_board(db, project_id, board_id, revision))


@router.get("/assets")
def project_assets(project_id: int, db: Session = Depends(get_db)):
    return run(lambda: service.project_assets(db, project_id))


@router.post("/assets", status_code=201)
async def upload(project_id: int, file: UploadFile = File(...), caption: str | None = Form(None), db: Session = Depends(get_db)):
    # Read at most one byte beyond the limit rather than materializing an unbounded upload.
    content = await file.read(settings.max_upload_bytes + 1)
    return run(lambda: service.upload_project_asset(db, project_id, file.filename or "upload", content, caption))


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(project_id: int, asset_id: int, db: Session = Depends(get_db)):
    return run(lambda: service.delete_source_asset(db, "project", asset_id, project_id))
