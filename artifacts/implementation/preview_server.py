"""Run a disposable, loopback-only acceptance environment; never use live data."""

import base64
import os
from pathlib import Path
import sys
import tempfile


root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
os.chdir(root)

with tempfile.TemporaryDirectory(prefix="ideadock-board-preview-") as temporary:
    # Set explicit environment values before importing app modules so .env cannot
    # direct this acceptance run to the user's database or upload directory.
    os.environ["DATABASE_URL"] = "sqlite:///" + (Path(temporary) / "preview.db").as_posix()
    os.environ["UPLOAD_DIR"] = str(Path(temporary) / "uploads")
    os.environ["AUTO_BOOTSTRAP_DB"] = "false"

    from alembic import command
    from alembic.config import Config
    from app.db import SessionLocal
    from app.models import Epic
    from app.schemas import ItemCreate
    from app.services.items import add_mood_board_asset, create_item

    command.upgrade(Config(str(root / "alembic.ini")), "head")
    with SessionLocal() as session:
        item = create_item(session, ItemCreate(title="Completed reference note", epic_names=["Board acceptance"], status="done"))
        add_mood_board_asset(
            session,
            item_id=item.id,
            original_filename="reference.png",
            content=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a4WQAAAAASUVORK5CYII="),
            caption="Completed item reference",
        )
        session.add(Epic(name="Empty project", normalized_name="empty project"))
        session.commit()

    import uvicorn
    from app.main import app

    uvicorn.run(app, host="127.0.0.1", port=8027, access_log=False)
