# -*- coding: utf-8 -*-
"""A5: restoring an older-schema backup must bring the schema up to date.

Builds a genuine old-schema database (``migrate inventory 0003`` — before
``settled_at``, ``invoice_code``, and the ``sale_price``/``final_price``
removals), restores it, and asserts the app keeps working instead of
returning 500s / NOT-NULL failures.

The ORM connection is repointed at a scratch file with the same trick the
Django test runner itself uses (``connection.settings_dict["NAME"]``) — but
sqlite3's ``close()`` ignores in-memory connections (Django does this on
purpose to keep the shared-cache test DB alive), so the raw connection must
be dropped explicitly or queries keep hitting the in-memory test DB. The
in-memory DB is rebuilt in ``tearDownClass`` for the classes that follow.
``dbhelpers``' import-time path constants are patched (same technique as
``tests/test_legacy_api_baseline.py``).
"""
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.db import connections
from django.test import TransactionTestCase

from inventory import dbhelpers
from tests.helpers import product_payload

JSON_TYPE = "application/json"

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _set_conn_name(conn, name):
    """Repoint a live connection at another database file."""
    conn.close()
    # sqlite3's close() is a no-op for in-memory DBs; drop the raw
    # connection so the next query really reconnects to `name`
    conn.connection = None
    conn.settings_dict["NAME"] = name


class OldSchemaRestoreTests(TransactionTestCase):
    """Restoring a 0003-era backup must migrate, not break the app."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.live_path = os.path.join(cls.tmp.name, "live.sqlite3")
        cls.old_path = os.path.join(cls.tmp.name, "old_schema.sqlite3")

        # a genuine old-schema DB, built by the real migration machinery
        # (never touches the real db/ — TIKOTIME_DB points at the scratch file)
        env = dict(os.environ, TIKOTIME_DB=cls.old_path)
        proc = subprocess.run(
            [sys.executable, "manage.py", "migrate", "inventory", "0003"],
            cwd=str(BACKEND_DIR), env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            raise AssertionError(
                f"migrate inventory 0003 failed:\n{proc.stderr}")

        # the ORM connection and dbhelpers must both talk to the live file
        cls._original_name = connections["default"].settings_dict["NAME"]
        _set_conn_name(connections["default"], cls.live_path)
        for attr, value in (("DB_PATH", cls.live_path),
                            ("BACKUP_DIR", cls.tmp.name)):
            patcher = mock.patch.object(dbhelpers, attr, value)
            patcher.start()
            cls.addClassCleanup(patcher.stop)

        # the deployed app runs at the latest migration state
        call_command("migrate", verbosity=0, interactive=False)

    @classmethod
    def tearDownClass(cls):
        # back to the runner's in-memory DB; its raw connection was dropped
        # in setUpClass, so rebuild the schema for the classes that follow
        _set_conn_name(connections["default"], cls._original_name)
        call_command("migrate", verbosity=0, interactive=False)
        super().tearDownClass()

    def test_old_schema_backup_restore_keeps_app_working(self):
        with open(self.old_path, "rb") as fh:
            data = fh.read()
        with open(os.path.join(self.tmp.name, "old_backup.db"), "wb") as out:
            out.write(data)

        # the restore endpoint (the upload-then-restore flow shares this path)
        r = self.client.post("/api/backups/restore", {"name": "old_backup.db"},
                             content_type=JSON_TYPE)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["ok"])
        self.assertTrue(
            any(n.startswith("pre_restore_") for n in os.listdir(self.tmp.name)),
            "restore must keep its automatic pre-restore backup")

        # the old schema lacks invoice_code (sales) and settled_at (payments)
        # — both endpoints used to 500 after such a restore
        r = self.client.get("/api/sales")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["summary"]["count"], 0)

        r = self.client.get("/api/payments")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["ok"])

        # products.sale_price (NOT NULL, dropped in 0008) used to break creation
        r = self.client.post("/api/products", product_payload(),
                             content_type=JSON_TYPE)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["ok"])

        # the restored file must be fully migrated, not just patched
        conn = sqlite3.connect(self.live_path)
        cols = {c[1] for c in conn.execute("PRAGMA table_info(sales)")}
        conn.close()
        self.assertIn("invoice_code", cols)

    def test_failed_migrate_reports_the_pre_restore_backup(self):
        dbhelpers.backup_db("good.db")

        # a file with only a products table — schema sync cannot fix it
        junk = os.path.join(self.tmp.name, "junk_backup.db")
        conn = sqlite3.connect(junk)
        conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)")
        conn.commit()
        conn.close()

        good, err = dbhelpers.restore_db("junk_backup.db")
        self.assertFalse(good)
        self.assertIn("pre_restore_", err)
        self.assertTrue(any(n.startswith("pre_restore_")
                            for n in os.listdir(self.tmp.name)))

        # falling back to the good backup leaves a working app behind
        good, err = dbhelpers.restore_db("good.db")
        self.assertTrue(good, err)
        r = self.client.get("/api/sales")
        self.assertEqual(r.status_code, 200, r.content)
