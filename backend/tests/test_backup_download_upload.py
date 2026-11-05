# -*- coding: utf-8 -*-
"""Backup download/upload API: images travel with the backup.

Every test runs on throwaway temp dirs; the real ``db/`` is never touched.
``dbhelpers`` path constants and ``django.conf.settings`` path attributes are
patched to the same temp locations so the views and the helpers agree.
"""

import io
import os
import sqlite3
import tempfile
import zipfile
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from inventory import dbhelpers


def _make_db(db_path):
    """Create a minimal TikoTime-flavoured sqlite db with a ``products`` table."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, office_code TEXT, "
            "website_code TEXT, brand TEXT)")
        conn.execute(
            "INSERT INTO products (name, office_code, website_code, brand) "
            "VALUES ('ساعت نمونه', 'OF-1', 'WS-1', '')")
        conn.commit()
    finally:
        conn.close()


@contextmanager
def _patched(tmp):
    db_path = os.path.join(tmp, "t.sqlite3")
    img_dir = os.path.join(tmp, "images")
    backup_dir = os.path.join(tmp, "backups")
    _make_db(db_path)
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)
    patches = [
        mock.patch.object(dbhelpers, "DB_PATH", db_path),
        mock.patch.object(dbhelpers, "IMG_DIR", img_dir),
        mock.patch.object(dbhelpers, "BACKUP_DIR", backup_dir),
        mock.patch.object(settings, "BACKUP_DIR", backup_dir),
        mock.patch.object(settings, "IMG_DIR", img_dir),
    ]
    for p in patches:
        p.start()
    try:
        yield SimpleNamespace(db_path=db_path, img_dir=img_dir, backup_dir=backup_dir)
    finally:
        for p in reversed(patches):
            p.stop()


class BackupDownloadUploadTests(TestCase):
    """GET/POST /api/backups/{download,upload} with the ``.images.zip`` sidecar."""

    def test_download_with_images_returns_bundle_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            img_dir = os.path.join(tmp, "images")
            os.makedirs(img_dir, exist_ok=True)
            with open(os.path.join(img_dir, "a.png"), "wb") as f:
                f.write(b"PNG-A")
            with open(os.path.join(img_dir, "b.jpg"), "wb") as f:
                f.write(b"JPG-B")
            with _patched(tmp) as p:
                target = dbhelpers.backup_db()
                name = os.path.basename(target)
                stem = os.path.splitext(name)[0]
                resp = self.client.get(f"/api/backups/download/{name}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get("Content-Type"), "application/zip")
        self.assertEqual(resp["Content-Disposition"], f'attachment; filename="{stem}.zip"')
        body = b"".join(resp.streaming_content)
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            names = sorted(zf.namelist())
            self.assertIn(f"{stem}.db", names)
            self.assertIn("images/a.png", names)
            self.assertIn("images/b.jpg", names)
            for info in zf.infolist():
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)

    def test_download_old_backup_without_images_returns_plain_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _patched(tmp) as p:
                target = dbhelpers.backup_db()
                os.remove(os.path.splitext(target)[0] + ".images.zip")
                name = os.path.basename(target)
                resp = self.client.get(f"/api/backups/download/{name}")
                with open(target, "rb") as f:
                    expected = f.read()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get("Content-Type"), "application/octet-stream")
        self.assertEqual(resp["Content-Disposition"], f'attachment; filename="{name}"')
        self.assertEqual(b"".join(resp.streaming_content), expected)

    def test_download_missing_returns_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _patched(tmp):
                resp = self.client.get("/api/backups/download/does-not-exist.db")
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(resp.json()["ok"])

    def test_upload_zip_appears_in_list_and_restore_brings_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_db = os.path.join(tmp, "bundle.db")
            _make_db(tmp_db)
            with open(tmp_db, "rb") as f:
                db_bytes = f.read()
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_STORED) as zf:
                zf.writestr("bundle.db", db_bytes)
                zf.writestr("a.png", b"PNG-A")
                zf.writestr("b.jpg", b"JPG-B")
            with _patched(tmp) as p:
                uploaded = SimpleUploadedFile(
                    "bundle.zip", zip_buf.getvalue(), content_type="application/zip")
                resp = self.client.post("/api/backups/upload", {"file": uploaded})
                self.assertEqual(resp.status_code, 200)
                self.assertTrue(resp.json()["ok"], resp.json())
                self.assertEqual(resp.json()["name"], "bundle.db")
                listed = self.client.get("/api/backups").json()["backups"]
                self.assertIn("bundle.db", [n["name"] for n in listed])
                rest = self.client.post("/api/backups/restore",
                                        {"name": "bundle.db"}, content_type="application/json")
                self.assertEqual(rest.status_code, 200)
                self.assertTrue(rest.json()["ok"], rest.json())
                self.assertEqual(sorted(os.listdir(p.img_dir)), ["a.png", "b.jpg"])

    def test_upload_zip_with_malicious_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_db = os.path.join(tmp, "evil.db")
            _make_db(tmp_db)
            with open(tmp_db, "rb") as f:
                db_bytes = f.read()
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_STORED) as zf:
                zf.writestr("evil.db", db_bytes)
                zf.writestr("../evil.png", b"evil")
            with _patched(tmp) as p:
                uploaded = SimpleUploadedFile(
                    "evil.zip", zip_buf.getvalue(), content_type="application/zip")
                resp = self.client.post("/api/backups/upload", {"file": uploaded})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])
        self.assertIn("نام فایل در بکاپ نامعتبر است", resp.json()["error"])

    def test_upload_zip_without_db_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_STORED) as zf:
                zf.writestr("a.png", b"PNG-A")
            with _patched(tmp) as p:
                uploaded = SimpleUploadedFile(
                    "nodb.zip", zip_buf.getvalue(), content_type="application/zip")
                resp = self.client.post("/api/backups/upload", {"file": uploaded})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])
        self.assertIn("پایگاه‌داده (.db) نیست", resp.json()["error"])

    def test_upload_plain_db_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_db = os.path.join(tmp, "plain.db")
            _make_db(tmp_db)
            with open(tmp_db, "rb") as f:
                db_bytes = f.read()
            with _patched(tmp) as p:
                uploaded = SimpleUploadedFile(
                    "plain.db", db_bytes, content_type="application/octet-stream")
                resp = self.client.post("/api/backups/upload", {"file": uploaded})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"], resp.json())
        self.assertEqual(resp.json()["name"], "plain.db")

