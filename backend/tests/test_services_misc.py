# -*- coding: utf-8 -*-
"""Tests for calendar services, uploads and Excel export/import."""
import base64
import csv
import datetime
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from inventory.api import services
from inventory.api.services import ApiError
from inventory import excel_io
from inventory.jalali import gregorian_to_jalali
from inventory.models import Product, Repair, Sale
from inventory.utils import fa_money
from tests.helpers import make_product, sale_payload, today_iso


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
        # a same-day sale cell carries both the sale price and the purchase
        # price recorded at sale time (both feed the day-detail popup)
        Sale.objects.create(
            product=p, sale_price=150, purchase_price=100, profit=50,
            sale_date=self.mid, customer="x", customer_phone="09123456789")
        cell = next(c for c in services.calendar_month(self.jy, self.jm)["cells"]
                    if c and c["iso"] == self.mid)
        s_cell = cell["sales"][0]
        self.assertEqual(s_cell["price_display"], fa_money(150))
        self.assertEqual(s_cell["purchase_price_display"], fa_money(100))

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

    def test_sales_channels_validation(self):
        # same year-validation contract as monthly_activity (shared helper)
        year, months = services.sales_channels("1404")
        self.assertEqual(year, 1404)
        self.assertEqual(len(months), 12)
        year, months = services.sales_channels("")
        self.assertEqual(len(months), 12)
        _, err = call(services.sales_channels, "not-a-year")
        self.assertIn("نامعتبر", err.message)
        _, err = call(services.sales_channels, "99999")
        self.assertIn("بازه", err.message)

    def test_sales_channels_counts(self):
        # حضوری/آنلاین از sale_type، اعتباری از payment_type — ابعاد مستقل:
        # یک فروش آنلاینِ اعتباری در هر دو شمارنده می‌آید.
        # فروش‌ها در ماه جلالی جاری ثبت می‌شوند تا تست به تاریخ اجرا وابسته نباشد.
        iso = today_iso()
        today = datetime.date.fromisoformat(iso)
        jy, jm, _ = gregorian_to_jalali(today.year, today.month, today.day)
        p = make_product(purchase_date=iso)
        Sale.objects.create(
            product=p, sale_price=100, purchase_price=10, profit=90,
            sale_date=iso, customer="x", customer_phone="09123456789",
            sale_type="person", paid_cash=100, payment_type="cash")
        Sale.objects.create(
            product=p, sale_price=200, purchase_price=20, profit=180,
            sale_date=iso, customer="y", customer_phone="09123456788",
            sale_type="online", paid_cash=200, payment_type="cash")
        Sale.objects.create(
            product=p, sale_price=300, purchase_price=30, profit=270,
            sale_date=iso, customer="z", customer_phone="09123456787",
            sale_type="online", paid_cash=0, payment_type="credit",
            credit_provider="torob", is_settled=False)
        Sale.objects.create(
            product=p, sale_price=500, purchase_price=50, profit=450,
            sale_date=iso, customer="sn", customer_phone="09123456785",
            sale_type="person", paid_cash=500, payment_type="credit",
            credit_provider="snappay")
        Sale.objects.create(
            product=p, sale_price=600, purchase_price=60, profit=540,
            sale_date=iso, customer="dg", customer_phone="09123456784",
            sale_type="online", paid_cash=0, payment_type="credit",
            credit_provider="digipay")
        # credit with unknown/empty provider → only credit_count, no sub-row
        Sale.objects.create(
            product=p, sale_price=700, purchase_price=70, profit=630,
            sale_date=iso, customer="uk", customer_phone="09123456783",
            sale_type="person", paid_cash=700, payment_type="credit",
            credit_provider="")
        # unknown sale_type → not counted in person/online
        Sale.objects.create(
            product=p, sale_price=400, purchase_price=40, profit=360,
            sale_date=iso, customer="w", customer_phone="09123456786",
            sale_type="", paid_cash=400, payment_type="cash")
        _, months = services.sales_channels(str(jy))
        hit = next(m for m in months if m["jm"] == jm)
        self.assertEqual(hit["person_count"], 3)   # x + sn + uk
        self.assertEqual(hit["online_count"], 3)   # y + z + dg
        self.assertEqual(hit["credit_count"], 4)   # torob + snappay + digipay + empty
        self.assertEqual(hit["credit_snappay_count"], 1)
        self.assertEqual(hit["credit_digipay_count"], 1)
        self.assertEqual(hit["credit_torob_count"], 1)
        self.assertFalse(hit["future"])
        # every other month is zero — including the future ones of the current year
        others = [m for m in months if m["jm"] != jm]
        self.assertEqual(len(others), 11)
        for m in others:
            self.assertEqual(
                (m["person_count"], m["online_count"], m["credit_count"]),
                (0, 0, 0))


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


