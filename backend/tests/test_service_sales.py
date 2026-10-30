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
            paid_cash=100, payment_type="cash", is_settled=True)
        self.deposit = Sale.objects.create(
            product=self.p2, sale_price=200, purchase_price=50, profit=150,
            sale_date="2026-09-02", customer="Mary", customer_phone="09120000002",
            paid_cash=50, payment_type="deposit",
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

    def test_discount_payload_is_ignored(self):
        # Spec-002: there is no discount concept — the entered price stands.
        p = make_product()
        sale, _ = call(services.create_sale, sale_payload(
            p.id, discount_price="1400000"))
        self.assertEqual(sale.sale_price, 1_500_000)
        self.assertEqual(sale.profit, 500_000)

    def test_missing_price_rejected_saves_nothing(self):
        p = make_product()
        for payload in (sale_payload(p.id, sale_price=""),
                        sale_payload(p.id, sale_price="0")):
            _, err = call(services.create_sale, payload)
            self.assertEqual(err.status_code, 400)
            self.assertIn("قیمت فروش را وارد کنید", err.message)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertTrue(Product.objects.get(id=p.id).available)

    def test_validation_errors(self):
        p = make_product()
        cases = [
            (sale_payload(p.id, customer=""), "نام خریدار"),
            (sale_payload(p.id, customer_phone="123"), "شماره تماس"),
            (sale_payload(p.id, sale_price=""), "قیمت فروش را وارد کنید"),
            (sale_payload(p.id, sale_price="0"), "قیمت فروش را وارد کنید"),
            (sale_payload(p.id, paid_cash="99999999"), "قیمت فروش"),
            (sale_payload(99999), "محصول یافت نشد"),
            (sale_payload(None), "محصول انتخاب نشده است"),
            (sale_payload(p.id, sale_date="31/31/9999"), "تاریخ فروش"),
            (sale_payload(p.id, payment_type="deposit", paid_cash="0"),
             "بیعانه"),
            (sale_payload(p.id, paid_cash="500"), "برای فروش نقدی"),
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
            "sale_price": "1700000",
            "customer": "مریم", "notes": "edited",
        })
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.sale_price, 1700000)
        self.assertEqual(self.sale.profit, 700_000)
        self.assertEqual(self.sale.customer, "مریم")
        self.assertEqual(self.sale.notes, "edited")

    def test_update_overpayment_rejected_against_new_price(self):
        _, err = call(services.update_sale, self.sale,
                      {"sale_price": "1000000", "paid_cash": "2000000"})
        self.assertEqual(err.status_code, 400)
        self.assertIn("قیمت فروش", err.message)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.sale_price, 1500000)  # unchanged

    def test_update_deposit_price_syncs_receipt(self):
        # A2: the receipt mirrors the edited sale (paid amounts fall back to
        # the sale's current ones, so they are kept; the total follows the price)
        dep_sale = Sale.objects.filter(payment_type="deposit").first()
        receipt = Payment.objects.get(sale=dep_sale)
        services.update_sale(dep_sale, {"sale_price": "900000"})
        receipt.refresh_from_db()
        self.assertEqual(receipt.paid_amount, 500000)  # stored amount kept
        self.assertEqual(receipt.total_amount, 900000)
        dep_sale.refresh_from_db()
        self.assertEqual(dep_sale.sale_price, 900000)
        self.assertEqual(dep_sale.profit, -100000)     # 900000 - 1000000

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
        self.assertEqual(self.sale.sale_price, 1500000)

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


