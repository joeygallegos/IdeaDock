"""Independent lifecycle tests across existing items and the new board service."""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
from unittest.mock import patch

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
        self.project = self.item.epic_id
        self.asset = items.add_mood_board_asset(self.session, item_id=self.item.id, original_filename="sample.png", content=PNG)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        self.uploads.stop()
        self.temp.cleanup()

    def image(self, key=None):
        return dict(id="image-1", type="image", asset_key=key or f"item:{self.asset.id}", x=10, y=20, width=100, height=50)

    def test_deck_deduplicates_completed_items_and_isolates_projects(self):
        direct = boards.upload_project_asset(self.session, self.project, "direct.png", PNG)
        deck = boards.project_assets(self.session, self.project)
        self.assertEqual({asset["key"] for asset in deck}, {direct["key"], f"item:{self.asset.id}"})
        self.assertEqual(len(deck), 2)
        other = items.create_item(self.session, ItemCreate(title="Other", epic_names=["Work"]))
        self.assertEqual(boards.project_assets(self.session, other.epic_id), [])
        with self.assertRaises(boards.BoardError) as caught:
            boards.create_board(self.session, other.epic_id, BoardCreate(name="Wrong project", objects=[self.image()]))
        self.assertEqual(caught.exception.status, 400)

    def test_moving_item_preserves_placements_and_copy_then_deletion_guard(self):
        first = boards.create_board(self.session, self.project, BoardCreate(name="First", objects=[self.image()]))
        items.update_item(self.session, self.item.id, ItemUpdate(epic_names=["Work"]))
        self.assertEqual(boards.project_assets(self.session, self.project), [])
        latest = boards.board_dict(self.session, boards.require_board(self.session, self.project, first["id"]))
        self.assertEqual(latest["assets"][0]["key"], f"item:{self.asset.id}")
        copy = boards.create_board(self.session, self.project, BoardCreate(name="Copy", objects=latest["objects"], view=latest["view"]), source_id=first["id"])
        with self.assertRaises(boards.BoardError) as caught:
            items.delete_mood_board_asset(self.session, self.asset.id)
        self.assertEqual({b["name"] for b in caught.exception.detail["boards"]}, {"First", "Copy"})
        boards.delete_board(self.session, self.project, first["id"], first["revision"])
        path = settings.upload_path / self.asset.file_path
        self.assertTrue(path.exists())
        self.assertEqual(boards.board_dict(self.session, boards.require_board(self.session, self.project, copy["id"]))["objects"], copy["objects"])
        boards.delete_board(self.session, self.project, copy["id"], copy["revision"])
        self.assertTrue(items.delete_mood_board_asset(self.session, self.asset.id))
        self.assertFalse(path.exists())

    def test_two_sessions_cannot_overwrite_same_revision(self):
        board = boards.create_board(self.session, self.project, BoardCreate(name="Original"))
        with Session(self.engine) as second:
            # Both clients possess revision 1 before either attempts persistence.
            stale = boards.board_dict(second, boards.require_board(second, self.project, board["id"]))
            winner = boards.save_board(self.session, self.project, board["id"], BoardSave(name="Winner", revision=1, objects=[self.image()]))
            with self.assertRaises(boards.BoardError) as caught:
                boards.save_board(second, self.project, board["id"], BoardSave(name="Stale", revision=stale["revision"]))
            self.assertEqual(caught.exception.status, 409)
            self.assertEqual(caught.exception.detail["latest"]["name"], "Winner")
            self.assertEqual(caught.exception.detail["latest"]["objects"], winner["objects"])
            with self.assertRaises(boards.BoardError):
                boards.delete_board(second, self.project, board["id"], stale["revision"])
            self.assertEqual(boards.require_board(second, self.project, board["id"]).name, "Winner")

    def test_concurrent_revision_claim_has_exactly_one_winner(self):
        board = boards.create_board(self.session, self.project, BoardCreate(name="Original"))
        ready = Barrier(2)

        def save(name):
            with Session(self.engine) as session:
                ready.wait(timeout=5)
                try:
                    saved = boards.save_board(session, self.project, board["id"], BoardSave(name=name, revision=1))
                    return (200, saved["name"])
                except boards.BoardError as error:
                    return (error.status, error.detail["latest"]["name"])

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, ["Tab A", "Tab B"]))
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        self.assertEqual(results[0][1], results[1][1])

    def test_conflict_copy_retains_moved_asset_removed_from_latest(self):
        board = boards.create_board(self.session, self.project, BoardCreate(name="Original", objects=[self.image()]))
        items.update_item(self.session, self.item.id, ItemUpdate(epic_names=["Work"]))
        latest = boards.save_board(self.session, self.project, board["id"], BoardSave(name="Latest", revision=1, objects=[]))
        # Local recovery must retain assets the stale client legitimately received,
        # even if the latest board and current deck no longer expose those assets.
        copy = boards.create_board(self.session, self.project, BoardCreate(name="Recovered local", objects=board["objects"], view=board["view"]), source_id=board["id"])
        self.assertEqual(copy["objects"], board["objects"])
        self.assertEqual(boards.board_dict(self.session, boards.require_board(self.session, self.project, latest["id"]))["objects"], [])


if __name__ == "__main__":
    unittest.main()
