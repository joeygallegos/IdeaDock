"""Exercise actual Alembic upgrades on disposable databases, never the user's DB."""
from contextlib import closing
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BoardMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "migration.db"
        self.env = dict(os.environ, DATABASE_URL=f"sqlite:///{self.path.as_posix()}", AUTO_BOOTSTRAP_DB="false")

    def tearDown(self):
        self.temp.cleanup()

    def alembic(self, *args):
        # A subprocess avoids cached Settings redirecting a migration to another DB.
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *args], cwd=ROOT, env=self.env,
            text=True, capture_output=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_board_schema(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue(any("board" in name and name != "mood_board_assets" for name in tables), tables)
            self.assertTrue(db.execute("SELECT version_num FROM alembic_version").fetchone()[0].startswith("0003"))
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def seed_0002(self):
        self.alembic("upgrade", "0002_item_epics_many_to_many")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO epics (id,name,normalized_name) VALUES (1,'Home','home')")
            db.execute("INSERT INTO items (id,title,epic_id) VALUES (1,'Original note',1)")
            db.execute("INSERT INTO item_epics VALUES (1,1)")
            db.execute("INSERT INTO mood_board_assets (id,item_id,file_path,original_filename,caption) VALUES (1,1,'item-1/original.png','original.png','Keep me')")

    def assert_legacy_data(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute("SELECT title,epic_id FROM items").fetchall(), [("Original note", 1)])
            self.assertEqual(db.execute("SELECT * FROM item_epics").fetchall(), [(1, 1)])
            self.assertEqual(db.execute("SELECT file_path,caption FROM mood_board_assets").fetchall(), [("item-1/original.png", "Keep me")])

    def test_fresh_upgrade(self):
        self.alembic("upgrade", "head")
        self.assert_board_schema()

    def test_0002_upgrade_preserves_item_uploads(self):
        self.seed_0002()
        self.alembic("upgrade", "head")
        self.assert_board_schema()
        self.assert_legacy_data()

    def test_known_unversioned_0002_baseline_can_be_stamped_then_upgraded(self):
        self.seed_0002()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM alembic_version")
        # This tests the documented known-schema recovery, not arbitrary legacy schemas.
        self.alembic("stamp", "0002_item_epics_many_to_many")
        self.alembic("upgrade", "head")
        self.assert_board_schema()
        self.assert_legacy_data()


if __name__ == "__main__":
    unittest.main()

