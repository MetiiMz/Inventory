# -*- coding: utf-8 -*-
"""Backup images: backups carry IMG_DIR files, restore brings them back.

All of these run on a *temp* sqlite file and a *temp* IMG_DIR — the real
``db/`` is never touched. ``dbhelpers``' import-time path constants
(``DB_PATH``/``IMG_DIR``/``BACKUP_DIR``) are patched to throwaway locations,
same technique as ``tests/test_dbhelpers_reports.py``.
"""

import os
import tempfile
import zipfile
from unittest import mock

from django.test import TestCase

from inventory import dbhelpers
from inventory.models import Setting


class BackupImageTests(TestCase):
    """backup_db / restore_db / delete_backup with the ``.images.zip`` sidecar."""

    def _paths(self, tmp):
        return (
            os.path.join(tmp, "t.sqlite3"),
            os.path.join(tmp, "images"),
            os.path.join(tmp, "backups"),
        )

    def _patch(self, db_path, img_dir, backup_dir):
        return mock.patch.multiple(
            dbhelpers, DB_PATH=db_path, IMG_DIR=img_dir, BACKUP_DIR=backup_dir)

    def test_backup_zip_contains_images_flat_and_stored(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path, img_dir, backup_dir = self._paths(tmp)
            os.makedirs(os.path.join(img_dir, "subdir"))
            with open(os.path.join(img_dir, "a.png"), "wb") as f:
                f.write(b"PNG-A")
            with open(os.path.join(img_dir, "b.jpg"), "wb") as f:
                f.write(b"JPG-B")
            with open(os.path.join(img_dir, "subdir", "c.png"), "wb") as f:
                f.write(b"SHOULD-NOT-BE-ZIPPED")
            with self._patch(db_path, img_dir, backup_dir):
                target = dbhelpers.backup_db()
            zip_path = os.path.splitext(target)[0] + ".images.zip"
            self.assertTrue(os.path.isfile(zip_path))
            with zipfile.ZipFile(zip_path) as zf:
                # flat names only, no directories
                self.assertEqual(sorted(zf.namelist()), ["a.png", "b.jpg"])
                for info in zf.infolist():
                    self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                    self.assertFalse(info.is_dir())
                self.assertEqual(zf.read("a.png"), b"PNG-A")
                self.assertEqual(zf.read("b.jpg"), b"JPG-B")

    def test_backup_empty_or_missing_img_dir_gives_empty_zip(self):
        for kind in ("empty", "missing"):
            with tempfile.TemporaryDirectory() as tmp:
                db_path, img_dir, backup_dir = self._paths(tmp)
                if kind == "empty":
                    os.makedirs(img_dir)
                # "missing": IMG_DIR is never created
                with self._patch(db_path, img_dir, backup_dir):
                    target = dbhelpers.backup_db()
                zip_path = os.path.splitext(target)[0] + ".images.zip"
                self.assertTrue(os.path.isfile(zip_path), kind)
                with zipfile.ZipFile(zip_path) as zf:
                    self.assertEqual(zf.namelist(), [], kind)

    def test_list_backups_ignores_images_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path, img_dir, backup_dir = self._paths(tmp)
            os.makedirs(img_dir)
            with open(os.path.join(img_dir, "x.png"), "wb") as f:
                f.write(b"x")
            with self._patch(db_path, img_dir, backup_dir):
                target = dbhelpers.backup_db()
                listed = [n["name"] for n in dbhelpers.list_backups()]
            self.assertIn(os.path.basename(target), listed)
            self.assertFalse(
                any(n.endswith(".images.zip") for n in listed), listed)


    def test_clear_then_restore_brings_images_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path, img_dir, backup_dir = self._paths(tmp)
            os.makedirs(img_dir)
            with open(os.path.join(img_dir, "keep.png"), "wb") as f:
                f.write(b"keep")
            with open(os.path.join(img_dir, "gone.jpg"), "wb") as f:
                f.write(b"gone")
            with self._patch(db_path, img_dir, backup_dir):
                dbhelpers.set_setting("site_icon", "keep.png")
                dbhelpers.clear_database()
                self.assertEqual(os.listdir(img_dir), ["keep.png"])
                # pre_clear also writes a .images.zip sidecar: pick the .db
                pres = [n for n in os.listdir(backup_dir)
                        if n.startswith("pre_clear_") and n.endswith(".db")]
                self.assertEqual(len(pres), 1, os.listdir(backup_dir))
                good, err = dbhelpers.restore_db(pres[0])
                self.assertTrue(good, err)
                # clear_database wiped "gone.jpg"; the pre_clear backup had
                # zipped it before the wipe, so restore brings it back while
                # keeping the site icon that existed at restore time
                self.assertEqual(
                    sorted(os.listdir(img_dir)), ["gone.jpg", "keep.png"])

    def test_restore_keeps_existing_files_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path, img_dir, backup_dir = self._paths(tmp)
            os.makedirs(img_dir)
            with open(os.path.join(img_dir, "keep.png"), "wb") as f:
                f.write(b"current")
            with self._patch(db_path, img_dir, backup_dir):
                target = dbhelpers.backup_db()
                zip_path = os.path.splitext(target)[0] + ".images.zip"
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
                    zf.writestr("keep.png", b"from-backup")
                    zf.writestr("new.png", b"new")
                good, err = dbhelpers.restore_db(os.path.basename(target))
            self.assertTrue(good, err)
            with open(os.path.join(img_dir, "keep.png"), "rb") as f:
                self.assertEqual(f.read(), b"current")  # existing kept
            with open(os.path.join(img_dir, "new.png"), "rb") as f:
                self.assertEqual(f.read(), b"new")      # new one restored

    def test_restore_old_backup_without_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path, img_dir, backup_dir = self._paths(tmp)
            os.makedirs(img_dir)
            with open(os.path.join(img_dir, "surprise.jpg"), "wb") as f:
                f.write(b"s")
            with self._patch(db_path, img_dir, backup_dir):
                target = dbhelpers.backup_db()
                os.remove(os.path.splitext(target)[0] + ".images.zip")
                good, err = dbhelpers.restore_db(os.path.basename(target))
                self.assertTrue(good, err)
            self.assertTrue(
                os.path.isfile(os.path.join(img_dir, "surprise.jpg")))

    def test_restore_ignores_malicious_zip_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path, img_dir, backup_dir = self._paths(tmp)
            os.makedirs(img_dir)
            with self._patch(db_path, img_dir, backup_dir):
                target = dbhelpers.backup_db()
                zip_path = os.path.splitext(target)[0] + ".images.zip"
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
                    zf.writestr("safe.png", b"safe")
                    zf.writestr("../x", b"evil-parent")
                    zf.writestr("/etc/x", b"evil-abs")
                    zf.writestr("sub/y.png", b"evil-subdir")
                good, err = dbhelpers.restore_db(os.path.basename(target))
            self.assertTrue(good, err)
            self.assertEqual(os.listdir(img_dir), ["safe.png"])
            self.assertFalse(os.path.exists("/etc/x"))
            self.assertFalse(os.path.exists(os.path.join(tmp, "x")))

    def test_delete_backup_removes_images_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path, img_dir, backup_dir = self._paths(tmp)
            os.makedirs(img_dir)
            with open(os.path.join(img_dir, "x.png"), "wb") as f:
                f.write(b"x")
            with self._patch(db_path, img_dir, backup_dir):
                target = dbhelpers.backup_db()
                zip_path = os.path.splitext(target)[0] + ".images.zip"
                self.assertTrue(os.path.isfile(zip_path))
                good, err = dbhelpers.delete_backup(os.path.basename(target))
                self.assertTrue(good)
                self.assertFalse(os.path.exists(target))
                self.assertFalse(os.path.exists(zip_path))
                self.assertEqual(dbhelpers.list_backups(), [])