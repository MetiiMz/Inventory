# -*- coding: utf-8 -*-
"""Tests for the ledger (supplier purchase records) service functions."""
from django.test import TestCase

from inventory.api import services
from inventory.models import (
    LedgerInvoice, LedgerInvoiceImage, LedgerLineItem, LedgerSupplier,
)


def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except services.ApiError as exc:
        return None, exc


class LedgerSupplierServiceTests(TestCase):
    """supplier create (blank / duplicate stripped name)."""

    def test_create_stores_stripped_name(self):
        s, err = call(services.create_supplier, {"name": "  امید ساعت  "})
        self.assertIsNone(err)
        self.assertEqual(s.name, "امید ساعت")
        self.assertTrue(LedgerSupplier.objects.filter(
            id=s.id, name="امید ساعت").exists())

    def test_create_blank_name(self):
        _, err = call(services.create_supplier, {"name": "   "})
        self.assertEqual(err.status_code, 400)
        self.assertEqual(err.message, "نام تأمین‌کننده خالی است")
        self.assertEqual(LedgerSupplier.objects.count(), 0)

    def test_create_duplicate_stripped_name(self):
        call(services.create_supplier, {"name": "آبان"})
        _, err = call(services.create_supplier, {"name": " آبان "})
        self.assertEqual(err.status_code, 400)
        self.assertEqual(err.message, "این تأمین‌کننده قبلاً ثبت شده است")
        self.assertEqual(LedgerSupplier.objects.count(), 1)


class LedgerInvoiceCreateServiceTests(TestCase):
    """invoice create — unknown supplier, date, lines, photos, totals."""

    def setUp(self):
        self.supplier, _ = call(services.create_supplier, {"name": "تست"})

    def test_create_unknown_supplier(self):
        _, err = call(services.create_invoice, {
            "supplier_id": 999999, "purchase_date": "1405/03/31"})
        self.assertEqual(err.status_code, 404)
        self.assertEqual(err.message, "تأمین‌کننده یافت نشد")
        _, err = call(services.create_invoice, {"purchase_date": "1405/03/31"})
        self.assertEqual(err.status_code, 404)
        self.assertEqual(LedgerInvoice.objects.count(), 0)

    def test_create_invalid_date(self):
        _, err = call(services.create_invoice, {
            "supplier_id": self.supplier.id, "purchase_date": "xx"})
        self.assertEqual(err.status_code, 400)
        self.assertEqual(err.message, "تاریخ معتبر نیست")
        self.assertEqual(LedgerInvoice.objects.count(), 0)

    def test_create_requires_watch_name(self):
        _, err = call(services.create_invoice, {
            "supplier_id": self.supplier.id, "purchase_date": "1405/03/31",
            "lines": [{"watch_name": "  ", "unit_price": "1000"}]})
        self.assertEqual(err.status_code, 400)
        self.assertEqual(err.message, "نام ساعت را وارد کنید")
        self.assertEqual(LedgerInvoice.objects.count(), 0)
        self.assertEqual(LedgerLineItem.objects.count(), 0)

    def test_create_zero_line_invoice(self):
        inv, err = call(services.create_invoice, {
            "supplier_id": self.supplier.id, "purchase_date": "1405/03/31"})
        self.assertIsNone(err)
        self.assertEqual(LedgerLineItem.objects.count(), 0)
        self.assertEqual(inv.lines.count(), 0)

    def test_blank_and_zero_quantity_stored_as_one(self):
        inv, err = call(services.create_invoice, {
            "supplier_id": self.supplier.id, "purchase_date": "2026-06-21",
            "lines": [
                {"watch_name": "A", "quantity": "", "unit_price": "1000000"},
                {"watch_name": "B", "quantity": 0, "unit_price": "2000000"},
                {"watch_name": "C", "unit_price": "3"},
            ]})
        self.assertIsNone(err)
        self.assertEqual(
            list(inv.lines.order_by("id").values_list("quantity", flat=True)),
            [1, 1, 1])

    def test_zero_photo_invoice_allowed(self):
        inv, err = call(services.create_invoice, {
            "supplier_id": self.supplier.id, "purchase_date": "1405/03/31",
            "lines": [{"watch_name": "A", "unit_price": "1"}]})
        self.assertIsNone(err)
        self.assertEqual(LedgerInvoiceImage.objects.count(), 0)

    def test_images_array_creates_ordered_rows(self):
        inv, err = call(services.create_invoice, {
            "supplier_id": self.supplier.id, "purchase_date": "1405/03/31",
            "images": ["page1.jpg", "page2.jpg", "page3.jpg"]})
        self.assertIsNone(err)
        self.assertEqual(
            list(inv.images.order_by("order").values_list("filename", "order")),
            [("page1.jpg", 0), ("page2.jpg", 1), ("page3.jpg", 2)])

    def test_bad_image_entry_rejects_without_partial_rows(self):
        _, err = call(services.create_invoice, {
            "supplier_id": self.supplier.id, "purchase_date": "1405/03/31",
            "images": ["ok.jpg", ""],
            "lines": [{"watch_name": "A", "unit_price": "1"}]})
        self.assertEqual(err.status_code, 400)
        self.assertEqual(err.message, "عکس معتبر نیست")
        self.assertEqual(LedgerInvoice.objects.count(), 0)
        self.assertEqual(LedgerLineItem.objects.count(), 0)
        self.assertEqual(LedgerInvoiceImage.objects.count(), 0)

    def test_totals_match_hand_computed_mixed_fixture(self):
        inv, err = call(services.create_invoice, {
            "supplier_id": self.supplier.id, "purchase_date": "1405/03/31",
            "lines": [
                {"watch_name": "A", "quantity": 2, "unit_price": "3000000"},
                {"watch_name": "B", "quantity": "", "unit_price": "3500000"},
                {"watch_name": "C", "quantity": "4", "unit_price": "1000"},
            ]})
        self.assertIsNone(err)
        lines = list(inv.lines.order_by("id"))
        self.assertEqual(lines[0].quantity * lines[0].unit_price, 6000000.0)
        total_amount = sum(l.quantity * l.unit_price for l in lines)
        self.assertEqual(total_amount, 6000000.0 + 3500000.0 + 4000.0)
        # the serializer recomputes the same values — never a stored column
        from inventory.utils import ledger_invoice_dict
        d = ledger_invoice_dict(inv, with_lines=True)
        self.assertEqual(d["total_amount"], total_amount)
        self.assertEqual(d["total_quantity"], 7)
        self.assertEqual(d["lines"][0]["line_total"], 6000000.0)


