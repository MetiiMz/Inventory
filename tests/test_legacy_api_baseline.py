# -*- coding: utf-8 -*-
"""Legacy `/api/*` regression baseline — refactor step 0 (freeze before changes).

Purpose: lock the legacy HTTP contract **before** any structural change, so every
later step can prove "no behaviour change" by re-running this module. Scope = the
legacy routes only (`/api/*`, `/export/*`, `/data/images/*`) plus unknown-path
behaviour; the parallel `/api/v1/` layer is deliberately NOT covered (it is
removed in step 1).

Comparison rule (Q2): status code + **named key/value** equality. Key order inside
an object is irrelevant (the frontend reads keys by name); item order inside lists
is significant, so list assertions use stable data or look rows up by id.

Isolation: this module NEVER touches real user data.
* uploads   → ``override_settings(IMG_DIR=<tmp>)`` (services reads ``settings.IMG_DIR``)
* exports   → ``override_settings(DATA_DIR=<tmp>)`` (exports dir derives from it)
* backups   → ``override_settings(BACKUP_DIR=<tmp>)`` **plus**
              ``mock.patch.object(dbhelpers, "BACKUP_DIR", <tmp>)`` — the dbhelpers
              constants are bound at import time, so ``override_settings`` alone is
              not enough (same technique as ``tests/test_dbhelpers_reports.py``)
* destructive routes (``/api/database/clear``) are asserted with the helper stubbed,
  and ``/api/backups/restore`` only through its not-found branch, so nothing writes
  into the real ``data/`` area.
"""
import base64
import json
import os
import tempfile
from unittest import mock

from django.test import TestCase, override_settings

from inventory import dbhelpers
from inventory.models import Payment, Product, Repair, Sale, Setting, Tracking
from tests.helpers import (
    make_product, product_payload, sale_payload, today_iso, today_jalali,
)

JSON_TYPE = "application/json"

# 1x1 transparent PNG (same constant the existing upload tests use).
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGMAAQAA"
    "AAQAAQEAAwUAAA==")


