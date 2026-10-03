# -*- coding: utf-8 -*-
"""Tests for inventory.api.compat — the exact JSON contract the frontend uses."""
import json

from django.test import TestCase

from inventory.models import Payment, Product, Repair, Sale, Setting, Tracking
from tests.helpers import make_product, product_payload, sale_payload


class CompatProductContractTests(TestCase):
    """Legacy /api/products — plain-array lists, wrapped creates, ok envelopes."""

    def test_list_is_plain_array_with_legacy_keys(self):
        make_product()
        r = self.client.get("/api/products")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), list)
        row = r.json()[0]
        for key in ("is_available", "available", "purchase_date_fa",
                    "purchase_price_display", "total_value",
                    "total_sale_value", "availability_fa",
                    "profit_per_unit_display", "purchase_date_weekday"):
            self.assertIn(key, row)

    def test_create_wraps_in_product_and_returns_ok(self):
        r = self.client.post("/api/products", product_payload(),
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertIn("id", body["product"])

    def test_error_envelope(self):
        r = self.client.post("/api/products", {"name": ""},
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["ok"])
        self.assertIn("error", r.json())
        self.assertNotIn("detail", r.json())

    def test_put_update_delete(self):
        pid = self.client.post("/api/products", product_payload(),
                               content_type="application/json").json()["product"]["id"]
        r = self.client.put(f"/api/products/{pid}",
                            data=json.dumps(product_payload(name="Edited")),
                            content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["product"]["name"], "Edited")
        r = self.client.delete(f"/api/products/{pid}")
        self.assertTrue(r.json()["ok"])
        self.assertFalse(Product.objects.filter(id=pid).exists())

    def test_bulk_delete_returns_count(self):
        p1 = make_product()
        p2 = make_product(office_code="OF-BD", website_code="WS-BD")
        r = self.client.post("/api/products/bulk-delete",
                             data=json.dumps({"ids": [p1.id, p2.id]}),
                             content_type="application/json")
        self.assertEqual(r.json()["deleted"], 2)
        r = self.client.post("/api/products/bulk-delete",
                             data=json.dumps({"ids": []}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)


class CompatSaleContractTests(TestCase):
    """Legacy /api/sales — {items, summary}, wrapped sale, next_code."""

    def test_list_shape_items_summary(self):
        p = make_product()
        self.client.post("/api/sales", sale_payload(p.id),
                         content_type="application/json")
        r = self.client.get("/api/sales")
        body = r.json()
        self.assertEqual(set(body.keys()), {"items", "summary"})
        self.assertEqual(body["summary"]["count"], 1)
        row = body["items"][0]
        for key in ("product_image", "product_name", "final_price_display",
                    "profit_display", "sale_date_fa", "paid_total",
                    "customer_phone_fa", "invoice_code", "is_settled"):
            self.assertIn(key, row)

    def test_next_code_and_create(self):
        r = self.client.get("/api/sales", {"next_code": "1"})
        self.assertIn("next_invoice_code", r.json())
        p = make_product()
        r = self.client.post("/api/sales", sale_payload(p.id),
                             content_type="application/json")
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertIn("invoice_code", body["sale"])

    def test_put_and_delete_envelopes(self):
        p = make_product()
        sid = self.client.post("/api/sales", sale_payload(p.id),
                               content_type="application/json").json()["sale"]["id"]
        r = self.client.put(f"/api/sales/{sid}",
                            data=json.dumps(sale_payload(p.id, notes="up")),
                            content_type="application/json")
        self.assertTrue(r.json()["ok"])
        self.assertEqual(r.json()["sale"]["notes"], "up")
        r = self.client.delete(f"/api/sales/{sid}")
        self.assertTrue(r.json()["ok"])
        self.assertTrue(Product.objects.get(id=p.id).available)


class CompatPaymentContractTests(TestCase):
    """Legacy /api/payments — ok() envelope with items+summary."""

    def test_list_summary_and_filters(self):
        Payment.objects.create(product_name="W", customer_name="C",
                               total_amount=1000, paid_amount=400,
                               pay_date="2026-09-10")
        r = self.client.get("/api/payments", {"status": "unpaid"})
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["summary"]["count"], 1)
        row = body["items"][0]
        for key in ("remaining", "paid_percent", "remaining_display",
                    "pay_date_fa", "customer_phone_fa"):
            self.assertIn(key, row)

    def test_create_put_add_settle_delete(self):
        r = self.client.post("/api/payments", {
            "product_name": "W", "total_amount": "1000", "paid_amount": "100"},
            content_type="application/json")
        body = r.json()
        self.assertTrue(body["ok"])
        pid = body["payment"]["id"]

        r = self.client.put(f"/api/payments/{pid}",
                            data=json.dumps({"total_amount": "1000",
                                             "paid_amount": "200"}),
                            content_type="application/json")
        self.assertTrue(r.json()["ok"])
        self.assertEqual(r.json()["payment"]["paid_amount"], 200)

        r = self.client.post(f"/api/payments/{pid}/add",
                             data=json.dumps({"amount": "800"}),
                             content_type="application/json")
        self.assertTrue(r.json()["ok"])

        r = self.client.post(f"/api/payments/{pid}/settle-full",
                             data=json.dumps({}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)  # already settled
        self.assertIn("قبلاً", r.json()["error"])

        r = self.client.delete(f"/api/payments/{pid}")
        self.assertTrue(r.json()["ok"])


class CompatRepairTrackingContractTests(TestCase):
    """Legacy /api/repairs and /api/tracking."""

    def test_repairs_flow(self):
        r = self.client.post("/api/repairs", {"watch_name": "W"},
                             content_type="application/json")
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertIn("status_fa", body["repair"])
        rid = body["repair"]["id"]

        r = self.client.post(f"/api/repairs/{rid}/status",
                             data=json.dumps({"status": "delivered"}),
                             content_type="application/json")
        self.assertTrue(r.json()["ok"])

        r = self.client.get("/api/repairs", {"status": "delivered"})
        self.assertIsInstance(r.json(), list)
        self.assertEqual(len(r.json()), 1)

        r = self.client.delete(f"/api/repairs/{rid}")
        self.assertTrue(r.json()["ok"])

    def test_tracking_flow(self):
        r = self.client.post("/api/tracking", {"item_name": "Item"},
                             content_type="application/json")
        self.assertTrue(r.json()["ok"])
        tid = r.json()["tracking"]["id"]
        r = self.client.put(f"/api/tracking/{tid}",
                            data=json.dumps({"item_name": "Item",
                                             "status": "ordered"}),
                            content_type="application/json")
        self.assertTrue(r.json()["ok"])
        r = self.client.post("/api/tracking/bulk-delete",
                             data=json.dumps({"ids": [tid]}),
                             content_type="application/json")
        self.assertEqual(r.json()["deleted"], 1)


class CompatMiscContractTests(TestCase):
    """Brands POST (the bug the smoke run caught), settings, calendar, 404s."""

    def test_brands_get_and_post(self):
        r = self.client.post("/api/brands", {"name": "برند"},
                             content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        r = self.client.get("/api/brands")
        self.assertEqual(r.json()["brands"], ["برند"])
        r = self.client.post("/api/brands/delete", {"name": "برند"},
                             content_type="application/json")
        self.assertTrue(r.json()["ok"])

    def test_settings_get_and_post(self):
        r = self.client.post("/api/settings", {"store_name": "تیک"},
                             content_type="application/json")
        self.assertTrue(r.json()["ok"])
        r = self.client.get("/api/settings")
        for key in ("store_name", "store_phone", "store_address",
                    "currency", "site_icon"):
            self.assertIn(key, r.json())
        self.assertEqual(r.json()["store_name"], "تیک")

    def test_database_info_and_404(self):
        r = self.client.get("/api/database/info")
        self.assertTrue(r.json()["ok"])
        self.assertIn("products", r.json()["counts"])
        r = self.client.get("/api/definitely-not-a-route")
        self.assertEqual(r.status_code, 404)

    def test_page_routes_render(self):
        for url in ("/dashboard", "/products", "/calendar", "/repairs",
                    "/sold", "/tracking", "/payments", "/settings"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)
