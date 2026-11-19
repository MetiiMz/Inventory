# -*- coding: utf-8 -*-
"""پیلود روز تقویم — کلیدهایی که کارت‌های مودال جزئیات می‌خوانند.

مودال جزئیات تقویم همان کارت‌های صفحه‌ی فروش‌ها را نشان می‌دهد؛ پس
داده‌ی روز تقویم باید همان دیکشنری فروش (``sale_dict``) و همان
دیکشنری محصول/تعمیر را داشته باشد.  این تست قرارداد را می‌بندد تا
اگر روزی «فروش‌های تقویم» جداگانه ساخته شوند، همین‌جا شکست بخورد.
"""
import json

from django.test import TestCase

DAY = "2026-09-12"
DAY_FA = "۱۴۰۵/۰۶/۲۱"

# کاشی‌های کارت «اطلاعات ساعت» (هر چهار نوع رویداد)
INFO_TILE_KEYS = (
    "brand", "reference", "office_code", "website_code",
    "purchase_price_display", "purchase_date_fa", "supplier",
)

# کاشی‌های کارت «اطلاعات فروش» — همه‌ی انواع پرداخت
SALE_TILE_KEYS = INFO_TILE_KEYS + (
    "product_name", "product_image", "customer", "customer_phone_fa",
    "sale_price_display", "profit_display", "invoice_code", "sale_date_fa",
    "sale_type_fa", "payment_type", "payment_type_fa", "notes",
    "credit_provider_fa", "credit_tracking_code",
    "deposit_paid_amount_display", "deposit_remaining",
    "deposit_remaining_display", "is_settled", "settled_at_fa",
)

# کارت «اطلاعات موجودی» خرید + یادداشت
PURCHASE_TILE_KEYS = INFO_TILE_KEYS + (
    "name", "image", "is_available", "notes", "purchase_date",
)

# کارت‌های «اطلاعات ساعت» و «اطلاعات تعمیر» (دریافت و بازگشت)
REPAIR_TILE_KEYS = (
    "watch_name", "image", "watch_code", "issue",
    "customer_name", "customer_phone_fa",
    "delivery_date_fa", "return_date_fa",
    "is_warranty_fa", "status_fa", "status_color",
    "repair_price", "repair_price_display", "notes",
)


class CalendarDayDetailPayloadTests(TestCase):
    def _product(self, tag):
        payload = {
            "name": f"ساعت {tag}",
            "office_code": f"OF-{tag}",
            "website_code": f"WS-{tag}",
            "reference": f"REF-{tag}",
            "brand": "سیکو",
            "supplier": "تأمین‌کننده تست",
            "purchase_price": "1000000",
            "purchase_date": DAY,
            "image": f"{tag}.png",
            "notes": f"یادداشت محصول {tag}",
        }
        r = self.client.post("/api/products", data=payload,
                             content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["product"]

    def _sale(self, product_id, **extra):
        payload = {
            "product_id": product_id,
            "sale_price": "1500000",
            "payment_type": "cash",
            "customer": "خریدار تست",
            "customer_phone": "09123456789",
            "sale_date": DAY,
            **extra,
        }
        r = self.client.post("/api/sales", data=payload,
                             content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["sale"]

    def _repair(self, **extra):
        payload = {
            "watch_name": "ساعت تعمیری",
            "watch_code": "RP-1",
            "issue": "شیشه شکسته\nبند شل",
            "delivery_date": DAY,
            "return_date": DAY,
            "customer_name": "مشتری تعمیر",
            "customer_phone": "09121112233",
            "is_warranty": 0,
            "status": "done",
            "repair_price": "250000",
            "image": "repair.png",
            "notes": "یادداشت تعمیر",
            **extra,
        }
        r = self.client.post("/api/repairs", data=payload,
                             content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["repair"]

    def _day(self):
        r = self.client.get(f"/api/calendar/day?date={DAY}")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def test_sales_carry_every_sale_tile_key(self):
        """همه‌ی انواع پرداخت: کلیدها و مقادیر = همان چیزی که «فروش‌ها» می‌دهد."""
        cash = self._sale(self._product("cash")["id"], notes="یادداشت نقدی")
        deposit = self._sale(
            self._product("deposit")["id"], payment_type="deposit",
            deposit_amount="500000")
        credit = self._sale(
            self._product("credit")["id"], payment_type="credit",
            credit_provider="torob", credit_tracking_code="1234567")

        listed = {s["id"]: s for s in self.client.get("/api/sales").json()["items"]}
        day_sales = {s["id"]: s for s in self._day()["sales"]}

        for sale in (cash, deposit, credit):
            with self.subTest(payment=sale["payment_type"]):
                sid = sale["id"]
                self.assertIn(sid, day_sales)
                day_row, list_row = day_sales[sid], listed[sid]
                for key in SALE_TILE_KEYS:
                    self.assertIn(key, day_row, f"کلید {key} در پیلود روز نیست")
                    self.assertEqual(day_row[key], list_row[key],
                                     f"مقدار {key} با صفحه‌ی فروش‌ها یکی نیست")

        # مقادیر ویژه‌ی هر نوع پرداخت واقعاً پر شده‌اند
        self.assertEqual(day_sales[credit["id"]]["credit_provider_fa"], "ترب‌پی")
        self.assertTrue(day_sales[credit["id"]]["credit_tracking_code"].startswith("T-"))
        dep = day_sales[deposit["id"]]
        self.assertIsNotNone(dep["deposit_paid_amount_display"])
        self.assertGreater(dep["deposit_remaining"], 0)
        self.assertTrue(dep["deposit_remaining_display"])

    def test_purchase_carries_every_stock_tile_key(self):
        product = self._product("buy")
        listed = {p["id"]: p for p in self.client.get("/api/products").json()}
        purchases = {p["id"]: p for p in self._day()["purchases"]}

        self.assertIn(product["id"], purchases)
        row = purchases[product["id"]]
        for key in PURCHASE_TILE_KEYS:
            self.assertIn(key, row, f"کلید {key} در پیلود خرید نیست")
            self.assertEqual(row[key], listed[product["id"]][key])
        self.assertEqual(row["purchase_date_fa"], DAY_FA)
        self.assertTrue(row["is_available"])
        self.assertEqual(row["notes"], "یادداشت محصول buy")

    def test_repairs_carry_both_dates_for_in_and_out(self):
        repair = self._repair()
        day = self._day()
        for bucket in ("repairs_in", "repairs_out"):
            with self.subTest(bucket=bucket):
                rows = {r["id"]: r for r in day[bucket]}
                self.assertIn(repair["id"], rows)
                row = rows[repair["id"]]
                for key in REPAIR_TILE_KEYS:
                    self.assertIn(key, row, f"کلید {key} در {bucket} نیست")
                # هر دو تاریخ در هر دو حالت فرستاده می‌شوند
                self.assertEqual(row["delivery_date_fa"], DAY_FA)
                self.assertEqual(row["return_date_fa"], DAY_FA)
                self.assertEqual(row["status_fa"], "آماده تحویل")
                self.assertEqual(row["status_color"], "green")
                self.assertEqual(row["repair_price_display"], "۲۵۰٬۰۰۰")
                self.assertEqual(row["customer_phone_fa"], "۰۹۱۲۱۱۱۲۲۳۳")
                self.assertIn("\n", row["issue"])

    def test_day_payload_is_json_serialisable(self):
        """پیلود روز نباید شیء غیر JSON (تاریخ/Decimal) داشته باشد."""
        self._sale(self._product("json")["id"])
        self._repair()
        json.dumps(self._day())
