"""Regression coverage for the item contracts that project boards must preserve."""
import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base
from app.models import ItemStatus, ItemType, Priority
from app.parser import parse_quick_entry
from app.schemas import ItemCreate, ItemUpdate
from app.services import items


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aR1sAAAAASUVORK5CYII="
)


class ExistingWorkflowTests(unittest.TestCase):
    def setUp(self):
        # Never bind a regression test to the configured, user-owned database.
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.uploads = patch.object(settings, "upload_dir", self.temp.name)
        self.uploads.start()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        self.uploads.stop()
        self.temp.cleanup()

    def test_structured_capture_and_unknown_tokens(self):
        raw = "Call bank #Money #House -task @Chase !high due:2026-10-25 -unknown"
        item = items.create_item(self.session, ItemCreate(raw_input=raw))
        self.assertEqual(item.title, "Call bank -unknown")
        self.assertEqual(item.raw_input, raw)
        self.assertEqual(item.item_type, ItemType.task)
        self.assertEqual(item.priority, Priority.high)
        self.assertEqual({epic.name for epic in item.epics}, {"Money", "House"})
        self.assertEqual(item.entity_links[0].entity.name, "Chase")
        self.assertEqual(item.status, ItemStatus.inbox)

    def test_capture_defaults_and_invalid_date_remain_usable(self):
        parsed = parse_quick_entry("New idea due:nope")
        self.assertTrue(parsed.warnings)
        item = items.create_item(self.session, ItemCreate(raw_input=parsed.raw_input))
        self.assertEqual(item.title, "New idea due:nope")
        self.assertEqual(item.item_type, ItemType.idea)

    def test_completed_items_are_queryable_and_reopenable(self):
        item = items.create_item(self.session, ItemCreate(title="Finished", epic_names=["Home"]))
        item = items.update_item(self.session, item.id, ItemUpdate(status="done"))
        self.assertIsNotNone(item.completed_at)
        self.assertEqual(items.list_items(self.session, active_only=True), [])
        self.assertEqual([row.id for row in items.list_items(self.session, status=ItemStatus.done)], [item.id])
        item = items.update_item(self.session, item.id, ItemUpdate(status="next"))
        self.assertIsNone(item.completed_at)

    def test_existing_item_upload_metadata_and_delete(self):
        item = items.create_item(self.session, ItemCreate(title="Inspiration"))
        asset = items.add_mood_board_asset(
            self.session, item_id=item.id, original_filename="../sample.png",
            content=PNG, caption="  First image  ", sort_order=7,
        )
        path = settings.upload_path / asset.file_path
        self.assertTrue(path.is_relative_to(Path(self.temp.name)))
        self.assertEqual(path.read_bytes(), PNG)
        self.assertEqual(asset.caption, "First image")
        self.assertEqual(asset.sort_order, 7)
        self.assertEqual(items.get_item(self.session, item.id).mood_board_assets[0].id, asset.id)
        self.assertTrue(items.delete_mood_board_asset(self.session, asset.id))
        self.assertFalse(path.exists())
        self.assertIsNotNone(items.get_item(self.session, item.id))

    def test_upload_rejects_unsupported_extension_and_oversize(self):
        item = items.create_item(self.session, ItemCreate(title="Inspiration"))
        for name, content in [("file.txt", b"text"), ("large.png", PNG)]:
            with self.subTest(name=name), patch.object(settings, "max_upload_bytes", 20):
                with self.assertRaises(ValueError):
                    items.add_mood_board_asset(self.session, item_id=item.id, original_filename=name, content=content)
        self.assertEqual(list(Path(self.temp.name).rglob("*")), [])


if __name__ == "__main__":
    unittest.main()
