# -*- coding: utf-8 -*-
"""Tests for inventory.utils — formatters, parsers and the dict serializers."""
import datetime

from django.test import TestCase

from inventory import utils
from inventory.models import Payment, Repair, Sale, Tracking
from tests.helpers import make_product, today_iso


class FormattingTests(TestCase):
    """fa_date / fa_money / number parsing helpers."""

    def test_fa_date_formats_with_persian_digits(self):
        self.assertEqual(utils.fa_date("2026-09-10"), "۱۴۰۵/۰۶/۱۹")

    def test_fa_date_weekday_prefix(self):
        out = utils.fa_date("2026-09-10", with_weekday=True)
        self.assertTrue(out.endswith("۱۹ شهریور ۱۴۰۵"), out)

    def test_fa_date_empty_and_garbage(self):
        self.assertEqual(utils.fa_date(""), "")
        self.assertEqual(utils.fa_date("not-a-date"), "not-a-date")

    def test_fa_money_groups_and_persian_digits(self):
        self.assertEqual(utils.fa_money(1234567), "۱٬۲۳۴٬۵۶۷")
        self.assertEqual(utils.fa_money(0), "۰")
        self.assertEqual(utils.fa_money(None), "۰")
        self.assertEqual(utils.fa_money("12.6"), "۱۳")

    def test_clean_strips(self):
        self.assertEqual(utils.clean("  x  "), "x")
        self.assertEqual(utils.clean(None), "")

    def test_to_int_and_to_float_tolerant(self):
        self.assertEqual(utils.to_int("۱٬۰۰۰"), 1000)
        self.assertEqual(utils.to_int("abc", 7), 7)
        self.assertEqual(utils.to_float("۲٬۵۰۰.۵"), 2500.5)
        self.assertEqual(utils.to_float(None), 0.0)

    def test_phone_and_digit_normalization(self):
        self.assertEqual(utils.to_en_digits("۰۹۱۲"), "0912")
        # to_en_phone only translates digits; spaces are stripped by callers
        self.assertEqual(utils.to_en_phone(" ۰۹۱۲ ۳۴ "), "0912 34")
        self.assertEqual(utils.to_en_phone("۰۹۱۲۳۴۵۶۷۸۹"), "09123456789")


class InvoiceCodeTests(TestCase):
    """Stable TT-<jy><jm>-<id> invoice codes."""

    def test_format(self):
        self.assertEqual(utils.invoice_code(14, "2026-09-10"), "TT-140506-0014")

    def test_fallback_without_parseable_date(self):
        self.assertEqual(utils.invoice_code(9, ""), "TT-0009")

    def test_empty_id(self):
        self.assertEqual(utils.invoice_code(0, "2026-09-10"), "")


class ProductDictTests(TestCase):
    """product_dict — every display key the frontend consumes."""

    def test_all_keys_present(self):
        p = make_product(purchase_price=1000.0, sale_price=1500.0, available=True)
        d = utils.product_dict(p)
        for key in ("id", "name", "office_code", "website_code", "brand",
                    "purchase_price", "sale_price", "available", "is_available",
                    "purchase_date", "purchase_date_fa",
                    "purchase_date_weekday", "purchase_price_display",
                    "sale_price_display", "profit_per_unit",
                    "profit_per_unit_display", "total_value",
                    "total_value_display", "total_sale_value",
                    "total_sale_value_display", "availability_fa",
                    "created_at", "updated_at", "notes", "image"):
            self.assertIn(key, d)
        self.assertEqual(d["available"], 1)
        self.assertIs(d["is_available"], True)
        self.assertEqual(d["profit_per_unit"], 500)
        self.assertEqual(d["availability_fa"], "موجود")
        self.assertEqual(d["purchase_date_fa"], utils.fa_date(today_iso()))


class SalePaymentDictTests(TestCase):
    """sale_dict / payment_dict computed fields."""

    def test_sale_dict_deposit_and_invoice(self):
        p = make_product()
        s = Sale.objects.create(
            product=p, sale_price=1500, purchase_price=1000, profit=500,
            sale_date=today_iso(), customer="علی", customer_phone="09123456789",
            final_price=1400, paid_cash=400, paid_pos=0, paid_card2card=0,
            payment_type="deposit", is_settled=False, invoice_code="")
        d = utils.sale_dict(s, p)
        self.assertEqual(d["final_price"], 1400)
        self.assertEqual(d["paid_total"], 400)
        self.assertEqual(d["invoice_code"], utils.invoice_code(s.id, s.sale_date))
        self.assertIn("نقدی", d["paid_breakdown_fa"])
        self.assertEqual(d["payment_type_fa"], "بیعانه")
        self.assertEqual(d["product_name"], p.name)

    def test_sale_dict_deleted_product_degrades(self):
        # Sale.product is NOT NULL — use a detached instance to simulate
        # a deleted product (the cascade removes the sale in real life,
        # but the dict builder must still tolerate a missing product).
        s = Sale(
            product_id=None, sale_price=1, purchase_price=1, profit=0,
            sale_date=today_iso(), customer="x", customer_phone="09123456789",
            final_price=1)
        d = utils.sale_dict(s, None)
        self.assertEqual(d["product_name"], "")
        self.assertEqual(d["brand"], "")

    def test_payment_dict_math(self):
        pay = Payment.objects.create(
            product_name="w", customer_name="c", total_amount=1000,
            paid_amount=250, pay_date=today_iso())
        d = utils.payment_dict(pay)
        self.assertEqual(d["remaining"], 750)
        self.assertEqual(d["paid_percent"], 25)
        self.assertEqual(d["remaining_display"], utils.fa_money(750))


class RepairTrackingDictTests(TestCase):
    """repair_dict / tracking_dict status translations."""

    def test_repair_dict_status_fields(self):
        r = Repair.objects.create(
            watch_name="w", customer_name="c", status="in_progress",
            repair_price=123, delivery_date=today_iso())
        d = utils.repair_dict(r)
        self.assertEqual(d["status_fa"], "در حال تعمیر")
        self.assertEqual(d["status_color"], "amber")
        self.assertEqual(d["is_warranty_fa"], "خیر")
        self.assertEqual(d["repair_price_display"], utils.fa_money(123))

    def test_tracking_dict_status_fields(self):
        t = Tracking.objects.create(item_name="x", status="ordered", price=50)
        d = utils.tracking_dict(t)
        self.assertEqual(d["status_fa"], "سفارش داده شد")
        self.assertEqual(d["status_color"], "amber")
        self.assertEqual(d["price_display"], utils.fa_money(50))


class RemoveImageTests(TestCase):
    """remove_image only deletes files inside the image directory."""

    def test_missing_and_blank_names_are_safe(self):
        utils.remove_image("")
        utils.remove_image(None)
        utils.remove_image("../../etc/passwd")  # basename-only, must not raise