class SaleDepositReceiptSyncTests(TestCase):
    """A2: editing a deposit sale keeps its receipt and settlement in sync.

    Invariant — for every deposit sale:
    ``paid_cash+paid_pos+paid_card2card == receipt.paid_amount`` and
    ``receipt.total_amount == sale.sale_price``.
    """

    def setUp(self):
        self.p = make_product()
        self.deposit = services.create_sale(sale_payload(
            self.p.id, payment_type="deposit", sale_price="1500000",
            paid_cash="500000"))
        self.receipt = Payment.objects.get(sale=self.deposit)

    def assert_invariant(self, sale):
        sale.refresh_from_db()
        receipt = Payment.objects.get(sale=sale)
        paid_total = sale.paid_cash + sale.paid_pos + sale.paid_card2card
        self.assertEqual(paid_total, receipt.paid_amount)
        self.assertEqual(receipt.total_amount, sale.sale_price)

    def test_edit_price_buyer_and_paid_amounts_sync_receipt(self):
        services.update_sale(self.deposit, {
            "sale_price": "1800000",
            "paid_cash": "500000", "paid_pos": "300000",
            "customer": "مریم", "customer_phone": "09121112222",
        })
        self.deposit.refresh_from_db()
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.total_amount, 1800000)
        self.assertEqual(self.receipt.paid_amount, 800000)
        self.assertEqual(self.receipt.customer_name, "مریم")
        self.assertEqual(self.receipt.customer_phone, "09121112222")
        self.assertFalse(self.deposit.is_settled)
        self.assertIn("مانده", self.receipt.notes)
        self.assert_invariant(self.deposit)

    def test_edit_date_updates_receipt_pay_date(self):
        services.update_sale(self.deposit, {"sale_date": "1405/02/20"})
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.pay_date, "2026-05-10")

    def test_fully_paid_deposit_edit_marks_settled_on_both(self):
        services.update_sale(self.deposit, {"paid_cash": "1500000"})
        self.deposit.refresh_from_db()
        self.receipt.refresh_from_db()
        self.assertTrue(self.deposit.is_settled)
        self.assertEqual(self.deposit.settled_at, today_iso())
        self.assertEqual(self.receipt.settled_at, today_iso())
        self.assert_invariant(self.deposit)

    def test_price_raise_after_settlement_clears_the_stamp(self):
        services.update_sale(self.deposit, {"paid_cash": "1500000"})   # settle
        services.update_sale(self.deposit, {"sale_price": "2000000"})  # reopen
        self.deposit.refresh_from_db()
        self.receipt.refresh_from_db()
        self.assertFalse(self.deposit.is_settled)
        self.assertEqual(self.deposit.settled_at, "")
        self.assertEqual(self.receipt.settled_at, "")

    def test_cash_to_deposit_without_upfront_rejected(self):
        cash_sale = services.create_sale(sale_payload(
            make_product(office_code="OF-C2", website_code="WS-C2").id))
        _, err = call(services.update_sale, cash_sale, {
            "payment_type": "deposit",
            "paid_cash": "0", "paid_pos": "0", "paid_card2card": "0",
        })
        self.assertEqual(err.status_code, 400)
        self.assertIn("بیعانه", err.message)
        cash_sale.refresh_from_db()
        self.assertEqual(cash_sale.payment_type, "cash")
        self.assertFalse(Payment.objects.filter(sale=cash_sale).exists())

    def test_stay_deposit_edit_with_zero_paid_rejected(self):
        # F1: editing a deposit sale to zero paid used to pass and wipe the
        # receipt's paid_amount — same rejection as on create now
        dep_sale = services.create_sale(sale_payload(
            make_product(office_code="OF-Z1", website_code="WS-Z1").id,
            payment_type="deposit", paid_cash="500000"))
        receipt = Payment.objects.get(sale=dep_sale)
        _, err = call(services.update_sale, dep_sale, {
            "paid_cash": "0", "paid_pos": "0", "paid_card2card": "0"})
        self.assertEqual(err.status_code, 400)
        self.assertEqual(err.message, "برای فروش بیعانه، دست‌کم مبلغ بیعانه را وارد کنید")
        dep_sale.refresh_from_db()
        self.assertEqual(dep_sale.paid_cash, 500000)
        self.assertFalse(dep_sale.is_settled)
        receipt.refresh_from_db()
        self.assertEqual(receipt.paid_amount, 500000)

    def test_stay_deposit_edit_without_paid_fields_keeps_amount(self):
        # F1: omitting the paid fields still falls back to stored values
        dep_sale = services.create_sale(sale_payload(
            make_product(office_code="OF-Z2", website_code="WS-Z2").id,
            payment_type="deposit", paid_cash="500000"))
        services.update_sale(dep_sale, {"notes": "edit"})
        dep_sale.refresh_from_db()
        self.assertEqual(dep_sale.paid_cash, 500000)

    def test_cash_to_deposit_creates_receipt(self):
        cash_sale = services.create_sale(sale_payload(
            make_product(office_code="OF-C3", website_code="WS-C3").id))
        services.update_sale(cash_sale, {
            "payment_type": "deposit", "paid_cash": "600000"})
        cash_sale.refresh_from_db()
        receipt = Payment.objects.get(sale=cash_sale)
        self.assertEqual(cash_sale.payment_type, "deposit")
        self.assertFalse(cash_sale.is_settled)
        self.assertEqual(receipt.total_amount, 1500000)
        self.assertEqual(receipt.paid_amount, 600000)
        self.assertIn("بیعانه فروش", receipt.notes)
        self.assert_invariant(cash_sale)

    def test_cash_to_deposit_fully_paid_is_settled(self):
        cash_sale = services.create_sale(sale_payload(
            make_product(office_code="OF-C4", website_code="WS-C4").id))
        services.update_sale(cash_sale, {
            "payment_type": "deposit", "paid_cash": "1500000"})
        cash_sale.refresh_from_db()
        self.assertTrue(cash_sale.is_settled)
        receipt = Payment.objects.get(sale=cash_sale)
        self.assertEqual(receipt.paid_amount, receipt.total_amount)

    def test_deposit_to_cash_settles_remainder_into_paid_cash(self):
        services.update_sale(self.deposit, {"payment_type": "cash"})
        self.deposit.refresh_from_db()
        self.receipt.refresh_from_db()
        self.assertEqual(self.deposit.payment_type, "cash")
        self.assertEqual(self.deposit.paid_cash, 1500000)
        self.assertTrue(self.deposit.is_settled)
        self.assertEqual(self.deposit.settled_at, today_iso())
        self.assertEqual(self.receipt.total_amount, 1500000)
        self.assertEqual(self.receipt.paid_amount, 1500000)
        self.assertEqual(self.receipt.settled_at, today_iso())

    def test_manual_receipt_note_is_preserved(self):
        self.receipt.notes = "یادداشت دستی فقره"
        self.receipt.save(update_fields=["notes"])
        services.update_sale(self.deposit, {"sale_price": "1700000"})
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.notes, "یادداشت دستی فقره")

    def test_auto_receipt_note_refreshes_remaining(self):
        from inventory.utils import fa_money
        services.update_sale(self.deposit, {"sale_price": "1700000"})
        self.receipt.refresh_from_db()
        self.assertIn(fa_money(1200000), self.receipt.notes)
        self.assertIn(f"#{self.deposit.id}", self.receipt.notes)

    def test_deposit_fully_paid_at_creation_is_settled(self):
        p = make_product(office_code="OF-FP", website_code="WS-FP")
        sale, err = call(services.create_sale, sale_payload(
            p.id, payment_type="deposit", sale_price="1500000",
            paid_cash="1500000"))
        self.assertIsNone(err)
        self.assertTrue(sale.is_settled)
        receipt = Payment.objects.get(sale=sale)
        self.assertEqual(receipt.settled_at, today_iso())

    def test_cash_partial_breakdown_by_edit_rejected(self):
        # A4: a partial breakdown on a cash sale is rejected — «بیعانه» instead
        cash_sale = services.create_sale(sale_payload(
            make_product(office_code="OF-UP", website_code="WS-UP").id))
        _, err = call(services.update_sale, cash_sale, {
            "paid_cash": "500000", "paid_pos": "500000"})
        self.assertEqual(err.status_code, 400)
        self.assertIn("نقدی", err.message)
        cash_sale.refresh_from_db()
        self.assertEqual(cash_sale.paid_cash, 1500000)  # unchanged
        self.assertTrue(cash_sale.is_settled)


