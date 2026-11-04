# -*- coding: utf-8 -*-
"""Image upload hardening: no SVGs, content-signature verification, safe serving.

All tests run on a *temp* IMG_DIR (override_settings) — never the real
db/images. Pillow is not installed, so real images are built from minimal
valid file signatures instead of an image library.
"""

import base64
import json
import os
import tempfile

from django.test import TestCase, override_settings

JSON_TYPE = "application/json"

# Minimal valid image signatures (Pillow not installed).
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
JPEG = b"\xff\xd8\xff\x00"
GIF = b"GIF89a\x01\x00"
WEBP = b"RIFF\x00\x00\x00\x00WEBP"
AVIF = b"\x00\x00\x00\x20ftypavif"
ICO = b"\x00\x00\x01\x00" + b"\x00" * 6
SVG = b"<svg xmlns='http://www.w3.org/2000/svg'><rect width='10' height='10'/></svg>"
TEXT = b"this is not an image, just text"


def _b64(data):
    return base64.b64encode(data).decode()


class ImageHardeningTests(TestCase):
    """Upload validation + /data/images/ serving on a throwaway IMG_DIR."""

    def post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload),
                                content_type=JSON_TYPE)

    def test_svg_image_rejected_400_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(IMG_DIR=tmp):
                r = self.post_json("/api/upload", {
                    "kind": "image", "name": "evil.svg",
                    "data": "data:image/svg+xml;base64," + _b64(SVG)})
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn("فرمت فایل پشتیبانی نمی‌شود", r.json()["error"])
                self.assertFalse(os.path.exists(os.path.join(tmp, "evil.svg")))
                self.assertEqual(os.listdir(tmp), [])

    def test_svg_icon_rejected_400_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(IMG_DIR=tmp):
                r = self.post_json("/api/upload", {
                    "kind": "icon", "name": "logo.svg",
                    "data": _b64(SVG)})
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn("فرمت فایل پشتیبانی نمی‌شود", r.json()["error"])
                self.assertFalse(os.path.exists(os.path.join(tmp, "logo.svg")))
                self.assertEqual(os.listdir(tmp), [])

    def test_text_file_named_png_rejected_400_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(IMG_DIR=tmp):
                r = self.post_json("/api/upload", {
                    "kind": "image", "name": "x.png",
                    "data": _b64(TEXT)})
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn("تصویر معتبر نیست", r.json()["error"])
                self.assertFalse(os.path.exists(os.path.join(tmp, "x.png")))
                self.assertEqual(os.listdir(tmp), [])

    def test_multipart_text_file_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(IMG_DIR=tmp):
                r = self.client.post("/api/upload", {
                    "kind": "image",
                    "file": SimpleUploadedFile("t.png", TEXT),
                })
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn("تصویر معتبر نیست", r.json()["error"])
                self.assertEqual(os.listdir(tmp), [])

    def test_real_images_stored_200(self):
        cases = (("a.png", PNG), ("b.jpg", JPEG), ("c.gif", GIF),
                 ("d.webp", WEBP), ("e.avif", AVIF))
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(IMG_DIR=tmp):
                for name, sig in cases:
                    r = self.post_json("/api/upload", {
                        "kind": "image", "name": name,
                        "data": "data:image/png;base64," + _b64(sig)})
                    self.assertEqual(r.status_code, 200, (name, r.content))
                    ext = os.path.splitext(name)[1]
                    self.assertTrue(r.json()["path"].endswith(ext))
                    self.assertTrue(os.path.isfile(
                        os.path.join(tmp, r.json()["path"])))

    def test_real_png_via_multipart_stored(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(IMG_DIR=tmp):
                r = self.client.post("/api/upload", {
                    "kind": "image",
                    "file": SimpleUploadedFile("t.png", PNG),
                })
                self.assertEqual(r.status_code, 200, r.content)
                self.assertTrue(r.json()["path"].endswith(".png"))
                self.assertTrue(os.path.isfile(
                    os.path.join(tmp, r.json()["path"])))

    def test_old_svg_served_with_security_headers(self):
        """An SVG already sitting in IMG_DIR keeps being served, hardened."""
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "legacy.svg"), "wb") as f:
                f.write(SVG)
            with override_settings(IMG_DIR=tmp):
                r = self.client.get("/data/images/legacy.svg")
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
                csp = r.headers["Content-Security-Policy"]
                self.assertIn("default-src 'none'", csp)
                self.assertIn("sandbox", csp)
                self.assertIn("max-age", r.headers.get("Cache-Control", ""))

    def test_path_traversal_returns_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(IMG_DIR=tmp):
                r = self.client.get("/data/images/../escape.svg")
        self.assertEqual(r.status_code, 404)

    def test_nonexistent_returns_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(IMG_DIR=tmp):
                r = self.client.get("/data/images/nope.png")
        self.assertEqual(r.status_code, 404)

