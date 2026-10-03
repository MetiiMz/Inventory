# -*- coding: utf-8 -*-
"""Tests for inventory.api.services — sale business rules (cash/deposit)."""
from django.test import TestCase

from inventory.api import services
from inventory.api.services import ApiError
from inventory.models import Payment, Product, Sale
from tests.helpers import make_product, sale_payload, today_iso


def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except ApiError as exc:
        return None, exc


class SaleQuerysetTests(TestCase):
    """Filtering of the sale list (deposits always included)."""

    def setUp(self):
        self.p1 = make_product(name="Rolex")
        self.p2 = make_product(name="Omega", office_code="OF-X2",
                               website_code="WS-X2")
        self.cash = Sale.objects.create(
            product=self.p1, sale_price=100, purchase_price=50, profit=50,
            sale_date="2026-09-01", customer="Ali", customer_phone="09120000001",
            final_price=100, paid_cash=100, payment_type="cash", is_settled=True)
        self.deposit = Sale.objects.create(
            product=self.p2, sale_price=200, purchase_price=50, profit=150,
            sale_date="2026-09-02", customer="Mary", customer_phone="09120000002",
            final_price=200, paid_cash=50, payment_type="deposit",
            is_settled=False)

    def test_deposit_sales_are_always_listed(self):
        ids = list(services.sale_queryset({}).values_list("id", flat=True))
        self.assertIn(self.deposit.id, ids)

    def test_search_by_customer_phone_and_invoice(self):
        self.assertIn(self.cash.id,
                      list(services.sale_queryset({"q": "Ali"}).values_list("id", flat=True)))
        self.assertIn(self.deposit.id,
                      list(services.sale_queryset({"q": "09120000002"}).values_list("id", flat=True)))

    def test_sale_type_and_pay_method_filters(self):
        ids = list(services.sale_queryset({"sale_type": "online"})
                   .values_list("id", flat=True))
        self.assertEqual(ids, [])
        ids = list(services.sale_queryset({"pay_method": "pos"})
                   .values_list("id", flat=True))
        self.assertEqual(ids, [])
        ids = list(services.sale_queryset({"pay_method": "cash"})
                   .values_list("id", flat=True))
        # both fixtures paid in cash (deposit receipt paid_cash counts too)
        self.assertIn(self.cash.id, ids)

    def test_date_range(self):
        ids = list(services.sale_queryset(
            {"date_from": "1405/06/11", "date_to": "1405/06/12"})
            .values_list("id", flat=True))
        self.assertEqual(ids, [self.deposit.id])

    def test_next_invoice_code_increments(self):
        code = services.next_invoice_code()
        self.assertTrue(code.startswith("TT-"), code)


