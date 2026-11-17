"""Exercise actual Alembic upgrades on disposable databases, never the user's DB."""
from contextlib import closing
import json
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
            self.assertEqual(db.execute("SELECT version_num FROM alembic_version").fetchone()[0], "0004_item_board_ownership")
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

    def seed_boards(self):
        self.seed_0002()
        self.alembic("upgrade", "0003_visual_boards")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("PRAGMA foreign_keys=ON")
            # Destination IDs deliberately differ from Epic IDs; an equal-ID
            # fixture would miss accidental reuse of the old owner identity.
            db.execute("INSERT INTO items (id,title) VALUES (8,'Destination')")
            db.execute("INSERT INTO epics (id,name,normalized_name) VALUES (2,'Assets only','assets only')")
            db.execute("INSERT INTO project_assets (id,project_id,file_path,original_filename) VALUES (5,1,'project-1/source.png','source.png'),(6,2,'project-2/unused.png','unused.png')")
            db.execute("INSERT INTO visual_boards (id,project_id,name,revision,layout) VALUES (7,1,'Keep board',9,?)",
                       ('{"objects":[{"asset_key":"project:5"}],"view":{"zoom":0.7}}',))
            db.execute("INSERT INTO board_asset_references (id,board_id,item_asset_id) VALUES (11,7,1)")
            db.execute("INSERT INTO board_asset_references (id,board_id,project_asset_id) VALUES (12,7,5)")
            db.execute("INSERT INTO board_asset_access (id,board_id,item_asset_id) VALUES (13,7,1)")
            db.execute("INSERT INTO board_asset_access (id,board_id,project_asset_id) VALUES (14,7,5)")

    def snapshot(self):
        with closing(sqlite3.connect(self.path)) as db:
            return "\n".join(db.iterdump())

    def map_path(self, value):
        path = Path(self.temp.name) / "owners.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return str(path)

    def test_explicit_mapping_preserves_boards_sources_and_references(self):
        self.seed_boards()
        with closing(sqlite3.connect(self.path)) as db:
            board = db.execute("SELECT id,name,revision,layout,created_at,updated_at FROM visual_boards").fetchall()
            references = db.execute("SELECT * FROM board_asset_references ORDER BY id").fetchall()
            access = db.execute("SELECT * FROM board_asset_access ORDER BY id").fetchall()
        self.alembic("-x", f"board_owner_map={self.map_path({'1': 8, '2': 8})}", "upgrade", "head")
        self.assert_board_schema()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("PRAGMA foreign_keys=ON")
            self.assertEqual(db.execute("SELECT id,name,revision,layout,created_at,updated_at FROM visual_boards").fetchall(), board)
            self.assertEqual(db.execute("SELECT * FROM board_asset_references ORDER BY id").fetchall(), references)
            self.assertEqual(db.execute("SELECT * FROM board_asset_access ORDER BY id").fetchall(), access)
            self.assertEqual(db.execute("SELECT id,item_id FROM visual_boards").fetchall(), [(7, 8)])
            self.assertEqual(db.execute("SELECT id,item_id,file_path FROM project_assets ORDER BY id").fetchall(),
                             [(5, 8, 'project-1/source.png'), (6, 8, 'project-2/unused.png')])
            for table in ("visual_boards", "project_assets"):
                self.assertEqual([(row[2], row[3], row[4], row[6]) for row in db.execute(f"PRAGMA foreign_key_list({table})")],
                                 [("items", "item_id", "id", "RESTRICT")])
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM items WHERE id=8")

    def test_bad_mapping_stops_without_schema_or_data_changes(self):
        self.seed_boards()
        before = self.snapshot()
        for mapping in (None, {"1": 8}, {"1": 8, "2": 999}, {"1": True, "2": 8}):
            with self.subTest(mapping=mapping):
                args = [] if mapping is None else ["-x", f"board_owner_map={self.map_path(mapping)}"]
                result = subprocess.run([sys.executable, "-m", "alembic", *args, "upgrade", "head"],
                                        cwd=ROOT, env=self.env, text=True, capture_output=True, timeout=60)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("mapping", result.stderr)
                self.assertEqual(self.snapshot(), before)

    def test_installer_accepts_owner_map(self):
        self.seed_boards()
        result = subprocess.run([sys.executable, "-m", "scripts.migrate_database", "--board-owner-map",
                                 self.map_path({"1": 8, "2": 8})], cwd=ROOT, env=self.env,
                                text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_board_schema()

    def test_foreign_key_failure_rolls_back_rebuilt_tables(self):
        self.seed_boards()
        with closing(sqlite3.connect(self.path)) as db, db:
            # Simulate legacy corruption to force failure after both parent
            # rebuilds; DDL, owner updates, and the revision must all roll back.
            db.execute("UPDATE board_asset_references SET item_asset_id=999 WHERE id=11")
        before = self.snapshot()
        result = subprocess.run([sys.executable, "-m", "alembic", "-x",
                                 f"board_owner_map={self.map_path({'1': 8, '2': 8})}", "upgrade", "head"],
                                cwd=ROOT, env=self.env, text=True, capture_output=True, timeout=60)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("foreign keys", result.stderr)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()