class SaleCashFullPaymentTests(TestCase):
    """A4: a cash sale must be paid in full — partial = «بیعانه» instead."""

    def test_create_cash_partial_breakdown_rejected(self):
        p = make_product()
        sale, err = call(services.create_sale, sale_payload(
            p.id, sale_price="2000000", paid_cash="500000"))
        self.assertEqual(err.status_code, 400)
        self.assertIn("برای فروش نقدی", err.message)
        self.assertIn("بیعانه", err.message)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertTrue(Product.objects.get(id=p.id).available)

    def test_create_cash_full_breakdown_accepted(self):
        p = make_product()
        sale, err = call(services.create_sale, sale_payload(
            p.id, sale_price="2000000", paid_cash="500000",
            paid_pos="1500000"))
        self.assertIsNone(err)
        self.assertTrue(sale.is_settled)
        self.assertEqual((sale.paid_cash, sale.paid_pos), (500000.0, 1500000.0))

    def test_create_cash_without_breakdown_still_all_cash(self):
        p = make_product()
        sale, _ = call(services.create_sale, sale_payload(p.id))
        self.assertEqual(sale.paid_cash, 1500000)

    def test_update_price_change_with_stale_breakdown_resets_to_all_cash(self):
        cash_sale = services.create_sale(sale_payload(
            make_product(office_code="OF-RS", website_code="WS-RS").id))
        services.update_sale(cash_sale, {"sale_price": "2000000"})
        cash_sale.refresh_from_db()
        self.assertEqual(cash_sale.sale_price, 2000000)
        self.assertEqual(cash_sale.paid_cash, 2000000)  # reset, was 1500000
        self.assertEqual(cash_sale.paid_pos, 0)
        self.assertTrue(cash_sale.is_settled)

    def test_update_price_change_with_matching_breakdown_kept(self):
        cash_sale = services.create_sale(sale_payload(
            make_product(office_code="OF-MB", website_code="WS-MB").id,
            paid_cash="0", paid_pos="1500000"))
        services.update_sale(cash_sale, {"sale_price": "2000000",
                                         "paid_pos": "2000000"})
        cash_sale.refresh_from_db()
        self.assertEqual(cash_sale.paid_pos, 2000000)
        self.assertEqual(cash_sale.paid_cash, 0)
        self.assertTrue(cash_sale.is_settled)

    def test_update_explicit_partial_breakdown_rejected(self):
        cash_sale = services.create_sale(sale_payload(
            make_product(office_code="OF-EP", website_code="WS-EP").id))
        _, err = call(services.update_sale, cash_sale, {
            "paid_cash": "500000", "paid_pos": "500000"})
        self.assertEqual(err.status_code, 400)
        self.assertIn("برای فروش نقدی", err.message)
        cash_sale.refresh_from_db()
        self.assertEqual(cash_sale.paid_cash, 1500000)
        self.assertTrue(cash_sale.is_settled)

    def test_legacy_partial_cash_row_rejected_on_edit(self):
        # a cash sale stored by the old buggy behaviour cannot be edited
        # until its amounts are fixed (or it becomes a deposit)
        p = make_product(office_code="OF-LG", website_code="WS-LG")
        legacy = Sale.objects.create(
            product=p, sale_price=2000, purchase_price=1000, profit=1000,
            sale_date=today_iso(), customer="x", customer_phone="09123456789",
            paid_cash=500, payment_type="cash", is_settled=True)
        _, err = call(services.update_sale, legacy, {"notes": "edit"})
        self.assertEqual(err.status_code, 400)
        self.assertIn("برای فروش نقدی", err.message)
        legacy.refresh_from_db()
        self.assertEqual(legacy.paid_cash, 500)

    def test_legacy_partial_cash_row_fixed_by_full_breakdown(self):
        p = make_product(office_code="OF-L2", website_code="WS-L2")
        legacy = Sale.objects.create(
            product=p, sale_price=2000, purchase_price=1000, profit=1000,
            sale_date=today_iso(), customer="x", customer_phone="09123456789",
            paid_cash=500, payment_type="cash", is_settled=True)
        services.update_sale(legacy, {"paid_cash": "2000", "paid_pos": "0"})
        legacy.refresh_from_db()
        self.assertEqual(legacy.paid_cash, 2000)
        self.assertTrue(legacy.is_settled)


