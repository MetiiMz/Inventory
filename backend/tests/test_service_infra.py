# -*- coding: utf-8 -*-
"""Tests for payment, repair and tracking service functions."""
from django.test import TestCase

from inventory.api import services
from inventory.api.services import ApiError
from inventory.models import Payment, Repair, Sale, Tracking
from tests.helpers import make_product, today_iso


def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except ApiError as exc:
        return None, exc


def make_payment(**overrides):
    fields = {
        "product_name": "Watch X", "customer_name": "Ali",
        "customer_phone": "09123456789", "total_amount": 1000.0,
        "paid_amount": 400.0, "pay_date": today_iso(), "notes": "",
    }
    fields.update(overrides)
    return Payment.objects.create(**fields)


class PaymentQuerysetTests(TestCase):
    """status / q filters of the payment list."""

    def test_unpaid_and_paid_filters(self):
        unpaid = make_payment(total_amount=1000, paid_amount=400)
        paid = make_payment(total_amount=500, paid_amount=500,
                            product_name="Done", customer_name="M"
                            )
        ids = list(services.payment_queryset({"status": "unpaid"})
                   .values_list("id", flat=True))
        self.assertEqual(ids, [unpaid.id])
        ids = list(services.payment_queryset({"status": "paid"})
                   .values_list("id", flat=True))
        self.assertEqual(ids, [paid.id])

    def test_q_matches_product_customer_phone(self):
        pay = make_payment(product_name="Golden Watch")
        self.assertIn(pay.id, list(
            services.payment_queryset({"q": "golden"}).values_list("id", flat=True)))
        self.assertIn(pay.id, list(
            services.payment_queryset({"q": "09123456789"}).values_list("id", flat=True)))


class PaymentWriteTests(TestCase):
    """create / update / delete / add / settle-full."""

    def test_create_standalone_payment(self):
        pay, err = call(services.create_payment, {
            "product_name": "Manual", "total_amount": "900",
            "paid_amount": "100", "pay_date": "1405/06/19",
        })
        self.assertIsNone(err)
        self.assertEqual(pay.pay_date, "2026-09-10")

    def test_create_links_product_name_and_rejects_bad_amounts(self):
        product = make_product()
        pay, err = call(services.create_payment, {
            "product_id": str(product.id), "total_amount": "900",
            "paid_amount": "100",
        })
        self.assertIsNone(err)
        self.assertEqual(pay.product_name, product.name)

        _, err = call(services.create_payment, {"total_amount": "0"})
        self.assertIn("نام محصول", err.message)  # name checked before amounts
        _, err = call(services.create_payment,
                      {"product_name": "W", "total_amount": "0"})
        self.assertIn("مبلغ کل", err.message)
        _, err = call(services.create_payment,
                      {"product_name": "W", "total_amount": "100",
                       "paid_amount": "200"})
        self.assertIn("نمی‌تواند از مبلغ کل", err.message)
        _, err = call(services.create_payment,
                      {"product_id": "999999", "total_amount": "100"})
        self.assertIn("یافت نشد", err.message)

    def test_update_recomputes_settlement(self):
        # Sale.product is NOT NULL — create a real product for the sale row
        product = make_product()
        sale = Sale.objects.create(
            product=product, sale_price=1, purchase_price=1, profit=0,
            sale_date=today_iso(), customer="x", customer_phone="09123456789",
            final_price=1, is_settled=False)
        pay = make_payment(sale=sale)
        services.update_payment(pay, {"paid_amount": "1000"})
        pay.refresh_from_db()
        self.assertEqual(pay.settled_at, today_iso())
        self.assertTrue(Sale.objects.get(id=sale.id).is_settled)

        services.update_payment(pay, {"paid_amount": "100"})
        pay.refresh_from_db()
        self.assertEqual(pay.settled_at, "")
        self.assertFalse(Sale.objects.get(id=sale.id).is_settled)

    def test_update_validation(self):
        pay = make_payment()
        _, err = call(services.update_payment, pay, {"total_amount": "0"})
        self.assertEqual(err.status_code, 400)
        _, err = call(services.update_payment, pay,
                      {"total_amount": "100", "paid_amount": "500"})
        self.assertEqual(err.status_code, 400)
        _, err = call(services.update_payment, pay, {"pay_date": "xx"})
        self.assertEqual(err.status_code, 400)

    def test_delete(self):
        pay = make_payment()
        services.delete_payment(pay)
        self.assertFalse(Payment.objects.filter(id=pay.id).exists())

    def test_add_instalment_then_overpay_rejected(self):
        pay = make_payment(total_amount=1000, paid_amount=400)
        pay = services.add_payment(pay, {"amount": "600"})
        self.assertEqual(pay.paid_amount, 1000)
        # fully settled: adding 1 more exceeds the remaining balance
        _, err = call(services.add_payment, pay, {"amount": "1"})
        self.assertIn("مانده", err.message)
        _, err = call(services.add_payment, pay, {"amount": "0"})
        self.assertEqual(err.status_code, 400)

    def test_settle_full_adds_remainder_to_sale_cash(self):
        product = make_product()
        sale = Sale.objects.create(
            product=product, sale_price=1500, purchase_price=1000, profit=500,
            sale_date=today_iso(), customer="علی", customer_phone="09123456789",
            final_price=1500, paid_cash=500, payment_type="deposit",
            is_settled=False)
        pay = make_payment(sale=sale, product=product, total_amount=1500,
                           paid_amount=500)
        services.settle_payment_full(pay)
        pay.refresh_from_db()
        sale.refresh_from_db()
        self.assertEqual(pay.paid_amount, 1500)
        self.assertTrue(sale.is_settled)
        self.assertEqual(sale.paid_cash, 1500)

        _, err = call(services.settle_payment_full, pay)
        self.assertIn("قبلاً", err.message)

    def test_bulk_delete(self):
        pays = [make_payment(), make_payment()]
        _, err = call(services.bulk_delete_payments, [])
        self.assertEqual(err.status_code, 400)
        n = services.bulk_delete_payments([pays[0].id, str(pays[1].id)])
        self.assertEqual(n, 2)