class ImportSoldProtectionTests(TestCase):
    """A6: an import file must not resurrect a sold watch."""

    HEADER = ["نام ساعت", "رفرنس", "کد انبار سایت", "کد دفتر فروشگاه",
              "برند", "قیمت خرید", "وضعیت",
              "تأمین‌کننده", "تاریخ خرید", "یادداشت"]

    def _import(self, *rows):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/import.csv"
            with open(path, "w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(self.HEADER)
                writer.writerows(rows)
            return excel_io.import_products(path)

    def test_file_saying_available_cannot_resurrect_sold_watch(self):
        p = make_product(office_code="OF-SOLD", website_code="WS-SOLD",
                         brand="OldBrand")
        services.create_sale(sale_payload(p.id))
        p.refresh_from_db()
        self.assertFalse(p.available)  # sold

        ok, stats, errors = self._import(
            ["Test Watch", "REF-S", "WS-SOLD", "OF-SOLD", "NewBrand",
             1200, "موجود", "sup", "1405/06/19", "edited"])
        self.assertTrue(ok, errors)
        self.assertEqual(stats["updated"], 1, errors)
        p.refresh_from_db()
        self.assertFalse(p.available)  # still sold — the fix
        # the rest of the row is really applied (it was an update, not skip)
        self.assertEqual(p.brand, "NewBrand")
        self.assertEqual(p.notes, "edited")

    def test_existing_lookup_is_case_insensitive(self):
        p = make_product(office_code="OF-CASE", website_code="WS-CASE")
        p.available = False
        p.save(update_fields=["available"])

        ok, stats, errors = self._import(
            ["Test Watch", "REF-C", "ws-case", "of-case", "",
             900, "موجود", "", "", ""])
        self.assertTrue(ok, errors)
        self.assertEqual(stats["updated"], 1, errors)
        self.assertEqual(stats["added"], 0)
        self.assertEqual(Product.objects.count(), 1)
        p.refresh_from_db()
        # the row matched case-insensitively and was updated in place
        self.assertEqual(p.office_code, "of-case")
        self.assertFalse(p.available)  # never touched on update

    def test_new_row_still_uses_file_status(self):
        ok, stats, errors = self._import(
            ["New Watch", "REF-N", "WS-NEW1", "OF-NEW1", "",
             900, "ناموجود", "", "", ""])
        self.assertTrue(ok, errors)
        self.assertEqual(stats["added"], 1)
        p = Product.objects.get(office_code="OF-NEW1")
        self.assertFalse(p.available)  # file status honoured for new rows


class ImportLegacyPurchaseTypeColumnTests(TestCase):
    """G1: «نوع خرید» is gone from products — but old files that still
    carry the column must import fine (extra columns are ignored)."""

    LEGACY_HEADER = ["نام ساعت", "رفرنس", "کد انبار سایت", "کد دفتر فروشگاه",
                     "برند", "قیمت خرید", "وضعیت",
                     "تأمین‌کننده", "تاریخ خرید", "نوع خرید", "یادداشت"]

    def _import(self, header, *rows):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/import.csv"
            with open(path, "w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(header)
                writer.writerows(rows)
            return excel_io.import_products(path)

    def test_legacy_file_with_purchase_type_column_imports(self):
        ok, stats, errors = self._import(
            self.LEGACY_HEADER,
            ["W1", "R1", "WS-G1", "OF-G1", "", 900,
             "موجود", "", "", "آنلاین", "legacy notes"])
        self.assertTrue(ok, errors)
        self.assertEqual(stats["added"], 1)
        p = Product.objects.get(office_code="OF-G1")
        self.assertEqual(p.name, "W1")
        self.assertEqual(p.notes, "legacy notes")
        self.assertEqual(list(errors), [])

    def test_legacy_file_update_ignores_purchase_type(self):
        # updating an existing product from an old-format file: the extra
        # column must not break the row (its value is just dropped)
        make_product(office_code="OF-GU", website_code="WS-GU")
        ok, stats, errors = self._import(
            self.LEGACY_HEADER,
            ["W2", "R2", "WS-GU", "OF-GU", "", 900,
             "موجود", "", "", "آنلاین", "edited"])
        self.assertTrue(ok, errors)
        self.assertEqual(stats["updated"], 1)
        p = Product.objects.get(office_code="OF-GU")
        self.assertEqual(p.notes, "edited")  # the update really happened
        self.assertEqual(list(errors), [])

    def test_export_has_no_purchase_type_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/products.csv"
            excel_io.export_products(path, "csv")
            with open(path, encoding="utf-8-sig") as fh:
                text = fh.read()
        self.assertNotIn("نوع خرید", text)
        header = text.splitlines()[0]
        self.assertNotIn("نوع", header.split(","))
