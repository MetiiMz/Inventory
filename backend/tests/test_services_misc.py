# -*- coding: utf-8 -*-
"""Tests for calendar services, uploads and Excel export/import."""
import base64
import datetime
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from inventory.api import services
from inventory.api.services import ApiError
from inventory.models import Product, Repair, Sale
from tests.helpers import make_product, today_iso


def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except ApiError as exc:
        return None, exc


class CalendarServiceTests(TestCase):
    """Month grid layout and day details."""

    def setUp(self):
        self.jy, self.jm = 1405, 6  # شهریور ۱۴۰۵
        self.mid = "2026-09-10"     # ۱۹ شهریور — inside the month

    def test_month_grid_shape(self):
        data = services.calendar_month(self.jy, self.jm)
        self.assertEqual(data["jy"], 1405)
        self.assertEqual(data["month_name"], "شهریور")
        self.assertEqual(len(data["cells"]), 35)  # week-aligned grid
        days = [c["day"] for c in data["cells"] if c]
        self.assertEqual(days, list(range(1, 32)))

    def test_month_events_are_bucketed(self):
        p = make_product(purchase_date=self.mid)
        data = services.calendar_month(self.jy, self.jm)
        cell = next(c for c in data["cells"] if c and c["iso"] == self.mid)
        self.assertEqual(cell["purchases"][0]["id"], p.id)
        self.assertEqual(cell["purchases"][0]["type"], "purchase")

    def test_invalid_month_falls_back_to_current(self):
        data = services.calendar_month(None, None)
        today = datetime.date.today()
        self.assertIn(data["jy"], (1404, 1405, 1406))
        self.assertTrue(data["cells"])

    def test_day_detail(self):
        p = make_product(purchase_date=self.mid)
        Sale.objects.create(
            product=p, sale_price=1, purchase_price=1, profit=0,
            sale_date=self.mid, customer="x", customer_phone="09123456789")
        Repair.objects.create(watch_name="W", customer_name="C",
                              delivery_date=self.mid, status="received")
        data = services.calendar_day(self.mid)
        self.assertEqual(data["date_iso"], self.mid)
        self.assertEqual(len(data["purchases"]), 1)
        self.assertEqual(len(data["sales"]), 1)
        self.assertEqual(len(data["repairs_in"]), 1)
        self.assertTrue(data["date_fa"])

    def test_day_requires_date(self):
        _, err = call(services.calendar_day, "")
        self.assertEqual(err.status_code, 400)

    def test_monthly_activity_validation(self):
        year, months = services.monthly_activity("1404")
        self.assertEqual(year, 1404)
        self.assertEqual(len(months), 12)
        year, months = services.monthly_activity(None)
        self.assertEqual(len(months), 12)
        _, err = call(services.monthly_activity, "not-a-year")
        self.assertIn("نامعتبر", err.message)
        _, err = call(services.monthly_activity, "99999")
        self.assertIn("بازه", err.message)

    def test_monthly_activity_sale_type_counts(self):
        # Spec-002 (US5): the chart gains in-person/online count series
        p = make_product(purchase_date="2026-09-01")
        Sale.objects.create(
            product=p, sale_price=100, purchase_price=10, profit=90,
            sale_date="2026-09-10", customer="x", customer_phone="09123456789",
            sale_type="person", paid_cash=100, payment_type="cash")
        Sale.objects.create(
            product=p, sale_price=200, purchase_price=20, profit=180,
            sale_date="2026-09-11", customer="y", customer_phone="09123456788",
            sale_type="online", paid_cash=200, payment_type="cash")
        _, months = services.monthly_activity("1405")
        hit = next((m for m in months if m["person_count"] or m["online_count"]), None)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["person_count"], 1)
        self.assertEqual(hit["online_count"], 1)
        self.assertEqual(hit["count"], 2)
        for m in months:
            if m is hit:
                continue
            self.assertEqual(m["person_count"], 0)
            self.assertEqual(m["online_count"], 0)