class LedgerUpdateServiceTests(TestCase):
    """PUT semantics: omitted keys keep their values; present keys are
    fully replaced (lines / images), date is swapped."""

    def setUp(self):
        self.supplier, _ = call(services.create_supplier, {"name": "تست"})
        self.inv, _ = call(services.create_invoice, {
            "supplier_id": self.supplier.id, "purchase_date": "2026-06-21",
            "lines": [
                {"watch_name": "A", "quantity": 2, "unit_price": "1000"},
            ],
        })

    def test_update_replaces_lines_keeps_date(self):
        inv, err = call(services.update_invoice, self.inv, {
            "lines": [
                {"watch_name": "X", "quantity": "3", "unit_price": "5"},
                {"watch_name": "Y", "unit_price": "7"},
            ]})
        self.assertIsNone(err)
        self.assertEqual(inv.purchase_date, "2026-06-21")
        lines = list(LedgerLineItem.objects.filter(invoice=self.inv)
                     .order_by("id"))
        self.assertEqual([l.watch_name for l in lines], ["X", "Y"])
        self.assertEqual((lines[0].quantity, lines[1].quantity), (3, 1))
        self.assertEqual(lines[0].unit_price, 5.0)

    def test_update_replaces_date_keeps_lines(self):
        inv, err = call(services.update_invoice, self.inv,
                        {"purchase_date": "1405/03/31"})
        self.assertIsNone(err)
        self.assertEqual(inv.purchase_date, "2026-06-21")  # contract pair
        inv, err = call(services.update_invoice, self.inv,
                        {"purchase_date": "2027-01-15"})
        self.assertIsNone(err)
        self.assertEqual(inv.purchase_date, "2027-01-15")
        self.assertEqual(LedgerLineItem.objects.filter(invoice=self.inv).count(), 1)

    def test_update_replaces_images_in_order(self):
        inv, err = call(services.update_invoice, self.inv,
                        {"images": ["c.jpg", "a.jpg", "b.jpg"]})
        self.assertIsNone(err)
        self.assertEqual(
            list(inv.images.order_by("order").values_list("filename", flat=True)),
            ["c.jpg", "a.jpg", "b.jpg"])

    def test_update_invalid_date_rejected_without_changes(self):
        _, err = call(services.update_invoice, self.inv, {"purchase_date": "xx"})
        self.assertEqual(err.status_code, 400)
        self.assertEqual(err.message, "تاریخ معتبر نیست")
        self.assertEqual(self.inv.purchase_date, "2026-06-21")

    def test_update_blank_line_name_rejected_without_partial_rows(self):
        _, err = call(services.update_invoice, self.inv, {
            "lines": [{"watch_name": "  ", "unit_price": "1"}]})
        self.assertEqual(err.status_code, 400)
        self.assertEqual(err.message, "نام ساعت را وارد کنید")
        lines = list(LedgerLineItem.objects.filter(invoice=self.inv)
                     .values_list("watch_name", flat=True))
        self.assertEqual(lines, ["A"])


