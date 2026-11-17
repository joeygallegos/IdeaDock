"""Independent lifecycle tests across existing items and the new board service."""
import asyncio
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from app.api.boards import router as board_router
from app.db import get_db
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base
from app.schemas import BoardCreate, BoardSave, ItemCreate, ItemUpdate
from app.services import boards, items
from test_existing_workflows import PNG


class BoardIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.temp.name).as_posix()}/test.db")
        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.uploads = patch.object(settings, "upload_dir", str(Path(self.temp.name) / "uploads"))
        self.uploads.start()
        self.item = items.create_item(self.session, ItemCreate(title="Source", epic_names=["Home"], status="done"))
        self.owner_id = self.item.id
        self.asset = items.add_mood_board_asset(self.session, item_id=self.item.id, original_filename="sample.png", content=PNG)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        self.uploads.stop()
        self.temp.cleanup()

    def request(self, method, path, body=None, content_type="application/json"):
        # Invoke the ASGI router directly so HTTP contracts are exercised without
        # introducing an HTTP-client dependency or touching the live database.
        app = FastAPI()
        app.include_router(board_router, prefix="/api")
        app.dependency_overrides[get_db] = lambda: self.session
        raw = body if isinstance(body, bytes) else json.dumps(body).encode() if body is not None else b""
        route, _, query = path.partition("?")

        async def invoke():
            messages = []
            async def receive():
                return {"type": "http.request", "body": raw, "more_body": False}
            async def send(message):
                messages.append(message)
            await app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                       "method": method, "path": route, "raw_path": route.encode(),
                       "query_string": query.encode(), "root_path": "", "scheme": "http",
                       "server": ("test", 80), "client": ("test", 123),
                       "headers": [(b"content-type", content_type.encode())]}, receive, send)
            status = next(m["status"] for m in messages if m["type"] == "http.response.start")
            response = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
            return status, json.loads(response) if response else None
        return asyncio.run(invoke())

    def test_http_board_lifecycle_search_upload_and_retired_routes(self):
        owner = items.create_item(self.session, ItemCreate(title="Owner without Epic"))
        base = f"/api/items/{owner.id}"
        status, board = self.request("POST", base + "/boards", {"name": "Mood palette"})
        self.assertEqual(status, 201)
        self.assertEqual(board["item_id"], owner.id)
        status, results = self.request("GET", "/api/boards?q=PALETTE")
        self.assertEqual((status, results[0]["name"], results[0]["item_title"]), (200, "Mood palette", owner.title))
        boundary = "ideadock-test"
        multipart = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="source.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
                     + PNG + f"\r\n--{boundary}--\r\n".encode())
        status, asset = self.request("POST", base + "/board-assets", multipart, f"multipart/form-data; boundary={boundary}")
        self.assertEqual(status, 201)
        status, deck = self.request("GET", base + "/board-assets")
        self.assertEqual((status, deck[0]["key"]), (200, asset["key"]))
        status, saved = self.request("PUT", base + f'/boards/{board["id"]}',
                                     {"name": board["name"], "revision": 1, "objects": [self.image(asset["key"])]})
        self.assertEqual((status, saved["revision"]), (200, 2))
        self.assertEqual(self.request("GET", f'/api/items/{self.item.id}/boards/{board["id"]}')[0], 404)
        self.assertEqual(self.request("DELETE", base + f'/board-assets/{asset["id"]}')[0], 409)
        self.assertEqual(self.request("PUT", base + f'/boards/{board["id"]}', {"name": "Stale", "revision": 1})[0], 409)
        status, copied = self.request("POST", base + f'/boards/{board["id"]}/copy',
                                      {"name": "Copy", "objects": saved["objects"], "view": saved["view"]})
        self.assertEqual(status, 201)
        self.assertEqual(self.request("DELETE", base + f'/boards/{board["id"]}?revision=2')[0], 204)
        self.assertEqual(self.request("DELETE", base + f'/boards/{copied["id"]}?revision=1')[0], 204)
        self.assertEqual(self.request("DELETE", base + f'/board-assets/{asset["id"]}')[0], 204)
        self.assertEqual(self.request("GET", base + "/boards")[1], [])
        for method in ["GET", "POST", "PUT", "DELETE"]:
            self.assertEqual(self.request(method, "/api/projects/1/boards")[0], 410)

    def image(self, key=None):
        return dict(id="image-1", type="image", asset_key=key or f"item:{self.asset.id}", x=10, y=20, width=100, height=50)

    def test_deck_includes_completed_owner_and_isolates_items(self):
        direct = boards.upload_board_asset(self.session, self.owner_id, "direct.png", PNG)
        deck = boards.item_assets(self.session, self.owner_id)
        self.assertEqual({asset["key"] for asset in deck}, {direct["key"], f"item:{self.asset.id}"})
        self.assertEqual(len(deck), 2)
        other = items.create_item(self.session, ItemCreate(title="Other", epic_names=["Work"]))
        self.assertEqual(boards.item_assets(self.session, other.id), [])
        with self.assertRaises(boards.BoardError) as caught:
            boards.create_board(self.session, other.id, BoardCreate(name="Wrong project", objects=[self.image()]))
        self.assertEqual(caught.exception.status, 400)

    def test_epic_change_preserves_placements_and_copy_then_deletion_guard(self):
        first = boards.create_board(self.session, self.owner_id, BoardCreate(name="First", objects=[self.image()]))
        items.update_item(self.session, self.item.id, ItemUpdate(epic_names=["Work"]))
        self.assertEqual(len(boards.item_assets(self.session, self.owner_id)), 1)
        latest = boards.board_dict(self.session, boards.require_board(self.session, self.owner_id, first["id"]))
        self.assertEqual(latest["assets"][0]["key"], f"item:{self.asset.id}")
        copy = boards.create_board(self.session, self.owner_id, BoardCreate(name="Copy", objects=latest["objects"], view=latest["view"]), source_id=first["id"])
        with self.assertRaises(boards.BoardError) as caught:
            items.delete_mood_board_asset(self.session, self.asset.id)
        self.assertEqual({b["name"] for b in caught.exception.detail["boards"]}, {"First", "Copy"})
        boards.delete_board(self.session, self.owner_id, first["id"], first["revision"])
        path = settings.upload_path / self.asset.file_path
        self.assertTrue(path.exists())
        self.assertEqual(boards.board_dict(self.session, boards.require_board(self.session, self.owner_id, copy["id"]))["objects"], copy["objects"])
        boards.delete_board(self.session, self.owner_id, copy["id"], copy["revision"])
        self.assertTrue(items.delete_mood_board_asset(self.session, self.asset.id))
        self.assertFalse(path.exists())

    def test_two_sessions_cannot_overwrite_same_revision(self):
        board = boards.create_board(self.session, self.owner_id, BoardCreate(name="Original"))
        with Session(self.engine) as second:
            # Both clients possess revision 1 before either attempts persistence.
            stale = boards.board_dict(second, boards.require_board(second, self.owner_id, board["id"]))
            winner = boards.save_board(self.session, self.owner_id, board["id"], BoardSave(name="Winner", revision=1, objects=[self.image()]))
            with self.assertRaises(boards.BoardError) as caught:
                boards.save_board(second, self.owner_id, board["id"], BoardSave(name="Stale", revision=stale["revision"]))
            self.assertEqual(caught.exception.status, 409)
            self.assertEqual(caught.exception.detail["latest"]["name"], "Winner")
            self.assertEqual(caught.exception.detail["latest"]["objects"], winner["objects"])
            with self.assertRaises(boards.BoardError):
                boards.delete_board(second, self.owner_id, board["id"], stale["revision"])
            self.assertEqual(boards.require_board(second, self.owner_id, board["id"]).name, "Winner")

    def test_concurrent_revision_claim_has_exactly_one_winner(self):
        board = boards.create_board(self.session, self.owner_id, BoardCreate(name="Original"))
        ready = Barrier(2)

        def save(name):
            with Session(self.engine) as session:
                ready.wait(timeout=5)
                try:
                    saved = boards.save_board(session, self.owner_id, board["id"], BoardSave(name=name, revision=1))
                    return (200, saved["name"])
                except boards.BoardError as error:
                    return (error.status, error.detail["latest"]["name"])

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, ["Tab A", "Tab B"]))
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        self.assertEqual(results[0][1], results[1][1])

    def test_conflict_copy_retains_migrated_asset_removed_from_latest(self):
        board = boards.create_board(self.session, self.owner_id, BoardCreate(name="Original", objects=[self.image()]))
        other = items.create_item(self.session, ItemCreate(title="Migrated source owner"))
        # Model a pre-migration sibling-item image retained by this board.
        self.asset.item_id = other.id
        self.session.commit()
        latest = boards.save_board(self.session, self.owner_id, board["id"], BoardSave(name="Latest", revision=1, objects=[]))
        # Local recovery must retain assets the stale client legitimately received,
        # even if the latest board and current deck no longer expose those assets.
        copy = boards.create_board(self.session, self.owner_id, BoardCreate(name="Recovered local", objects=board["objects"], view=board["view"]), source_id=board["id"])
        self.assertEqual(copy["objects"], board["objects"])
        self.assertEqual(boards.board_dict(self.session, boards.require_board(self.session, self.owner_id, latest["id"]))["objects"], [])


if __name__ == "__main__":
    unittest.main()