class UploadServiceTests(TestCase):
    """Image uploads via multipart and JSON/base64."""

    PNG = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGMAAQAA"
        "AAQAAQEAAwUAAA==")

    def test_multipart_upload(self):
        f = SimpleUploadedFile("t.png", self.PNG)
        r = self.client_post_file(f)
        self.assertTrue(r.endswith(".png"))

    def client_post_file(self, f):
        from django.test import RequestFactory
        req = RequestFactory().post("/api/upload", {"file": f, "kind": "image"})
        return services.save_upload(req)

    def test_json_base64_upload(self):
        from django.test import RequestFactory
        body = json_dumps({"kind": "image", "name": "x.png",
                           "data": "data:image/png;base64," +
                                   base64.b64encode(self.PNG).decode()})
        req = RequestFactory().post(
            "/api/upload", data=body, content_type="application/json")
        fname = services.save_upload(req)
        self.assertTrue(fname.endswith(".png"))

    def test_rejects_bad_ext_and_oversize(self):
        from django.test import RequestFactory
        req = RequestFactory().post(
            "/api/upload",
            data=json_dumps({"kind": "image", "name": "x.exe",
                             "data": base64.b64encode(b"bin").decode()}),
            content_type="application/json")
        _, err = call(services.save_upload, req)
        self.assertIn("فرمت", err.message)

        req = RequestFactory().post(
            "/api/upload",
            data=json_dumps({"kind": "image", "name": "x.png",
                             "data": base64.b64encode(b"z" * (2 * 1024 * 1024 + 1)).decode()}),
            content_type="application/json")
        _, err = call(services.save_upload, req)
        self.assertIn("مگابایت", err.message)

    def test_rejects_missing_file(self):
        from django.test import RequestFactory
        req = RequestFactory().post("/api/upload", data={})
        _, err = call(services.save_upload, req)
        self.assertIn("انتخاب نشده", err.message)


def json_dumps(data):
    import json
    return json.dumps(data)


class ExportImportTests(TestCase):
    """Excel/CSV export + the import template (real openpyxl round-trip)."""

    def test_export_valid_kind_and_fmt(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(DATA_DIR=tmp):
                path, name = services.export_data_file("products", "xlsx")
                self.assertTrue(name.startswith("products_"))
                self.assertTrue(path.endswith(".xlsx"))
                path, name = services.export_data_file("sales", "csv")
                self.assertTrue(path.endswith(".csv"))

    def test_export_invalid_kind(self):
        _, err = call(services.export_data_file, "hackers", "xlsx")
        self.assertEqual(err.status_code, 404)
        _, err = call(services.export_data_file, "products", "exe")
        self.assertEqual(err.status_code, 404)

    def test_import_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(DATA_DIR=tmp):
                path, name = services.import_template_file()
                self.assertTrue(name.endswith(".xlsx"))

    def test_import_rejects_non_excel(self):
        f = SimpleUploadedFile("virus.exe", b"nope")
        _, err = call(services.import_products_file, f)
        self.assertIn("csv یا xlsx", err.message)

    def test_import_valid_file(self):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        # legacy 11-column shape with the removed «قیمت فروش» column — the
        # importer must map by header and silently drop that column
        ws.append(["نام ساعت", "رفرنس", "کد انبار سایت", "کد دفتر فروشگاه",
                   "برند", "قیمت خرید", "قیمت فروش", "وضعیت",
                   "تأمین‌کننده", "تاریخ خرید", "یادداشت"])
        ws.append(["Test Import", "REF-1", "WS-IMP", "OF-IMP", "Brand",
                   1000, 3000, "موجود", "sup", "1405/06/19", "note"])
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = f"{tmp}/import.xlsx"
            wb.save(tmp_path)
            with override_settings(DATA_DIR=tmp):
                with open(tmp_path, "rb") as fh:
                    f = SimpleUploadedFile("import.xlsx", fh.read())
                    stats, errors = services.import_products_file(f)
        self.assertEqual(stats["added"], 1)
        p = Product.objects.get(reference="REF-1")
        self.assertEqual(p.purchase_price, 1000)
        self.assertEqual(p.notes, "note")
        # the legacy price column must not leak onto the product
        self.assertNotEqual(getattr(p, "sale_price", 0) or 0, 3000)