class LedgerDeleteServiceTests(TestCase):
    """Destructive deletes with server-side file cleanup (FR-010)."""

    def setUp(self):
        import os
        from django.conf import settings
        self.IMG_DIR = settings.IMG_DIR
        os.makedirs(self.IMG_DIR, exist_ok=True)
        self.supplier, _ = call(services.create_supplier, {"name": "تست"})

    def _make_file(self, fname):
        import os
        p = os.path.join(self.IMG_DIR, fname)
        with open(p, "wb") as fh:
            fh.write(b"fake-image-bytes")
        return p

    def test_update_clears_images_and_removes_files(self):
        import os
        fname = "ledgertest_gone.jpg"
        p = self._make_file(fname)
        inv, _ = call(services.create_invoice, {
            "supplier_id": self.supplier.id, "purchase_date": "2026-06-21",
            "images": [fname],
            "lines": [{"watch_name": "A", "unit_price": "1"}]})
        done, err = call(services.update_invoice, inv, {"images": []})
        self.assertIsNone(err)
        self.assertEqual(inv.images.count(), 0)
        self.assertFalse(os.path.exists(p))

    def test_update_keeps_files_still_referenced_removes_others(self):
        import os
        keep, drop = "ledgertest_keep.jpg", "ledgertest_drop.jpg"
        pk, pd = self._make_file(keep), self._make_file(drop)
        inv, _ = call(services.create_invoice, {
            "supplier_id": self.supplier.id, "purchase_date": "2026-06-21",
            "images": [drop, keep],
            "lines": [{"watch_name": "A", "unit_price": "1"}]})
        done, err = call(services.update_invoice, inv, {"images": [keep]})
        self.assertIsNone(err)
        self.assertTrue(os.path.exists(pk))
        self.assertFalse(os.path.exists(pd))
        self.assertEqual(list(inv.images.order_by("order")
                              .values_list("filename", flat=True)), [keep])
        if os.path.exists(pk):
            os.remove(pk)

    def test_delete_invoice_removes_rows_and_files(self):
        import os
        from inventory.models import LedgerSupplier
        fname = "ledgertest_inv_file.jpg"
        p = self._make_file(fname)
        inv, _ = call(services.create_invoice, {
            "supplier_id": self.supplier.id, "purchase_date": "2026-06-21",
            "images": [fname],
            "lines": [{"watch_name": "A", "unit_price": "1"}]})
        deleted, err = call(services.delete_invoice, inv)
        self.assertIsNone(err)
        inv_id = inv.id
        self.assertFalse(LedgerInvoice.objects.filter(id=inv_id).exists())
        self.assertEqual(LedgerLineItem.objects.filter(invoice_id=inv_id).count(), 0)
        self.assertEqual(LedgerInvoiceImage.objects.filter(invoice_id=inv_id).count(), 0)
        self.assertFalse(os.path.exists(p))
        self.assertTrue(LedgerSupplier.objects.filter(id=self.supplier.id).exists())

    def test_delete_supplier_full_cascade(self):
        import os
        fname = "ledgertest_cascade.jpg"
        p = self._make_file(fname)
        call(services.create_invoice, {
            "supplier_id": self.supplier.id, "purchase_date": "2026-06-21",
            "images": [fname],
            "lines": [{"watch_name": "A", "unit_price": "1"}]})
        call(services.create_invoice, {
            "supplier_id": self.supplier.id, "purchase_date": "2026-07-01",
            "lines": [{"watch_name": "B", "quantity": 2, "unit_price": "3"}]})
        self.assertEqual(LedgerInvoice.objects.filter(supplier=self.supplier).count(), 2)
        deleted, err = call(services.delete_supplier, self.supplier)
        self.assertIsNone(err)
        self.assertFalse(LedgerSupplier.objects.filter(id=self.supplier.id).exists())
        self.assertEqual(LedgerInvoice.objects.count(), 0)
        self.assertEqual(LedgerLineItem.objects.count(), 0)
        self.assertEqual(LedgerInvoiceImage.objects.count(), 0)
        self.assertFalse(os.path.exists(p))