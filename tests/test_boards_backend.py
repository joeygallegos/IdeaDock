"""Visual-board persistence and failure tests use only temporary storage."""
import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base
from app.models import BoardAssetReference, Epic, ItemStatus, MoodBoardAsset, ProjectAsset, VisualBoard
from app.schemas import BoardCreate, BoardSave, ItemCreate, ItemUpdate
from app.services import boards, items

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aR1sAAAAASUVORK5CYII=")


def image(key, object_id="image", **changes):
    return dict(id=object_id, type="image", asset_key=key, x=12, y=-4, width=200, height=100, **changes)


def payload(board, **changes):
    value = {k: board[k] for k in ("name", "objects", "view", "revision")}
    value.update(changes)
    return BoardSave(**value)


class BoardBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.temp.name) / 'test.db'}")
        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.uploads = patch.object(settings, "upload_dir", str(Path(self.temp.name) / "uploads"))
        self.uploads.start()
        self.item = items.create_item(self.session, ItemCreate(title="Inspiration", epic_names=["Home"]))
        self.project_id = self.item.epic_id
        self.other = Epic(name="Other", normalized_name="other")
        self.session.add(self.other)
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        self.uploads.stop()
        self.temp.cleanup()

    def upload(self):
        return boards.upload_project_asset(self.session, self.project_id, "photo.png", PNG)

    def test_all_objects_view_round_trip_and_independent_boards(self):
        asset = self.upload()
        objects = [image(asset["key"]), dict(id="label", type="text", text="Direction A", x=0, y=10, width=80, height=30),
                   dict(id="swatch", type="swatch", color="#aabbcc", x=20, y=10, width=40, height=40)]
        one = boards.create_board(self.session, self.project_id, BoardCreate(name="First", objects=objects, view=dict(x=-100, y=50, zoom=.75)))
        two = boards.create_board(self.session, self.project_id, BoardCreate(name="Second", objects=[image(asset["key"])]))
        one = boards.save_board(self.session, self.project_id, one["id"], payload(one, objects=list(reversed(objects))))
        self.session.expire_all()
        reloaded = boards.board_dict(self.session, boards.require_board(self.session, self.project_id, one["id"]))
        self.assertEqual(reloaded["objects"], list(reversed(objects)))
        self.assertEqual(reloaded["view"], dict(x=-100, y=50, zoom=.75))
        self.assertEqual(len(boards.list_boards(self.session, self.project_id)), 2)
        self.assertEqual(boards.board_dict(self.session, boards.require_board(self.session, self.project_id, two["id"]))["revision"], 1)
        stored = self.session.get(ProjectAsset, asset["id"])
        self.assertEqual((settings.upload_path / stored.file_path).read_bytes(), PNG)

    def test_combined_completed_legacy_and_duplicate_membership(self):
        item_asset = items.add_mood_board_asset(self.session, item_id=self.item.id, original_filename="item.png", content=PNG)
        items.update_item(self.session, self.item.id, ItemUpdate(status=ItemStatus.done, is_archived=True))
        direct = self.upload()
        deck = boards.project_assets(self.session, self.project_id)
        self.assertEqual({a["key"] for a in deck}, {f"item:{item_asset.id}", direct["key"]})
        self.assertEqual(len(deck), 2)
        self.item.epics.clear()
        self.session.commit()
        self.assertEqual(len(boards.project_assets(self.session, self.project_id)), 2)
        self.assertEqual(boards.project_assets(self.session, self.other.id), [])

    def test_moved_source_retained_and_copy_and_deletion_protected(self):
        source = items.add_mood_board_asset(self.session, item_id=self.item.id, original_filename="item.png", content=PNG)
        key = f"item:{source.id}"
        board = boards.create_board(self.session, self.project_id, BoardCreate(name="Original", objects=[image(key)]))
        items.update_item(self.session, self.item.id, ItemUpdate(epic_names=["Other"]))
        self.assertEqual(boards.project_assets(self.session, self.project_id), [])
        saved = boards.save_board(self.session, self.project_id, board["id"], payload(board))
        self.assertEqual(saved["assets"][0]["key"], key)
        copy = boards.create_board(self.session, self.project_id, BoardCreate(name="Copy", objects=saved["objects"], view=saved["view"]), source_id=board["id"])
        with self.assertRaises(boards.BoardError) as caught:
            items.delete_mood_board_asset(self.session, source.id)
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual({b["name"] for b in caught.exception.detail["boards"]}, {"Original", "Copy"})
        boards.delete_board(self.session, self.project_id, board["id"], saved["revision"])
        self.assertTrue((settings.upload_path / source.file_path).exists())
        boards.save_board(self.session, self.project_id, copy["id"], payload(copy, objects=[]))
        self.assertTrue(items.delete_mood_board_asset(self.session, source.id))

    def test_project_isolation_and_failed_save_is_atomic(self):
        asset = self.upload()
        board = boards.create_board(self.session, self.project_id, BoardCreate(name="Home"))
        for action in [lambda: boards.require_board(self.session, self.other.id, board["id"]),
                       lambda: boards.create_board(self.session, self.other.id, BoardCreate(name="Cross", objects=[image(asset["key"])])),
                       lambda: boards.create_board(self.session, self.other.id, BoardCreate(name="Copy"), source_id=board["id"])]:
            with self.assertRaises(boards.BoardError):
                action()
        with self.assertRaises(boards.BoardError):
            boards.save_board(self.session, self.project_id, board["id"], payload(board, objects=[image("project:99999")]))
        original = boards.board_dict(self.session, boards.require_board(self.session, self.project_id, board["id"]))
        self.assertEqual(original["revision"], 1)
        self.assertEqual(original["objects"], [])

    def test_conflict_copy_retains_history_without_granting_other_boards_access(self):
        source = items.add_mood_board_asset(
            self.session, item_id=self.item.id, original_filename="item.png", content=PNG
        )
        key = f"item:{source.id}"
        board = boards.create_board(
            self.session, self.project_id,
            BoardCreate(name="Original", objects=[image(key)]),
        )
        unrelated = boards.create_board(
            self.session, self.project_id, BoardCreate(name="Unrelated")
        )
        items.update_item(self.session, self.item.id, ItemUpdate(epic_names=["Other"]))
        boards.save_board(
            self.session, self.project_id, board["id"], payload(board, objects=[])
        )
        # Local state still has the image even though the latest version no longer does.
        local = BoardCreate(name="Recovered", objects=board["objects"], view=board["view"])
        recovered = boards.create_board(
            self.session, self.project_id, local, source_id=board["id"]
        )
        self.assertEqual(recovered["assets"][0]["key"], key)
        with self.assertRaises(boards.BoardError):
            boards.create_board(
                self.session, self.project_id, local, source_id=unrelated["id"]
            )
        boards.delete_board(self.session, self.project_id, recovered["id"], 1)
        self.assertTrue(items.delete_mood_board_asset(self.session, source.id))
        # Access history disappears with the source; it must never block deletion.
        from app.models import BoardAssetAccess
        self.assertEqual(boards.reference_keys(self.session, board["id"], BoardAssetAccess), set())

    def test_conflict_and_copy_preserve_latest(self):
        board = boards.create_board(self.session, self.project_id, BoardCreate(name="Original"))
        with Session(self.engine) as second:
            stale = boards.board_dict(second, boards.require_board(second, self.project_id, board["id"]))
            current = boards.save_board(self.session, self.project_id, board["id"], payload(board, name="Latest"))
            with self.assertRaises(boards.BoardError) as caught:
                boards.save_board(second, self.project_id, board["id"], payload(stale, name="Local"))
            self.assertEqual(caught.exception.status, 409)
            self.assertEqual(caught.exception.detail["latest"]["name"], "Latest")
            local_copy = boards.create_board(second, self.project_id, BoardCreate(name="Local copy"), source_id=board["id"])
            self.assertNotEqual(local_copy["id"], board["id"])
            with self.assertRaises(boards.BoardError):
                boards.delete_board(second, self.project_id, board["id"], 1)
            self.assertEqual(boards.require_board(second, self.project_id, board["id"]).revision, current["revision"])

    def test_project_asset_guard_and_placement_removal(self):
        asset = self.upload()
        board = boards.create_board(self.session, self.project_id, BoardCreate(name="Used", objects=[image(asset["key"])]))
        with self.assertRaises(boards.BoardError):
            boards.delete_source_asset(self.session, "project", asset["id"], self.project_id)
        boards.save_board(self.session, self.project_id, board["id"], payload(board, objects=[]))
        self.assertEqual(len(boards.project_assets(self.session, self.project_id)), 1)
        boards.delete_source_asset(self.session, "project", asset["id"], self.project_id)
        self.assertEqual(boards.project_assets(self.session, self.project_id), [])

    def test_validation_rejects_invalid_geometry_and_object_content(self):
        for field, value in [("x", float("nan")), ("y", float("inf")), ("width", 0), ("height", -1), ("x", "10"), ("x", True)]:
            obj = image("project:1")
            obj[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                BoardCreate(name="Bad", objects=[obj])
        for value in [dict(name=" "), dict(name="Bad", view=dict(zoom=0)), dict(name="Bad", objects=[image("project:1"), image("project:1")]),
                      dict(name="Bad", objects=[dict(id="s", type="swatch", x=0,y=0,width=10,height=10,color="red")])]:
            with self.assertRaises(ValidationError):
                BoardCreate(**value)

    def test_upload_validation_and_database_failure_cleanup(self):
        for name, data in [("bad.png", b"not an image"), ("bad.svg", b"<svg/>"), ("bad.jpg", PNG), ("empty.png", b"")]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                boards.upload_project_asset(self.session, self.project_id, name, data)
        with patch.object(settings, "max_upload_bytes", 10), self.assertRaises(ValueError):
            self.upload()
        with patch.object(self.session, "commit", side_effect=RuntimeError("database unavailable")), self.assertRaises(RuntimeError):
            self.upload()
        self.assertEqual(list(settings.upload_path.rglob("*.png")), [])
        asset = boards.upload_project_asset(self.session, self.project_id, "../../safe.png", PNG)
        self.assertEqual(asset["original_filename"], "safe.png")
        stored = self.session.get(ProjectAsset, asset["id"])
        self.assertTrue((settings.upload_path / stored.file_path).resolve().is_relative_to(settings.upload_path))


if __name__ == "__main__":
    unittest.main()