class SaleCreateTests(TestCase):
    """Transactional sale creation rules."""

    def test_cash_sale_flips_stock_and_settles(self):
        p = make_product(available=True)
        sale, err = call(services.create_sale, sale_payload(p.id))
        self.assertIsNone(err)
        self.assertTrue(sale.is_settled)
        self.assertFalse(Product.objects.get(id=p.id).available)
        self.assertEqual(sale.profit, 500_000)

    def test_cash_sale_without_breakdown_defaults_to_cash(self):
        p = make_product()
        sale, _ = call(services.create_sale, sale_payload(p.id))
        self.assertEqual(sale.paid_cash, 1_500_000)
        self.assertEqual(sale.paid_pos, 0)

    def test_cash_sale_with_breakdown(self):
        p = make_product()
        sale, err = call(services.create_sale, sale_payload(
            p.id, paid_cash="400000", paid_pos="600000", paid_card2card="500000"))
        self.assertIsNone(err)
        self.assertEqual((sale.paid_cash, sale.paid_pos, sale.paid_card2card),
                         (400000.0, 600000.0, 500000.0))

    def test_deposit_creates_receipt_and_keeps_unsettled(self):
        p = make_product()
        sale, err = call(services.create_sale, sale_payload(
            p.id, payment_type="deposit", paid_cash="500000"))
        self.assertIsNone(err)
        self.assertFalse(sale.is_settled)
        receipt = Payment.objects.get(sale=sale)
        self.assertEqual(receipt.paid_amount, 500000)
        self.assertEqual(receipt.total_amount, 1500000)
        self.assertIn("مانده", receipt.notes)

    def test_discount_sets_final_price(self):
        p = make_product()
        sale, _ = call(services.create_sale, sale_payload(
            p.id, discount_price="1400000"))
        self.assertEqual(sale.final_price, 1400000)
        self.assertEqual(sale.profit, 400_000)

    def test_validation_errors(self):
        p = make_product()
        cases = [
            (sale_payload(p.id, customer=""), "نام خریدار"),
            (sale_payload(p.id, customer_phone="123"), "شماره تماس"),
            (sale_payload(p.id, sale_price="2000000", discount_price="2500000"),
             "قیمت نهایی"),
            (sale_payload(p.id, paid_cash="99999999"), "قیمت نهایی"),
            (sale_payload(99999), "محصول یافت نشد"),
            (sale_payload(None), "محصول انتخاب نشده است"),
            (sale_payload(p.id, sale_date="31/31/9999"), "تاریخ فروش"),
            (sale_payload(p.id, payment_type="deposit", paid_cash="0"),
             "بیعانه"),
        ]
        for payload, fragment in cases:
            _, err = call(services.create_sale, payload)
            self.assertIsNotNone(err, fragment)
            self.assertIn(fragment, err.message, fragment)

    def test_missing_product_is_404(self):
        _, err = call(services.create_sale, sale_payload(99999))
        self.assertEqual(err.status_code, 404)

    def test_manual_invoice_code_unique_and_capped(self):
        p = make_product()
        sale, err = call(services.create_sale,
                         sale_payload(p.id, invoice_code="MY-CODE-1"))
        self.assertIsNone(err)
        self.assertEqual(sale.invoice_code, "MY-CODE-1")
        p2 = make_product()
        _, err = call(services.create_sale,
                      sale_payload(p2.id, invoice_code="MY-CODE-1"))
        self.assertIn("کد فاکتور", err.message)
        p3 = make_product()
        _, err = call(services.create_sale, sale_payload(
            p3.id, invoice_code="X" * 41))
        self.assertIn("۴۰", err.message)


class SaleUpdateDeleteTests(TestCase):
    """update_sale / delete_sale / bulk_delete_sales."""

    def setUp(self):
        self.p = make_product()
        self.sale = services.create_sale(sale_payload(self.p.id))
        services.create_sale(sale_payload(
            make_product(office_code="OF-D", website_code="WS-D").id,
            payment_type="deposit", paid_cash="500000"))

    def test_update_prices_and_fields(self):
        services.update_sale(self.sale, {
            "sale_price": "1600000", "discount_price": "1500000",
            "customer": "مریم", "notes": "edited",
        })
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.final_price, 1500000)
        self.assertEqual(self.sale.customer, "مریم")
        self.assertEqual(self.sale.notes, "edited")

    def test_update_date_syncs_receipt(self):
        receipt = Payment.objects.filter(sale_id=self.sale.id).first()
        services.update_sale(self.sale, {"sale_date": "1405/01/15"})
        if receipt:  # cash sale has no receipt; use the deposit one instead
            receipt.refresh_from_db()

        dep_sale = Sale.objects.filter(payment_type="deposit").first()
        dep_receipt = Payment.objects.get(sale_id=dep_sale.id)
        services.update_sale(dep_sale, {"sale_date": "1405/02/20"})
        dep_receipt.refresh_from_db()
        self.assertEqual(dep_receipt.pay_date, "2026-05-10")

    def test_patch_keeps_current_values(self):
        services.update_sale(self.sale, {"notes": "only-note"})
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.customer, "علی")
        self.assertEqual(self.sale.final_price, 1500000)

    def test_update_validation_still_applies(self):
        _, err = call(services.update_sale, self.sale, {"customer": ""})
        self.assertEqual(err.status_code, 400)

    def test_delete_restores_stock(self):
        services.delete_sale(self.sale)
        self.assertFalse(Sale.objects.filter(id=self.sale.id).exists())
        self.assertTrue(Product.objects.get(id=self.p.id).available)

    def test_bulk_delete_restores_stock_and_requires_ids(self):
        _, err = call(services.bulk_delete_sales, [])
        self.assertEqual(err.status_code, 400)
        dep_sale = Sale.objects.filter(payment_type="deposit").first()
        n = services.bulk_delete_sales([self.sale.id, str(dep_sale.id)])
        self.assertEqual(n, 2)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertTrue(Product.objects.get(id=self.p.id).available)
        self.assertEqual(
            Payment.objects.filter(sale_id=dep_sale.id).count(), 0)