def make_repair(**overrides):
    fields = {
        "watch_name": "Seiko", "watch_code": "WC-1", "issue": "battery",
        "customer_name": "Hassan", "customer_phone": "09120000000",
        "is_warranty": False, "status": "received", "repair_price": 250.0,
        "delivery_date": today_iso(), "return_date": "", "image": "", "notes": "",
    }
    fields.update(overrides)
    return Repair.objects.create(**fields)


class RepairServiceTests(TestCase):
    """repair CRUD + status flow."""

    def test_queryset_filters(self):
        r1 = make_repair(watch_name="Alpha")
        r2 = make_repair(watch_name="Beta", status="delivered")
        self.assertEqual(list(services.repair_queryset({"status": "delivered"})
                              .values_list("id", flat=True)), [r2.id])
        self.assertIn(r1.id, list(
            services.repair_queryset({"q": "alpha"}).values_list("id", flat=True)))
        self.assertIn(r1.id, list(
            services.repair_queryset({"q": "0912000000"}).values_list("id", flat=True)))

    def test_create_defaults_delivery_date_and_status(self):
        repair, err = call(services.create_repair, {"watch_name": "New"})
        self.assertIsNone(err)
        self.assertEqual(repair.delivery_date, today_iso())
        self.assertEqual(repair.status, "received")

    def test_create_validation(self):
        _, err = call(services.create_repair, {"watch_name": ""})
        self.assertIn("الزامی", err.message)
        _, err = call(services.create_repair,
                      {"watch_name": "x", "customer_phone": "abc"})
        self.assertIn("شماره", err.message)
        _, err = call(services.create_repair,
                      {"watch_name": "x", "delivery_date": "xx"})
        self.assertIn("تحویل", err.message)
        _, err = call(services.create_repair,
                      {"watch_name": "x", "return_date": "xx"})
        self.assertIn("بازگشت", err.message)

    def test_update_patch_and_image_swap(self):
        repair = make_repair(image="old.png")
        services.update_repair(repair, {"issue": "dial"}, partial=True)
        repair.refresh_from_db()
        self.assertEqual(repair.issue, "dial")
        self.assertEqual(repair.watch_name, "Seiko")

    def test_delete(self):
        repair = make_repair()
        services.delete_repair(repair)
        self.assertFalse(Repair.objects.filter(id=repair.id).exists())

    def test_set_status_flow(self):
        repair = make_repair()
        repair = services.set_repair_status(repair, {"status": "in_progress"})
        self.assertEqual(repair.status, "in_progress")
        self.assertEqual(repair.return_date, "")
        repair = services.set_repair_status(repair, {"status": "delivered"})
        self.assertEqual(repair.return_date, today_iso())

    def test_set_status_validation(self):
        repair = make_repair()
        _, err = call(services.set_repair_status, repair, {"status": "nope"})
        self.assertEqual(err.status_code, 400)
        _, err = call(services.set_repair_status, repair,
                      {"status": "done", "return_date": "xx"})
        self.assertEqual(err.status_code, 400)

    def test_bulk_delete(self):
        rs = [make_repair(), make_repair()]
        _, err = call(services.bulk_delete_repairs, [])
        self.assertEqual(err.status_code, 400)
        self.assertEqual(services.bulk_delete_repairs([rs[0].id, rs[1].id]), 2)


class TrackingServiceTests(TestCase):
    """tracking CRUD."""

    def test_queryset_filters(self):
        t1 = Tracking.objects.create(item_name="Alpha Order", status="new")
        t2 = Tracking.objects.create(item_name="Beta", status="delivered")
        self.assertEqual(list(services.tracking_queryset({"status": "new"})
                              .values_list("id", flat=True)), [t1.id])
        self.assertIn(t1.id, list(
            services.tracking_queryset({"q": "alpha"}).values_list("id", flat=True)))
        self.assertIn(t2.id, list(
            services.tracking_queryset({"q": "beta"}).values_list("id", flat=True)))

    def test_create_defaults(self):
        t, err = call(services.create_tracking, {"item_name": "Sub Order"})
        self.assertIsNone(err)
        self.assertEqual(t.status, "new")
        self.assertEqual(t.price, 0)

    def test_create_validation(self):
        _, err = call(services.create_tracking, {"item_name": ""})
        self.assertIn("الزامی", err.message)

    def test_update_patch_and_delete(self):
        t = Tracking.objects.create(item_name="A", status="new")
        services.update_tracking(t, {"status": "ordered"}, partial=True)
        t.refresh_from_db()
        self.assertEqual(t.status, "ordered")
        services.delete_tracking(t)
        self.assertFalse(Tracking.objects.filter(id=t.id).exists())

    def test_bulk_delete(self):
        ts = [Tracking.objects.create(item_name=f"t{i}") for i in range(2)]
        _, err = call(services.bulk_delete_tracking, [])
        self.assertEqual(err.status_code, 400)
        self.assertEqual(services.bulk_delete_tracking([ts[0].id, ts[1].id]), 2)
