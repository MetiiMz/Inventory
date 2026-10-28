# -*- coding: utf-8 -*-
"""A1 hardening tests.

* Detail endpoints (``/api/products/<id>`` … ``/api/payments/<id>``) accept
  only GET/PUT/DELETE — anything else answers ``405`` with the legacy
  error envelope and must NOT delete the record.
* :class:`inventory.middleware.SameOriginMiddleware` refuses state-changing
  requests whose ``Origin`` belongs to a different site (``403``), while the
  app's own same-origin calls keep working.
* ``ALLOWED_HOSTS`` is loopback-only plus the ``DJANGO_ALLOWED_HOSTS``
  env override.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import TestCase

from inventory.models import Payment, Product, Repair, Sale, Tracking
from tests.helpers import make_product, product_payload, sale_payload

JSON_TYPE = "application/json"

BACKEND_DIR = Path(__file__).resolve().parent.parent


class DetailMethodAllowListTests(TestCase):
    """Anything but GET/PUT/DELETE on a detail route → 405, row intact."""

    def _fixtures(self):
        """One row of each kind, created through the legacy API itself."""
        product = make_product()
        sale_id = self.client.post("/api/sales", sale_payload(product.id),
                                   content_type=JSON_TYPE).json()["sale"]["id"]
        repair_id = self.client.post("/api/repairs", {"watch_name": "ساعت"},
                                     content_type=JSON_TYPE).json()["repair"]["id"]
        tracking_id = self.client.post("/api/tracking", {"item_name": "قطعه"},
                                       content_type=JSON_TYPE).json()["tracking"]["id"]
        payment_id = self.client.post("/api/payments", {
            "product_name": "ساعت", "total_amount": "1000",
            "paid_amount": "100"}, content_type=JSON_TYPE).json()["payment"]["id"]
        return [
            (f"/api/products/{product.id}", Product, product.id),
            (f"/api/sales/{sale_id}", Sale, sale_id),
            (f"/api/repairs/{repair_id}", Repair, repair_id),
            (f"/api/tracking/{tracking_id}", Tracking, tracking_id),
            (f"/api/payments/{payment_id}", Payment, payment_id),
        ]

    def test_unsupported_methods_are_405_and_record_survives(self):
        for url, model, obj_id in self._fixtures():
            for method in ("head", "options", "post", "patch"):
                with self.subTest(url=url, method=method):
                    # head/options take no body (the client would treat
                    # ``data`` as query-string params)
                    kwargs = (
                        {"data": "{}", "content_type": JSON_TYPE}
                        if method in ("post", "patch") else {}
                    )
                    r = getattr(self.client, method)(url, **kwargs)
                    self.assertEqual(r.status_code, 405, f"{method} {url}")
                    if method != "head":  # HEAD answers without a body
                        body = r.json()
                        self.assertFalse(body["ok"])
                        self.assertEqual(body["error"], "متد پشتیبانی نمی‌شود")
                    self.assertTrue(
                        model.objects.filter(id=obj_id).exists(),
                        f"{method} {url} must not delete the record")

    def test_tracking_detail_get_and_delete_still_work(self):
        """Positive control — the re-wired DELETE branch must keep working."""
        tid = self.client.post("/api/tracking", {"item_name": "قطعه"},
                               content_type=JSON_TYPE).json()["tracking"]["id"]
        url = f"/api/tracking/{tid}"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(self.client.delete(url).json()["ok"])
        self.assertFalse(Tracking.objects.filter(id=tid).exists())


class SameOriginMiddlewareTests(TestCase):
    """Cross-origin state-changers → 403; the app's own calls keep working."""

    def _post(self, **extra):
        return self.client.post("/api/products", product_payload(),
                                content_type=JSON_TYPE, **extra)

    def test_cross_origin_post_is_403(self):
        r = self._post(HTTP_ORIGIN="http://evil.example")
        self.assertEqual(r.status_code, 403)
        body = r.json()
        self.assertFalse(body["ok"])
        self.assertTrue(body["error"])
        self.assertFalse(Product.objects.exists())

    def test_cross_origin_delete_is_403(self):
        product = make_product()
        r = self.client.delete(f"/api/products/{product.id}",
                               HTTP_ORIGIN="http://evil.example")
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Product.objects.filter(id=product.id).exists())

    def test_different_port_is_cross_origin(self):
        r = self._post(HTTP_ORIGIN="http://localhost:9000")
        self.assertEqual(r.status_code, 403)

    def test_null_origin_is_rejected(self):
        # sandboxed iframes / file:// pages send ``Origin: null``
        r = self._post(HTTP_ORIGIN="null")
        self.assertEqual(r.status_code, 403)

    def test_same_origin_post_passes(self):
        r = self._post(HTTP_ORIGIN="http://testserver")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    def test_real_world_localhost_pair_passes(self):
        """The app serves on localhost:8000 — its own pages must keep working."""
        r = self.client.post("/api/products", product_payload(),
                             content_type=JSON_TYPE,
                             HTTP_HOST="localhost:8000",
                             HTTP_ORIGIN="http://localhost:8000")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    def test_post_without_origin_passes(self):
        r = self._post()
        self.assertEqual(r.status_code, 200)

    def test_origin_ignored_on_safe_methods(self):
        r = self.client.get("/api/products", HTTP_ORIGIN="http://evil.example")
        self.assertEqual(r.status_code, 200)


class AllowedHostsSettingsTests(TestCase):
    """Loopback-only defaults, extendable via DJANGO_ALLOWED_HOSTS."""

    def test_defaults_are_loopback_only(self):
        self.assertNotIn("*", settings.ALLOWED_HOSTS)
        for host in ("127.0.0.1", "localhost", "[::1]"):
            self.assertIn(host, settings.ALLOWED_HOSTS)

    def test_env_var_extends_allowed_hosts(self):
        script = "\n".join([
            "import os",
            "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tikotime.settings')",
            "import django",
            "django.setup()",
            "from django.conf import settings",
            "print('|'.join(settings.ALLOWED_HOSTS))",
        ])
        env = dict(
            os.environ,
            DJANGO_ALLOWED_HOSTS="example.com, foo.bar",
            TIKOTIME_DB="/tmp/opencode/a1-envtest.sqlite3",
        )
        proc = subprocess.run(
            [sys.executable, "-c", script], cwd=str(BACKEND_DIR), env=env,
            capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        hosts = proc.stdout.strip().split("|")
        self.assertIn("example.com", hosts)
        self.assertIn("foo.bar", hosts)
        self.assertIn("localhost", hosts)
        self.assertNotIn("*", hosts)
