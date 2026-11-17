from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    BoardAssetAccess,
    BoardAssetReference,
    Item,
    MoodBoardAsset,
    ProjectAsset,
    VisualBoard,
)
from app.schemas import BoardCreate, BoardSave
from app.services.items import sanitize_filename_stem


class BoardError(Exception):
    def __init__(self, status: int, detail):
        self.status = status
        self.detail = detail


def require_item(session: Session, item_id: int) -> None:
    if session.get(Item, item_id) is None:
        raise BoardError(404, "Item not found.")


def require_board(session: Session, item_id: int, board_id: int) -> VisualBoard:
    board = session.scalar(
        select(VisualBoard)
        .where(VisualBoard.id == board_id, VisualBoard.item_id == item_id)
        .execution_options(populate_existing=True)
    )
    if board is None:
        raise BoardError(404, "Board not found.")
    return board


def asset_dict(asset, kind: str, source_name: str, item_id: int | None = None) -> dict:
    return dict(
        key=f"{kind}:{asset.id}",
        id=asset.id,
        kind=kind,
        file_url=asset.file_url,
        original_filename=asset.original_filename,
        caption=asset.caption,
        item_id=item_id,
        source_name=source_name,
    )


def item_assets(session: Session, item_id: int) -> list[dict]:
    require_item(session, item_id)
    # Epic membership never expands the library: only the owner's images are
    # available for new placements, including completed or archived owners.
    assets = session.scalars(
        select(MoodBoardAsset)
        .where(MoodBoardAsset.item_id == item_id)
        .order_by(MoodBoardAsset.id)
    ).all()
    result = [asset_dict(a, "item", a.item.title, a.item_id) for a in assets]
    owner = session.get(Item, item_id)
    direct_assets = session.scalars(
        select(ProjectAsset)
        .where(ProjectAsset.item_id == item_id)
        .order_by(ProjectAsset.id)
    )
    # The legacy source kind is persisted in layouts; retain it across migration.
    result.extend(asset_dict(a, "project", owner.title) for a in direct_assets)
    return result


def reference_keys(session: Session, board_id: int, model=BoardAssetReference) -> set[str]:
    references = session.scalars(select(model).where(model.board_id == board_id))
    return {
        f"item:{r.item_asset_id}" if r.item_asset_id else f"project:{r.project_asset_id}"
        for r in references
    }


def board_dict(session: Session, board: VisualBoard) -> dict:
    layout = json.loads(board.layout)
    assets = []
    for key in sorted(reference_keys(session, board.id)):
        kind, raw_id = key.split(":")
        model = MoodBoardAsset if kind == "item" else ProjectAsset
        asset = session.get(model, int(raw_id))
        if asset is not None:
            source = (
                asset.item.title if kind == "item"
                else session.get(Item, asset.item_id).title
            )
            assets.append(asset_dict(
                asset, kind, source, asset.item_id if kind == "item" else None
            ))
    return dict(
        id=board.id,
        item_id=board.item_id,
        name=board.name,
        revision=board.revision,
        objects=layout["objects"],
        view=layout["view"],
        assets=assets,
        created_at=board.created_at,
        updated_at=board.updated_at,
    )


def list_boards(session: Session, item_id: int) -> list[dict]:
    require_item(session, item_id)
    rows = session.scalars(
        select(VisualBoard)
        .where(VisualBoard.item_id == item_id)
        .order_by(VisualBoard.updated_at.desc(), VisualBoard.id.desc())
    )
    return [board_dict(session, board) for board in rows]


def search_boards(session: Session, q: str = "") -> list[dict]:
    query = select(VisualBoard.id, VisualBoard.name, VisualBoard.item_id, Item.title).join(
        Item, Item.id == VisualBoard.item_id
    )
    if q.strip():
        # Escape SQL wildcard characters: a name search treats % and _ literally.
        query = query.where(func.lower(VisualBoard.name).contains(q.strip().lower(), autoescape=True))
    rows = session.execute(query.order_by(func.lower(VisualBoard.name), VisualBoard.id))
    return [dict(id=row.id, name=row.name, item_id=row.item_id, item_title=row.title) for row in rows]


def encode_layout(payload: BoardCreate) -> str:
    return json.dumps(
        dict(objects=[o.model_dump() for o in payload.objects], view=payload.view.model_dump()),
        allow_nan=False,
    )


def replace_references(session, board, payload, retained):
    allowed = {a["key"] for a in item_assets(session, board.item_id)} | retained
    keys = {o.asset_key for o in payload.objects if o.type == "image"}
    if not keys <= allowed:
        raise BoardError(400, "An image is not available to this item.")
    # Lock sources before replacing references. FK RESTRICT is the final guard
    # against concurrent deletion, including SQLite where FOR UPDATE is ignored.
    for key in sorted(keys):
        kind, raw_id = key.split(":")
        model = MoodBoardAsset if kind == "item" else ProjectAsset
        source = session.scalar(
            select(model).where(model.id == int(raw_id)).with_for_update()
        )
        if source is None:
            raise BoardError(400, "A source image no longer exists.")
    session.execute(
        delete(BoardAssetReference).where(BoardAssetReference.board_id == board.id)
    )
    historical_keys = reference_keys(session, board.id, BoardAssetAccess)
    for key in sorted(keys):
        kind, raw_id = key.split(":")
        reference = dict(
            board_id=board.id,
            item_asset_id=int(raw_id) if kind == "item" else None,
            project_asset_id=int(raw_id) if kind == "project" else None,
        )
        session.add(BoardAssetReference(**reference))
        # Historical access allows recovery of a local placement removed remotely
        # after migration narrows its library. It grants nothing to unrelated items.
        if key not in historical_keys:
            session.add(BoardAssetAccess(**reference))


