# -*- coding: utf-8 -*-
"""تست‌های یکپارچگی فروش و تقویم — پورت Django نسخه‌ی تست قدیمی.

قرارداد: فروش ثبت‌شده باید هم در نمای ماه و هم در نمای روز تقویم دیده شود؛
حذف فروش یا محصول باید بلافاصله از هر دو نما پاک شود، موجودی برگردد و
رسید بیعانه هم به‌صورت آبشاری حذف شود.
"""
import datetime

from django.test import TestCase

from inventory.jalali import gregorian_to_jalali
from inventory.models import Payment, Product, Sale


def _today_iso():
    return datetime.date.today().isoformat()


class CalendarSaleConsistencyTests(TestCase):
    def _mk_product(self, name, office, website):
        r = self.client.post("/api/products", data={
            "name": name, "office_code": office, "website_code": website,
            "purchase_price": "100", "sale_price": "200",
        }, content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["product"]["id"]

    def _mk_sale(self, pid, **extra):
        payload = {
            "product_id": pid, "payment_type": "cash",
            "customer": "علی", "customer_phone": "09123456789", **extra,
        }
        r = self.client.post("/api/sales", data=payload, content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["sale"]["id"]

    def _cal_sale_ids(self):
        today = datetime.date.today()
        jy, jm, _ = gregorian_to_jalali(today.year, today.month, today.day)
        cells = self.client.get(f"/api/calendar?jy={jy}&jm={jm}").json()["cells"]
        return [s["id"] for c in cells if c for s in c["sales"]]

    def _day_sale_ids(self, iso):
        return [s["id"] for s in
                self.client.get(f"/api/calendar/day?date={iso}").json()["sales"]]

    def test_sale_visible_then_deleted_from_both_views(self):
        """فروش بی‌تاریخ (امروز) در ماه و روز دیده می‌شود؛ حذف → از هر دو نما پاک."""
        pid = self._mk_product("Test Rolex", "OF-10", "WS-10")
        sid = self._mk_sale(pid)  # بدون تاریخ → امروز
        self.assertIn(sid, self._cal_sale_ids())
        self.assertIn(sid, self._day_sale_ids(_today_iso()))

        r = self.client.delete(f"/api/sales/{sid}")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn(sid, self._cal_sale_ids())
        self.assertNotIn(sid, self._day_sale_ids(_today_iso()))
        self.assertTrue(Product.objects.get(id=pid).available)

    def test_deposit_receipt_cascade_on_bulk_delete(self):
        """فروش بیعانه رسید می‌سازد؛ حذف گروهی فروش، رسید را هم حذف می‌کند."""
        pid = self._mk_product("Deposit Test", "OF-20", "WS-20")
        sid = self._mk_sale(pid, payment_type="deposit", paid_cash="50")
        self.assertEqual(Payment.objects.filter(sale_id=sid).count(), 1)

        r = self.client.post("/api/sales/bulk-delete",
                             data={"ids": [sid]}, content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Payment.objects.filter(sale_id=sid).count(), 0)
        self.assertFalse(Sale.objects.filter(id=sid).exists())

    def test_product_delete_removes_sale_from_calendar(self):
        """حذف محصول، فروش آن را از تقویم هم حذف می‌کند (آبشاری)."""
        pid = self._mk_product("Cascade Test", "OF-30", "WS-30")
        sid = self._mk_sale(pid)
        self.assertIn(sid, self._cal_sale_ids())

        r = self.client.delete(f"/api/products/{pid}")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn(sid, self._cal_sale_ids())
        self.assertNotIn(sid, self._day_sale_ids(_today_iso()))
        self.assertFalse(Sale.objects.filter(id=sid).exists())