def _legacy_sale(product, customer, phone):
    """A bare sale row, as created by the old double-sell bug (A7)."""
    return Sale.objects.create(
        product=product, sale_price=2000, purchase_price=1000, profit=1000,
        sale_date=today_iso(), customer=customer, customer_phone=phone,
        paid_cash=2000, payment_type="cash", is_settled=True)


class SaleAlreadySoldGuardTests(TestCase):
    """A7: a sold watch cannot be sold again (stale tab / direct API call),
    and deleting one of several legacy sales keeps the watch sold."""

    def test_second_sale_for_sold_product_rejected(self):
        p = make_product(office_code="OF-G1", website_code="WS-G1")
        services.create_sale(sale_payload(p.id))
        _, err = call(services.create_sale, sale_payload(p.id))
        self.assertEqual(err.status_code, 400)
        self.assertIn("فروخته شده", err.message)
        self.assertEqual(Sale.objects.count(), 1)
        p.refresh_from_db()
        self.assertFalse(p.available)

    def test_delete_single_sale_restores_stock(self):
        p = make_product(office_code="OF-G3", website_code="WS-G3")
        sale = services.create_sale(sale_payload(p.id))
        services.delete_sale(sale)
        p.refresh_from_db()
        self.assertTrue(p.available)

    def test_delete_one_of_two_legacy_sales_keeps_watch_sold(self):
        p = make_product(office_code="OF-G4", website_code="WS-G4")
        p.available = False
        p.save(update_fields=["available"])
        s1 = _legacy_sale(p, "علی", "09120000001")
        _legacy_sale(p, "رضا", "09120000002")

        services.delete_sale(s1)
        p.refresh_from_db()
        self.assertFalse(p.available)  # the second sale still owns it
        self.assertEqual(Sale.objects.filter(product=p).count(), 1)

        services.delete_sale(Sale.objects.get(product=p))
        p.refresh_from_db()
        self.assertTrue(p.available)

    def test_bulk_delete_frees_only_watches_without_remaining_sales(self):
        sold_twice = make_product(office_code="OF-G5", website_code="WS-G5")
        sold_twice.available = False
        sold_twice.save(update_fields=["available"])
        s1 = _legacy_sale(sold_twice, "علی", "09120000001")
        s2 = _legacy_sale(sold_twice, "رضا", "09120000002")
        once = make_product(office_code="OF-G6", website_code="WS-G6")
        once.available = False
        once.save(update_fields=["available"])
        s3 = _legacy_sale(once, "مریم", "09120000003")

        n = services.bulk_delete_sales([s1.id, s3.id])
        self.assertEqual(n, 2)
        sold_twice.refresh_from_db()
        once.refresh_from_db()
        self.assertFalse(sold_twice.available)  # s2 still references it
        self.assertTrue(once.available)

        services.bulk_delete_sales([s2.id])
        sold_twice.refresh_from_db()
        self.assertTrue(sold_twice.available)

    def test_watch_becomes_sellable_again_after_deleting_its_sale(self):
        p = make_product(office_code="OF-G7", website_code="WS-G7")
        sale = services.create_sale(sale_payload(p.id))
        _, err = call(services.create_sale, sale_payload(p.id))
        self.assertEqual(err.status_code, 400)

        services.delete_sale(sale)
        second, err = call(services.create_sale, sale_payload(p.id))
        self.assertIsNone(err)
        self.assertEqual(Sale.objects.filter(product=p).count(), 1)
        self.assertFalse(Product.objects.get(id=p.id).available)