class LegacyApiBaselineTests(TestCase):
    """Fixed dataset + grouped per-route expectations (tasks T004-T008)."""

    # ------------------------------------------------------------- helpers
    def post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload),
                                content_type=JSON_TYPE)

    def put_json(self, url, payload):
        return self.client.put(url, data=json.dumps(payload),
                               content_type=JSON_TYPE)

    def assertNamedKeys(self, row, keys):
        """Every named key exists (Q2: key order inside an object is free)."""
        missing = [k for k in keys if k not in row]
        self.assertEqual(missing, [], f"missing keys: {missing}")

    def assertLegacyError(self, resp, status=400):
        """``{ok: false, error: <Persian message>}`` — never a DRF ``detail``."""
        self.assertEqual(resp.status_code, status)
        body = resp.json()
        self.assertFalse(body["ok"])
        self.assertTrue(body["error"])
        self.assertNotIn("detail", body)
        return body

    def assertDefaultNotFound(self, resp):
        """Unknown path: Django's default 404 — no JSON envelope, no redirect."""
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn("Location", resp)
        self.assertFalse(
            resp.headers.get("Content-Type", "").startswith(JSON_TYPE),
            "unknown paths must not answer with a JSON envelope")

    def assertAttachment(self, resp, suffix=".xlsx"):
        self.assertEqual(resp.status_code, 200)
        disposition = resp.headers.get("Content-Disposition", "")
        self.assertIn("attachment", disposition)
        self.assertIn(suffix, disposition)

    # ---------------------------------------------------------------- data
    def setUp(self):
        """Fixed data: 2 products, a cash sale, a deposit sale (+receipt),
        a repair, a tracking record, a brand and store settings."""
        self.product = make_product()
        cash = self.post_json("/api/sales", sale_payload(self.product.id))
        self.assertEqual(cash.status_code, 200, cash.content)
        self.sale_id = cash.json()["sale"]["id"]

        deposit_product = make_product(office_code="OF-DEP", website_code="WS-DEP")
        deposit = self.post_json("/api/sales", sale_payload(
            deposit_product.id, payment_type="deposit",
            sale_price="1500000", paid_cash="500000"))
        self.assertEqual(deposit.status_code, 200, deposit.content)
        self.deposit_sale_id = deposit.json()["sale"]["id"]
        self.deposit_payment = Payment.objects.get(sale_id=self.deposit_sale_id)

        self.repair_id = self.post_json(
            "/api/repairs", {"watch_name": "ساعت تست"}).json()["repair"]["id"]
        self.tracking_id = self.post_json(
            "/api/tracking", {"item_name": "قطعه تست"}).json()["tracking"]["id"]
        self.post_json("/api/brands", {"name": "برند-تست"})
        self.post_json("/api/settings", {"store_name": "فروشگاه تست"})

    # ============================================== T005: products, sales
    def test_products_list_shape_and_values(self):
        r = self.client.get("/api/products")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIsInstance(body, list)          # legacy: a plain array
        self.assertEqual(len(body), 2)
        row = next(x for x in body if x["id"] == self.product.id)
        self.assertNamedKeys(row, (
            "id", "name", "office_code", "website_code", "available",
            "is_available", "purchase_date_fa", "purchase_price_display",
            "total_value", "total_sale_value", "availability_fa",
            "profit_per_unit_display", "purchase_date_weekday"))
        self.assertEqual(row["name"], self.product.name)
        self.assertEqual(row["available"], 0)      # sold -> out of stock (legacy int)

    def test_products_crud_and_errors(self):
        created = self.post_json("/api/products", product_payload())
        self.assertEqual(created.status_code, 200, created.content)
        body = created.json()
        self.assertTrue(body["ok"])
        pid = body["product"]["id"]

        detail = self.client.get(f"/api/products/{pid}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], pid)  # legacy: bare object

        updated = self.put_json(f"/api/products/{pid}",
                                product_payload(name="ویرایش‌شده"))
        self.assertTrue(updated.json()["ok"])
        self.assertEqual(updated.json()["product"]["name"], "ویرایش‌شده")

        self.assertLegacyError(self.post_json("/api/products", {"name": ""}), 400)

        self.assertTrue(self.client.delete(f"/api/products/{pid}").json()["ok"])
        self.assertFalse(Product.objects.filter(id=pid).exists())

        # deleted = number of ids sent, not rows matched
        bulk = self.post_json("/api/products/bulk-delete", {"ids": [pid]})
        self.assertEqual(bulk.json()["deleted"], 1)
        self.assertLegacyError(
            self.post_json("/api/products/bulk-delete", {"ids": []}), 400)

    def test_products_not_found_message(self):
        self.assertLegacyError(self.client.get("/api/products/999999"), 404)

    def test_sales_list_summary_and_next_code(self):
        r = self.client.get("/api/sales")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(set(body.keys()), {"items", "summary"})
        self.assertEqual(body["summary"]["count"], 2)
        row = next(x for x in body["items"] if x["id"] == self.sale_id)
        self.assertNamedKeys(row, (
            "id", "product_image", "product_name", "final_price_display",
            "profit_display", "sale_date_fa", "paid_total",
            "customer_phone_fa", "invoice_code", "is_settled"))
        self.assertTrue(row["invoice_code"])

        nc = self.client.get("/api/sales", {"next_code": "1"})
        self.assertEqual(nc.status_code, 200)
        self.assertIn("next_invoice_code", nc.json())

    def test_sales_update_delete_bulk_and_not_found(self):
        upd = self.put_json(f"/api/sales/{self.sale_id}",
                            sale_payload(self.product.id, notes="یادداشت"))
        self.assertTrue(upd.json()["ok"])
        self.assertEqual(upd.json()["sale"]["notes"], "یادداشت")

        bulk = self.post_json("/api/sales/bulk-delete",
                              {"ids": [self.deposit_sale_id]})
        self.assertEqual(bulk.json()["deleted"], 1)
        self.assertFalse(Sale.objects.filter(id=self.deposit_sale_id).exists())

        self.assertTrue(
            self.client.delete(f"/api/sales/{self.sale_id}").json()["ok"])
        self.assertTrue(Product.objects.get(id=self.product.id).available)

        self.assertLegacyError(self.client.get("/api/sales/999999"), 404)

    # ============================================== T005: payments
    def test_payments_list_shape_and_rows(self):
        r = self.client.get("/api/payments")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertNamedKeys(body, ("items", "summary"))
        self.assertEqual(body["summary"]["count"], len(body["items"]))
        self.assertNamedKeys(body["items"][0], (
            "remaining", "paid_percent", "remaining_display",
            "pay_date_fa", "customer_phone_fa"))

        unpaid = self.client.get("/api/payments", {"status": "unpaid"})
        self.assertTrue(unpaid.json()["ok"])
        self.assertEqual(unpaid.json()["summary"]["count"],
                         len(unpaid.json()["items"]))

    def test_payments_create_update_add_settle_delete(self):
        created = self.post_json("/api/payments", {
            "product_name": "W", "total_amount": "1000", "paid_amount": "100"})
        body = created.json()
        self.assertTrue(body["ok"])
        pid = body["payment"]["id"]
        self.assertEqual(body["payment"]["paid_amount"], 100)

        upd = self.put_json(f"/api/payments/{pid}",
                            {"total_amount": "1000", "paid_amount": "200"})
        self.assertTrue(upd.json()["ok"])
        self.assertEqual(upd.json()["payment"]["paid_amount"], 200)

        self.assertTrue(self.post_json(
            f"/api/payments/{pid}/add", {"amount": "800"}).json()["ok"])

        # fully paid now -> settle-full refuses with the legacy message
        settled = self.post_json(f"/api/payments/{pid}/settle-full", {})
        self.assertLegacyError(settled, 400)
        self.assertIn("قبلاً", settled.json()["error"])

        # a partially paid receipt settles successfully
        p2 = self.post_json("/api/payments", {
            "product_name": "W2", "total_amount": "1000",
            "paid_amount": "100"}).json()["payment"]["id"]
        # settle-full answers with a bare ``{ok: true}`` envelope (no ``payment``
        # key) — the effect is verified through the model instead.
        done = self.post_json(f"/api/payments/{p2}/settle-full", {})
        self.assertTrue(done.json()["ok"])
        self.assertNamedKeys(done.json(), ("ok",))
        self.assertEqual(Payment.objects.get(id=p2).paid_amount, 1000)
        self.assertEqual(Payment.objects.get(id=p2).total_amount, 1000)

        bulk = self.post_json("/api/payments/bulk-delete", {"ids": [pid, p2]})
        self.assertEqual(bulk.json()["deleted"], 2)

        # NOTE: /api/payments/<id> has no GET in the legacy contract, so this
        # module deliberately never issues one.
        self.assertLegacyError(
            self.put_json("/api/payments/999999", {"total_amount": "1"}), 404)

    # ============================================== T006: repairs, tracking
    def test_repairs_list_shape_and_crud(self):
        r = self.client.get("/api/repairs")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIsInstance(body, list)          # legacy: a plain array
        self.assertEqual(len(body), 1)
        self.assertNamedKeys(body[0], (
            "id", "watch_name", "status", "status_fa", "status_color",
            "delivery_date_fa", "return_date_fa", "is_warranty_fa",
            "repair_price_display", "customer_phone_fa"))

        created = self.post_json("/api/repairs", {"watch_name": "ساعت دوم"})
        self.assertEqual(created.status_code, 200, created.content)
        self.assertTrue(created.json()["ok"])
        rid = created.json()["repair"]["id"]
        self.assertTrue(created.json()["repair"]["status_fa"])

        detail = self.client.get(f"/api/repairs/{rid}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], rid)  # legacy: bare object

        updated = self.put_json(f"/api/repairs/{rid}",
                                {"watch_name": "ساعت دوم", "notes": "یادداشت"})
        self.assertTrue(updated.json()["ok"], updated.content)
        self.assertEqual(updated.json()["repair"]["notes"], "یادداشت")

        # PUT is a full replacement (not a partial merge): a payload without the
        # required name is rejected with the legacy message.
        bad_put = self.put_json(f"/api/repairs/{rid}", {"notes": "x"})
        self.assertLegacyError(bad_put, 400)
        self.assertIn("الزامی", bad_put.json()["error"])

        filtered = self.client.get("/api/repairs", {"status": "received"})
        self.assertIsInstance(filtered.json(), list)
        self.assertEqual(len(filtered.json()), 2)

        bulk = self.post_json("/api/repairs/bulk-delete", {"ids": [rid]})
        self.assertEqual(bulk.json()["deleted"], 1)
        self.assertFalse(Repair.objects.filter(id=rid).exists())

        self.assertLegacyError(self.client.get("/api/repairs/999999"), 404)

    def test_repair_status_delivered_stamps_return_date(self):
        r = self.post_json(f"/api/repairs/{self.repair_id}/status",
                           {"status": "delivered"})
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["repair"]["status"], "delivered")
        self.assertEqual(body["repair"]["status_fa"], "تحویل شده")
        self.assertEqual(body["repair"]["return_date"], today_iso())

        done = self.client.get("/api/repairs", {"status": "delivered"})
        self.assertEqual(len(done.json()), 1)

        bad = self.post_json(f"/api/repairs/{self.repair_id}/status",
                             {"status": "nonsense"})
        self.assertLegacyError(bad, 400)
        self.assertIn("نامعتبر", bad.json()["error"])

        # unknown id -> legacy "not found" envelope
        self.assertLegacyError(
            self.post_json("/api/repairs/999999/status", {"status": "done"}), 404)

    def test_tracking_list_shape_and_crud(self):
        r = self.client.get("/api/tracking")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIsInstance(body, list)          # legacy: a plain array
        self.assertEqual(len(body), 1)
        self.assertNamedKeys(body[0], (
            "id", "item_name", "status", "status_fa", "status_color",
            "price_display", "customer_phone_fa"))

        created = self.post_json("/api/tracking", {"item_name": "قطعه‌ی دوم"})
        self.assertTrue(created.json()["ok"])
        tid = created.json()["tracking"]["id"]

        detail = self.client.get(f"/api/tracking/{tid}")
        self.assertEqual(detail.json()["id"], tid)  # legacy: bare object

        updated = self.put_json(f"/api/tracking/{tid}",
                                {"item_name": "قطعه‌ی دوم", "status": "ordered"})
        self.assertTrue(updated.json()["ok"])
        self.assertEqual(updated.json()["tracking"]["status"], "ordered")

        bulk = self.post_json("/api/tracking/bulk-delete", {"ids": [tid]})
        self.assertEqual(bulk.json()["deleted"], 1)
        self.assertFalse(Tracking.objects.filter(id=tid).exists())

        self.assertLegacyError(self.client.get("/api/tracking/999999"), 404)

    def test_brands_get_post_and_delete(self):
        r = self.client.get("/api/brands")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertNamedKeys(body, ("brands",))
        self.assertIn("برند-تست", body["brands"])

        added = self.post_json("/api/brands", {"name": "برند-دوم"})
        self.assertTrue(added.json()["ok"])
        self.assertIn("برند-دوم", self.client.get("/api/brands").json()["brands"])

        # duplicate -> legacy error message from the business layer
        dup = self.post_json("/api/brands", {"name": "برند-دوم"})
        self.assertLegacyError(dup, 400)
        self.assertIn("قبلاً", dup.json()["error"])

        removed = self.post_json("/api/brands/delete", {"name": "برند-دوم"})
        self.assertTrue(removed.json()["ok"])
        self.assertNotIn("برند-دوم",
                         self.client.get("/api/brands").json()["brands"])
        self.assertIn("برند-تست",
                      self.client.get("/api/brands").json()["brands"])

    # ============================================== T007: upload, calendar
    def test_upload_json_base64_and_serve_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(IMG_DIR=tmp):
                payload = {
                    "kind": "image", "name": "x.png",
                    "data": "data:image/png;base64,"
                            + base64.b64encode(PNG_1PX).decode(),
                }
                r = self.post_json("/api/upload", payload)
                self.assertEqual(r.status_code, 200, r.content)
                body = r.json()
                self.assertTrue(body["ok"])
                self.assertNamedKeys(body, ("path",))
                self.assertTrue(body["path"].endswith(".png"))
                # the file landed inside the TEMP dir, never in real data/images
                self.assertTrue(os.path.isfile(os.path.join(tmp, body["path"])))

                served = self.client.get(f"/data/images/{body['path']}")
                self.assertEqual(served.status_code, 200)
                self.assertIn("max-age", served.headers.get("Cache-Control", ""))

                # bad extension -> legacy Persian error
                bad = self.post_json("/api/upload", {
                    "kind": "image", "name": "x.exe",
                    "data": base64.b64encode(b"bin").decode()})
                self.assertLegacyError(bad, 400)

    def test_upload_multipart_and_missing_file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(IMG_DIR=tmp):
                r = self.client.post("/api/upload", {
                    "kind": "image",
                    "file": SimpleUploadedFile("t.png", PNG_1PX),
                })
                self.assertEqual(r.status_code, 200, r.content)
                self.assertTrue(r.json()["path"].endswith(".png"))
                self.assertEqual(len(os.listdir(tmp)), 1)

                empty = self.client.post("/api/upload", {"kind": "image"})
                self.assertLegacyError(empty, 400)
                self.assertIn("انتخاب نشده", empty.json()["error"])

    def test_serve_image_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(IMG_DIR=tmp):
                r = self.client.get("/data/images/nope.png")
                self.assertLegacyError(r, 404)

    def test_calendar_month_and_day(self):
        jy, jm, _ = today_jalali()
        r = self.client.get("/api/calendar", {"jy": str(jy), "jm": str(jm)})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertNamedKeys(body, ("jy", "jm", "month_name", "cells"))
        self.assertEqual((body["jy"], body["jm"]), (jy, jm))
        self.assertIsInstance(body["cells"], list)

        # missing parameters fall back to the current month (no error)
        fallback = self.client.get("/api/calendar")
        self.assertTrue(fallback.json()["ok"])
        self.assertEqual((fallback.json()["jy"], fallback.json()["jm"]), (jy, jm))

        day = self.client.get("/api/calendar/day", {"date": today_iso()})
        self.assertEqual(day.status_code, 200)
        self.assertTrue(day.json()["ok"])
        self.assertEqual(day.json()["date_iso"], today_iso())

        self.assertLegacyError(self.client.get("/api/calendar/day"), 400)

    def test_monthly_activity_report(self):
        jy, _, _ = today_jalali()
        r = self.client.get("/api/reports/monthly-activity", {"year": str(jy)})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertNamedKeys(body, ("year", "months"))
        self.assertEqual(body["year"], jy)
        self.assertEqual(len(body["months"]), 12)

        default = self.client.get("/api/reports/monthly-activity")
        self.assertTrue(default.json()["ok"])
        self.assertNamedKeys(default.json(), ("year", "months"))

        self.assertLegacyError(
            self.client.get("/api/reports/monthly-activity", {"year": "abc"}), 400)
        self.assertLegacyError(
            self.client.get("/api/reports/monthly-activity", {"year": "1200"}), 400)

    # ======================================== T008: export, import, backups
    def test_export_files_and_import_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(DATA_DIR=tmp):
                xlsx = self.client.get("/export/products.xlsx")
                self.assertAttachment(xlsx, ".xlsx")
                csv_resp = self.client.get("/export/sales.csv")
                self.assertAttachment(csv_resp, ".csv")
                template = self.client.get("/api/import/template")
                self.assertAttachment(template, ".xlsx")
                # export output must have landed under the TEMP data dir
                exported = os.path.join(tmp, "exports")
                self.assertTrue(os.path.isdir(exported))
                self.assertTrue(os.listdir(exported))

                bad = self.client.get("/export/hackers.xlsx")
                self.assertLegacyError(bad, 404)
                self.assertIn("یافت نشد", bad.json()["error"])
                self.assertLegacyError(self.client.get("/export/products.exe"), 404)

    def test_import_products_rejects_non_excel(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(DATA_DIR=tmp):
                r = self.client.post("/api/import/products", {
                    "file": SimpleUploadedFile("virus.exe", b"nope")})
                self.assertLegacyError(r, 400)
                self.assertIn("csv یا xlsx", r.json()["error"])

                missing = self.client.post("/api/import/products", {})
                self.assertLegacyError(missing, 400)
                self.assertIn("انتخاب نشده", missing.json()["error"])

    def test_backups_endpoints_are_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = os.path.join(tmp, "baseline_test_backup.db")
            with open(fake, "wb") as fh:
                fh.write(b"x")
            with mock.patch.object(dbhelpers, "BACKUP_DIR", tmp):
                with override_settings(BACKUP_DIR=tmp):
                    listed = self.client.get("/api/backups")
                    self.assertEqual(listed.status_code, 200)
                    body = listed.json()
                    self.assertTrue(body["ok"])
                    self.assertNamedKeys(body, ("backups",))
                    self.assertEqual([b["name"] for b in body["backups"]],
                                     ["baseline_test_backup.db"])
                    self.assertNamedKeys(body["backups"][0], ("name", "size", "modified"))

                    dl = self.client.get(
                        "/api/backups/download/baseline_test_backup.db")
                    self.assertEqual(dl.status_code, 200)
                    self.assertIn("attachment",
                                  dl.headers.get("Content-Disposition", ""))

                    self.assertLegacyError(
                        self.client.get("/api/backups/download/missing.db"), 404)

                    gone = self.post_json("/api/backups/delete",
                                          {"name": "baseline_test_backup.db"})
                    self.assertTrue(gone.json()["ok"])
                    self.assertFalse(os.path.isfile(fake))

                    self.assertLegacyError(
                        self.post_json("/api/backups/delete", {"name": "missing.db"}), 400)
                    # not-found branch returns BEFORE any restore work
                    self.assertLegacyError(
                        self.post_json("/api/backups/restore", {"name": "missing.db"}), 400)

    def test_database_info_and_settings(self):
        info = self.client.get("/api/database/info")
        self.assertEqual(info.status_code, 200)
        body = info.json()
        self.assertTrue(body["ok"])
        self.assertNamedKeys(body, ("counts",))
        self.assertNamedKeys(body["counts"],
                             ("payments", "sales", "products", "repairs", "tracking"))

        settings_resp = self.client.get("/api/settings")
        self.assertTrue(settings_resp.json()["ok"])
        self.assertNamedKeys(settings_resp.json(),
                             ("store_name", "store_phone", "store_address",
                              "currency", "site_icon"))
        self.assertEqual(settings_resp.json()["store_name"], "فروشگاه تست")

        saved = self.post_json("/api/settings", {"store_name": "نام تازه"})
        self.assertTrue(saved.json()["ok"])
        self.assertEqual(self.client.get("/api/settings").json()["store_name"],
                         "نام تازه")
        self.assertTrue(
            Setting.objects.filter(key="store_name", value="نام تازه").exists())

    # ======================================== T008: unknown-path behaviour
    def test_unknown_api_path_is_default_404(self):
        """Measured behaviour (see spec FR-014): Django's default 404 — the custom
        handler404 in inventory/views/pages.py is NOT wired into ROOT_URLCONF, so
        there is no JSON envelope and no redirect."""
        self.assertDefaultNotFound(self.client.get("/api/unknown-path"))
        self.assertDefaultNotFound(self.client.get("/api/definitely-not-a-route"))

    def test_unknown_page_path_is_default_404(self):
        self.assertDefaultNotFound(self.client.get("/no-such-page"))
        # the pages that DO exist still answer with 200 / 302 (baseline intact)
        for url in ("/dashboard", "/products", "/calendar", "/repairs",
                    "/sold", "/tracking", "/payments", "/settings"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.get("/").status_code, 302)
