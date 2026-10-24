"""Verify the installer's migration entrypoint against disposable legacy schemas."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = '0001_initial_schema'
MULTI = '0002_item_epics_many_to_many'
HEAD = '0003_visual_boards'
BOARD_TABLES = {'project_assets', 'visual_boards', 'board_asset_references', 'board_asset_access'}


class SetupMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'installer.db'
        self.upload_root = Path(self.temp.name) / 'uploads'
        self.source_file = self.upload_root / 'item-1' / 'original.png'
        self.source_file.parent.mkdir(parents=True)
        self.source_file.write_bytes(b'original uploaded bytes retained by migration')
        self.env = dict(os.environ, DATABASE_URL=f'sqlite:///{self.path.as_posix()}',
                        UPLOAD_DIR=str(self.upload_root), AUTO_BOOTSTRAP_DB='false')

    def tearDown(self):
        self.temp.cleanup()

    def run_python(self, *args):
        return subprocess.run([sys.executable, *args], cwd=ROOT, env=self.env,
                              capture_output=True, text=True, timeout=60)

    def seed(self, revision, tracking='tracked'):
        result = self.run_python('-m', 'alembic', 'upgrade', revision)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.seed_rows(revision, tracking)

    def seed_rows(self, revision, tracking='tracked'):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO epics (id,name,normalized_name) VALUES (1,'Home','home')")
            db.execute("INSERT INTO items (id,title,epic_id) VALUES (1,'Original note',1)")
            if revision != BASE:
                db.execute('INSERT INTO item_epics VALUES (1,1)')
            db.execute("INSERT INTO mood_board_assets (id,item_id,file_path,original_filename,caption) VALUES (1,1,'item-1/original.png','original.png','Keep me')")
            if tracking == 'absent':
                db.execute('DROP TABLE alembic_version')
            elif tracking == 'empty':
                db.execute('DELETE FROM alembic_version')

    def install_migrations(self, success=True):
        result = self.run_python('-m', 'scripts.migrate_database')
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def snapshot(self):
        # Logical dumps catch stamps, DDL, and data changes without depending on
        # SQLite file-header housekeeping bytes or journal configuration.
        with closing(sqlite3.connect(self.path)) as db:
            return '\n'.join(db.iterdump())

    def assert_current(self, has_data=True):
        self.assertEqual(self.source_file.read_bytes(), b'original uploaded bytes retained by migration')
        with closing(sqlite3.connect(self.path)) as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue(BOARD_TABLES <= tables, tables)
            self.assertEqual(db.execute('SELECT version_num FROM alembic_version').fetchall(), [(HEAD,)])
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            if has_data:
                self.assertEqual(db.execute('SELECT title,epic_id FROM items').fetchall(), [('Original note', 1)])
                self.assertEqual(db.execute('SELECT item_id,epic_id FROM item_epics').fetchall(), [(1, 1)])
                self.assertEqual(db.execute('SELECT file_path,original_filename,caption FROM mood_board_assets').fetchall(), [('item-1/original.png', 'original.png', 'Keep me')])

    def test_fresh_database(self):
        self.install_migrations()
        self.assert_current(has_data=False)

    def test_tracked_0001_runs_backfill_and_board_upgrade(self):
        self.seed(BASE)
        self.install_migrations()
        self.assert_current()

    def test_tracked_0002_runs_board_upgrade(self):
        self.seed(MULTI)
        self.install_migrations()
        self.assert_current()

    def test_unversioned_0001_is_baselined_then_migrated(self):
        self.seed(BASE, 'absent')
        self.install_migrations()
        self.assert_current()

    def test_unversioned_0002_is_baselined_then_migrated(self):
        self.seed(MULTI, 'absent')
        self.install_migrations()
        self.assert_current()

    def test_empty_version_table_is_not_treated_as_current(self):
        self.seed(MULTI, 'empty')
        self.install_migrations()
        self.assert_current()

    def test_unversioned_0002_repairs_missing_legacy_membership(self):
        self.seed(MULTI, 'absent')
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DELETE FROM item_epics')
        self.install_migrations()
        self.assert_current()

    def test_real_orm_bootstrap_legacy_shapes_are_recognized(self):
        for include_membership in (False, True):
            with self.subTest(include_membership=include_membership):
                # Model-created databases are the historical bootstrap pathway;
                # migration-only fixtures could hide differences in reflected DDL.
                code = (
                    'from app.db import Base, engine; from app import models; '
                    f'excluded = {BOARD_TABLES | (set() if include_membership else {"item_epics"})!r}; '
                    'Base.metadata.create_all(engine, tables=[table for name, table in Base.metadata.tables.items() if name not in excluded]); '
                    'engine.dispose()'
                )
                self.path = Path(self.temp.name) / f'bootstrap-{include_membership}.db'
                self.env['DATABASE_URL'] = f'sqlite:///{self.path.as_posix()}'
                result = self.run_python('-c', code)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.seed_rows(MULTI if include_membership else BASE)
                self.install_migrations()
                self.assert_current()

    def test_current_schema_is_idempotent(self):
        self.seed(HEAD)
        before = self.snapshot()
        self.install_migrations()
        self.assert_current()
        self.assertEqual(self.snapshot(), before)

    def test_partial_legacy_schema_rejected_without_any_modification(self):
        self.seed(BASE, 'absent')
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DROP TABLE tags')
        before = self.snapshot()
        self.install_migrations(success=False)
        self.assertEqual(self.snapshot(), before)

    def test_malformed_legacy_columns_rejected_without_any_modification(self):
        self.seed(MULTI, 'empty')
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('ALTER TABLE mood_board_assets RENAME COLUMN caption TO obsolete_caption')
        before = self.snapshot()
        self.install_migrations(success=False)
        self.assertEqual(self.snapshot(), before)

    def test_partial_board_tables_rejected_without_head_stamp(self):
        self.seed(MULTI, 'absent')
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE visual_boards (id INTEGER PRIMARY KEY)')
        before = self.snapshot()
        self.install_migrations(success=False)
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