class InvoiceCodePersistenceTests(TestCase):
    """B1: the auto invoice code is stored at creation and never changes."""

    def test_auto_code_persisted_and_edit_keeps_it(self):
        p = make_product(office_code="OF-B1", website_code="WS-B1")
        sale = services.create_sale(sale_payload(p.id, sale_date="2026-09-10"))
        # 2026-09-10 = ۱۹ شهریور ۱۴۰۵
        self.assertEqual(sale.invoice_code, f"TT-140506-{sale.id:04d}")

        services.update_sale(sale, {"sale_date": "2026-08-01"})
        sale.refresh_from_db()
        self.assertEqual(sale.sale_date, "2026-08-01")
        # the code must not change when the date is edited
        self.assertEqual(sale.invoice_code, f"TT-140506-{sale.id:04d}")

    def test_manual_code_stored(self):
        p = make_product(office_code="OF-B1M", website_code="WS-B1M")
        sale = services.create_sale(sale_payload(
            p.id, invoice_code="MY-INV-1"))
        self.assertEqual(sale.invoice_code, "MY-INV-1")
        p2 = make_product(office_code="OF-B1M2", website_code="WS-B1M2")
        _, err = call(services.create_sale, sale_payload(
            p2.id, invoice_code="MY-INV-1"))
        self.assertEqual(err.status_code, 400)

    def test_manual_code_matching_stored_auto_code_rejected(self):
        p = make_product(office_code="OF-B1A", website_code="WS-B1A")
        auto = services.create_sale(sale_payload(p.id))
        p2 = make_product(office_code="OF-B1B", website_code="WS-B1B")
        _, err = call(services.create_sale, sale_payload(
            p2.id, invoice_code=auto.invoice_code))
        self.assertEqual(err.status_code, 400)
        self.assertIn("قبلاً استفاده شده", err.message)

    def test_auto_code_suffixed_when_a_manual_code_took_the_slot(self):
        # F3: sale A (created earlier) holds a manual code equal to what a
        # later sale in the same month computes for itself — the auto code
        # gets a numeric suffix instead of duplicating
        p1 = make_product(office_code="OF-F3A", website_code="WS-F3A")
        a = services.create_sale(sale_payload(p1.id, sale_date="2026-09-10"))
        # sale C will get id a.id + 2; sale B claims that code manually
        # (legal at creation time — no sale owns it yet)
        taken_code = f"TT-140506-{a.id + 2:04d}"
        p2 = make_product(office_code="OF-F3B", website_code="WS-F3B")
        b = services.create_sale(sale_payload(
            p2.id, sale_date="2026-09-10", invoice_code=taken_code))
        self.assertEqual(b.invoice_code, taken_code)
        p3 = make_product(office_code="OF-F3C", website_code="WS-F3C")
        c = services.create_sale(sale_payload(p3.id, sale_date="2026-09-10"))
        # c.id == a.id + 2 → its natural code is taken → "-2"
        self.assertEqual(c.id, a.id + 2)
        self.assertEqual(c.invoice_code, f"{taken_code}-2")
        codes = list(Sale.objects.values_list("invoice_code", flat=True))
        self.assertEqual(len(codes), len(set(codes)))  # all unique

    def test_next_code_preview_uses_the_chosen_date(self):
        p = make_product(office_code="OF-B1C", website_code="WS-B1C")
        sale = services.create_sale(sale_payload(p.id, sale_date="2026-09-10"))
        # next id = last sale id + 1; month comes from the given Jalali date
        self.assertEqual(services.next_invoice_code("1405/05/01"),
                         f"TT-140505-{sale.id + 1:04d}")
        self.assertEqual(services.next_invoice_code("2026-08-01"),
                         f"TT-140505-{sale.id + 1:04d}")
        # without a date it falls back to today
        self.assertTrue(services.next_invoice_code().startswith("TT-"))

    def test_next_code_endpoint_accepts_sale_date_param(self):
        p = make_product(office_code="OF-B1D", website_code="WS-B1D")
        sale = services.create_sale(sale_payload(p.id, sale_date="2026-09-10"))
        r = self.client.get("/api/sales",
                            {"next_code": 1, "sale_date": "1405/05/01"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["next_invoice_code"],
                         f"TT-140505-{sale.id + 1:04d}")

    def test_backfill_migration_codes_empty_rows_only(self):
        import importlib

        from django.apps import apps

        mig = importlib.import_module(
            "inventory.migrations.0009_backfill_sale_invoice_codes")
        p = make_product(office_code="OF-B1E", website_code="WS-B1E")
        old = Sale.objects.create(
            product=p, sale_price=2000, purchase_price=1000, profit=1000,
            sale_date="2026-09-10", customer="x", customer_phone="09120000001",
            paid_cash=2000, payment_type="cash", is_settled=True)  # no code
        manual = Sale.objects.create(
            product=p, sale_price=2000, purchase_price=1000, profit=1000,
            sale_date="2026-09-11", customer="y", customer_phone="09120000002",
            paid_cash=2000, payment_type="cash", is_settled=True,
            invoice_code="KEEP-ME")
        nodate = Sale.objects.create(
            product=p, sale_price=2000, purchase_price=1000, profit=1000,
            sale_date="", customer="z", customer_phone="09120000003",
            paid_cash=2000, payment_type="cash", is_settled=True)

        mig.backfill_sale_codes(apps, None)

        old.refresh_from_db()
        manual.refresh_from_db()
        nodate.refresh_from_db()
        self.assertEqual(old.invoice_code, f"TT-140506-{old.id:04d}")
        self.assertEqual(manual.invoice_code, "KEEP-ME")
        self.assertEqual(nodate.invoice_code, f"TT-{nodate.id:04d}")
        # running it again changes nothing (idempotent)
        mig.backfill_sale_codes(apps, None)
        old.refresh_from_db()
        self.assertEqual(old.invoice_code, f"TT-140506-{old.id:04d}")
