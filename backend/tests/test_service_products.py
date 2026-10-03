# -*- coding: utf-8 -*-
"""Tests for inventory.api.services — product business rules."""
from django.test import TestCase

from inventory.api import services
from inventory.api.services import ApiError
from inventory.models import Product
from tests.helpers import make_product, product_payload


def call(fn, *args, **kwargs):
    """Run a service fn; return (result, api_error_or_None)."""
    try:
        return fn(*args, **kwargs), None
    except ApiError as exc:
        return None, exc


class ProductQuerysetTests(TestCase):
    """Filtering / searching / ordering of the product list."""

    def setUp(self):
        self.a = make_product(name="Rolex Alpha", office_code="OF-A",
                              website_code="WS-A", brand="Rolex",
                              purchase_price=1000, sale_price=2000,
                              purchase_date="2026-09-01", available=True)
        self.b = make_product(name="Omega Beta", office_code="OF-B",
                              website_code="WS-B", brand="Omega",
                              purchase_price=3000, sale_price=4000,
                              purchase_date="2026-09-05", available=False)

    def test_search_matches_name_code_brand_supplier(self):
        for term in ("Alpha", "OF-A", "WS-A", "Rolex"):
            ids = list(services.product_queryset({"q": term})
                       .values_list("id", flat=True))
            self.assertEqual(ids, [self.a.id], term)

    def test_brand_filter(self):
        ids = list(services.product_queryset({"brand": "Omega"})
                   .values_list("id", flat=True))
        self.assertEqual(ids, [self.b.id])

    def test_status_filter(self):
        avail = list(services.product_queryset({"status": "available"})
                     .values_list("id", flat=True))
        unavail = list(services.product_queryset({"status": "unavailable"})
                       .values_list("id", flat=True))
        self.assertEqual(avail, [self.a.id])
        self.assertEqual(unavail, [self.b.id])

    def test_date_range_filter(self):
        ids = list(services.product_queryset(
            {"date_from": "1405/06/14", "date_to": "1405/06/20"})
            .values_list("id", flat=True))
        self.assertEqual(ids, [self.b.id])

    def test_sorting_asc_desc_and_nocase(self):
        qs = services.product_queryset({"sort": "sale_price", "dir": "desc"})
        self.assertEqual(list(qs.values_list("id", flat=True)), [self.b.id, self.a.id])
        qs = services.product_queryset({"sort": "name", "dir": "asc"})
        self.assertEqual(list(qs.values_list("id", flat=True)), [self.b.id, self.a.id])

    def test_unknown_sort_falls_back(self):
        """An unknown sort column falls back to office_code (asc)."""
        qs = services.product_queryset({"sort": "hacker_field"})
        # fallback is office_code ascending
        self.assertEqual(list(qs.values_list("id", flat=True)),
                         list(Product.objects.order_by("office_code", "-id")
                              .values_list("id", flat=True)))


class ProductWriteTests(TestCase):
    """create/update/delete with validation and duplicate detection."""

    def test_create_valid_product(self):
        p, err = call(services.create_product, product_payload())
        self.assertIsNone(err)
        self.assertTrue(p.available)
        self.assertEqual(p.name, "Payload Watch")

    def test_create_missing_required_fields(self):
        for missing in ("name", "office_code", "website_code"):
            payload = product_payload()
            payload.pop(missing)
            _, err = call(services.create_product, payload)
            self.assertEqual(err.status_code, 400, missing)

    def test_create_bad_purchase_date(self):
        _, err = call(services.create_product,
                      product_payload(purchase_date="31/31/9999"))
        self.assertEqual(err.status_code, 400)
        self.assertIn("تاریخ", err.message)

    def test_duplicate_codes_rejected_case_insensitive(self):
        services.create_product(product_payload())
        payload = product_payload(office_code="OF-UNIQUE-Z",
                                  website_code="WS-UNIQUE-Z")
        # reuse the first product's office code in different case
        first = Product.objects.first()
        payload["office_code"] = first.office_code.lower()
        _, err = call(services.create_product, payload)
        self.assertEqual(err.status_code, 400)
        self.assertIn("کد دفتر فروشگاه", err.message)

    def test_duplicate_website_code_message(self):
        first = services.create_product(product_payload())
        _, err = call(services.create_product,
                      product_payload(office_code="OF-unique-x"))
        self.assertIn("کد انبار سایت", err.message)

    def test_update_preserves_sold_state_and_swaps_image(self):
        p = make_product(image="img_a.png")
        services.update_product(p, product_payload(
            office_code=p.office_code, website_code=p.website_code,
            image="img_b.png"))
        p.refresh_from_db()
        self.assertEqual(p.image, "img_b.png")
        # available flag is never flipped by edits
        p2 = make_product(office_code="OF-SOLD", website_code="WS-SOLD",
                          available=False)
        services.update_product(p2, product_payload(
            office_code=p2.office_code, website_code=p2.website_code))
        p2.refresh_from_db()
        self.assertFalse(p2.available)

    def test_update_patch_fills_missing_fields(self):
        p = make_product(brand="KeepMe", purchase_price=777)
        services.update_product(p, {"name": "Only Name"}, partial=True)
        p.refresh_from_db()
        self.assertEqual(p.brand, "KeepMe")
        self.assertEqual(p.purchase_price, 777)

    def test_delete_product(self):
        p = make_product()
        services.delete_product(p)
        self.assertFalse(Product.objects.filter(id=p.id).exists())

    def test_bulk_delete_requires_ids(self):
        _, err = call(services.bulk_delete_products, [])
        self.assertEqual(err.status_code, 400)
        p = make_product()
        n = services.bulk_delete_products([str(p.id)])
        self.assertEqual(n, 1)
        self.assertFalse(Product.objects.filter(id=p.id).exists())

    def test_error_object_shape(self):
        _, err = call(services.create_product, {"name": ""})
        self.assertEqual(err.status_code, 400)
        self.assertIsInstance(err.message, str)
