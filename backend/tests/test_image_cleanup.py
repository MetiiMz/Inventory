# -*- coding: utf-8 -*-
"""Orphan image cleanup — runs on a temp DB + temp IMG_DIR, never touches db/."""

import os
import tempfile
import time
from unittest import mock

from django.test import TestCase
from django.test.client import Client

from inventory import dbhelpers
from inventory.models import Product, Repair, Tracking, Setting
import inventory.api.services.uploads as uploads_mod


class OrphanImageCleanupTests(TestCase):
    """cleanup_orphan_images + POST /api/images/cleanup on throwaway paths."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.img_dir = os.path.join(self.tmp.name, "images")
        os.makedirs(self.img_dir)
        self.client = Client()

    def tearDown(self):
        self.tmp.cleanup()

    def _patch_img_dir(self):
        """Point cleanup_orphan_images (and the endpoint) at the temp IMG_DIR."""
        return mock.patch.object(uploads_mod, "IMG_DIR", self.img_dir)

    def _mtime(self, name, seconds_ago):
        path = os.path.join(self.img_dir, name)
        old = time.time() - seconds_ago
        os.utime(path, (old, old))

    def _mtime_path(self, path, seconds_ago):
        old = time.time() - seconds_ago
        os.utime(path, (old, old))
        return path

    def test_referenced_image_kept(self):
        Product.objects.create(
            name="Ref", office_code="OF-R1", website_code="WS-R1",
            purchase_price=1, purchase_date="2026-01-01", image="ref.png",
        )
        with open(os.path.join(self.img_dir, "ref.png"), "wb") as f:
            f.write(b"x")
        self._mtime("ref.png", 7200)  # older than threshold but referenced
        with self._patch_img_dir():
            removed = uploads_mod.cleanup_orphan_images()
        self.assertEqual(removed, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.img_dir, "ref.png")))

    def test_site_icon_kept(self):
        Setting.objects.update_or_create(
            key="site_icon", defaults={"value": "icon.png"})
        with open(os.path.join(self.img_dir, "icon.png"), "wb") as f:
            f.write(b"x")
        self._mtime("icon.png", 7200)
        with self._patch_img_dir():
            removed = uploads_mod.cleanup_orphan_images()
        self.assertEqual(removed, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.img_dir, "icon.png")))

    def test_unreferenced_old_file_removed(self):
        with open(os.path.join(self.img_dir, "orphan.jpg"), "wb") as f:
            f.write(b"x")
        self._mtime("orphan.jpg", 7200)  # older than 3600 s
        with self._patch_img_dir():
            removed = uploads_mod.cleanup_orphan_images()
        self.assertEqual(removed, 1)
        self.assertFalse(os.path.exists(os.path.join(self.img_dir, "orphan.jpg")))

    def test_unreferenced_new_file_kept(self):
        with open(os.path.join(self.img_dir, "fresh.png"), "wb") as f:
            f.write(b"x")
        self._mtime("fresh.png", 60)  # newer than 3600 s
        with self._patch_img_dir():
            removed = uploads_mod.cleanup_orphan_images()
        self.assertEqual(removed, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.img_dir, "fresh.png")))

    def test_subdirectories_and_symlinks_untouched(self):
        Product.objects.create(
            name="Ref", office_code="OF-SD", website_code="WS-SD",
            purchase_price=1, purchase_date="2026-01-01", image="ref.png",
        )
        sub = os.path.join(self.img_dir, "subdir")
        os.makedirs(sub)
        deep = os.path.join(sub, "deep.jpg")
        with open(deep, "wb") as f:
            f.write(b"x")
        self._mtime_path(deep, 7200)
        with open(os.path.join(self.img_dir, "ref.png"), "wb") as f:
            f.write(b"x")
        link = os.path.join(self.img_dir, "link.png")
        os.symlink(os.path.join(self.img_dir, "ref.png"), link)
        self._mtime("link.png", 7200)
        with self._patch_img_dir():
            removed = uploads_mod.cleanup_orphan_images()
        self.assertEqual(removed, 0)
        self.assertTrue(os.path.isfile(os.path.join(sub, "deep.jpg")))
        self.assertTrue(os.path.islink(link))

    def test_odd_names_handled(self):
        for name in ("weird file name.png", "UPPER.PNG", "a.b.c.jpg", "شات.jpg"):
            with open(os.path.join(self.img_dir, name), "wb") as f:
                f.write(b"x")
            self._mtime(name, 7200)
        with self._patch_img_dir():
            removed = uploads_mod.cleanup_orphan_images()
        self.assertEqual(removed, 4)
        for name in ("weird file name.png", "UPPER.PNG", "a.b.c.jpg", "شات.jpg"):
            self.assertFalse(os.path.exists(os.path.join(self.img_dir, name)))

    def test_endpoint_get_405_post_removed(self):
        with open(os.path.join(self.img_dir, "orphan.jpg"), "wb") as f:
            f.write(b"x")
        self._mtime("orphan.jpg", 7200)
        with self._patch_img_dir():
            resp = self.client.get("/api/images/cleanup")
            self.assertEqual(resp.status_code, 405, resp.content)
            resp = self.client.post(
                "/api/images/cleanup", {}, content_type="application/json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()["ok"])
        self.assertEqual(resp.json()["removed"], 1)
        self.assertFalse(os.path.exists(os.path.join(self.img_dir, "orphan.jpg")))