def create_board(
    session: Session, item_id: int, payload: BoardCreate, source_id: int | None = None
) -> dict:
    require_item(session, item_id)
    retained = set()
    if source_id is not None:
        source = require_board(session, item_id, source_id)
        retained = reference_keys(session, source.id, BoardAssetAccess)
    board = VisualBoard(
        item_id=item_id, name=payload.name, layout=encode_layout(payload), revision=1
    )
    try:
        session.add(board)
        session.flush()
        replace_references(session, board, payload, retained)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return board_dict(session, board)


def conflict(session: Session, item_id: int, board_id: int) -> None:
    # Release the old transaction snapshot so recovery sees the latest commit.
    session.rollback()
    board = require_board(session, item_id, board_id)
    raise BoardError(409, dict(
        code="revision_conflict",
        message="This board changed in another tab. Your local changes have not been saved.",
        latest=board_dict(session, board),
    ))


def save_board(
    session: Session, item_id: int, board_id: int, payload: BoardSave
) -> dict:
    require_board(session, item_id, board_id)
    try:
        # One conditional database write, not a check followed by an update:
        # exactly one tab can claim a revision under concurrent requests.
        result = session.execute(
            update(VisualBoard)
            .where(
                VisualBoard.id == board_id,
                VisualBoard.item_id == item_id,
                VisualBoard.revision == payload.revision,
            )
            .values(
                name=payload.name,
                layout=encode_layout(payload),
                revision=VisualBoard.revision + 1,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            conflict(session, item_id, board_id)
        board = require_board(session, item_id, board_id)
        retained = reference_keys(session, board_id, BoardAssetAccess)
        replace_references(session, board, payload, retained)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return board_dict(session, require_board(session, item_id, board_id))


def delete_board(session: Session, item_id: int, board_id: int, revision: int) -> None:
    require_board(session, item_id, board_id)
    result = session.execute(
        delete(VisualBoard).where(
            VisualBoard.id == board_id,
            VisualBoard.item_id == item_id,
            VisualBoard.revision == revision,
        )
    )
    if result.rowcount != 1:
        conflict(session, item_id, board_id)
    session.commit()


def used_by_boards(session: Session, kind: str, asset_id: int) -> list[dict]:
    column = (
        BoardAssetReference.item_asset_id if kind == "item"
        else BoardAssetReference.project_asset_id
    )
    rows = session.scalars(
        select(VisualBoard)
        .join(BoardAssetReference)
        .where(column == asset_id)
        .order_by(VisualBoard.id)
    )
    return [dict(id=b.id, item_id=b.item_id, name=b.name) for b in rows]


def protect_asset(session: Session, kind: str, asset_id: int) -> None:
    boards = used_by_boards(session, kind, asset_id)
    if boards:
        raise BoardError(409, dict(
            code="asset_in_use",
            message="Remove this image from these boards before deleting it.",
            boards=boards,
        ))


def validate_image(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    valid = (
        (suffix in {".jpg", ".jpeg"}
         and content.startswith(b"\xff\xd8\xff") and content.endswith(b"\xff\xd9"))
        or (suffix == ".png" and content.startswith(b"\x89PNG\r\n\x1a\n")
            and content[12:16] == b"IHDR" and b"IEND" in content[-12:])
        or (suffix == ".gif" and content[:6] in {b"GIF87a", b"GIF89a"}
            and content.endswith(b";"))
        or (suffix == ".webp" and content[:4] == b"RIFF"
            and content[8:12] == b"WEBP" and len(content) >= 20)
    )
    if not content or len(content) > settings.max_upload_bytes:
        raise ValueError("Image is empty or exceeds the upload size limit.")
    if not valid:
        raise ValueError("Upload a valid PNG, JPEG, GIF, or WebP image matching its filename.")
    return suffix


def upload_board_asset(
    session: Session, item_id: int, filename: str, content: bytes,
    caption: str | None = None,
) -> dict:
    require_item(session, item_id)
    suffix = validate_image(filename, content)
    # Original names are display metadata; generated paths never include directories.
    filename = filename.replace("\\", "/").split("/")[-1][:255]
    if caption is not None and len(caption) > 255:
        raise ValueError("Caption must be at most 255 characters.")
    stem = sanitize_filename_stem(Path(filename).stem)[:80]
    target = settings.upload_path / f"board-item-{item_id}" / f"{stem}-{uuid4().hex}{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_bytes(content)
        asset = ProjectAsset(
            item_id=item_id,
            file_path=target.relative_to(settings.upload_path).as_posix(),
            original_filename=filename,
            caption=caption,
        )
        session.add(asset)
        session.commit()
    except Exception:
        session.rollback()
        target.unlink(missing_ok=True)
        raise
    return asset_dict(asset, "project", session.get(Item, item_id).title)


def delete_source_asset(
    session: Session, kind: str, asset_id: int, item_id: int | None = None
) -> None:
    model = MoodBoardAsset if kind == "item" else ProjectAsset
    asset = session.scalar(select(model).where(model.id == asset_id).with_for_update())
    if asset is None or (kind == "project" and asset.item_id != item_id):
        raise BoardError(404, "Asset not found.")
    protect_asset(session, kind, asset_id)
    target = (settings.upload_path / asset.file_path).resolve()
    if settings.upload_path not in target.parents:
        raise ValueError("Refusing to delete a file outside the upload directory.")
    try:
        # Commit FK-checked deletion before touching disk. A competing placement
        # cannot retain metadata whose file this request already removed.
        session.delete(asset)
        session.commit()
    except IntegrityError:
        session.rollback()
        protect_asset(session, kind, asset_id)
        raise BoardError(409, "Image is in use. Reload and try again.")
    target.unlink(missing_ok=True)
