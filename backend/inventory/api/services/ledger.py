# -*- coding: utf-8 -*-
"""Supplier purchase ledger (حساب معین) — business rules.

A fully independent archival subsystem: imports ONLY the ledger models,
``inventory.jalali`` (via ``.common``), ``inventory.utils``, and ``.common``.
No product/sale/payment/repair/tracking/settings/report module is touched.
"""

from django.db import transaction
from django.db.models import Count

from inventory.models import (
    LedgerInvoice, LedgerInvoiceImage, LedgerLineItem, LedgerSupplier,
)
from inventory.utils import clean, remove_image, to_float, to_int

from .common import ApiError, _parse_iso_or_raise


# ------------------------------------------------------------------- reads
def ledger_suppliers_list():
    """Suppliers ordered by name ascending, each annotated with invoice_count."""
    return LedgerSupplier.objects.annotate(
        invoice_count=Count("invoices")).order_by("name")


def ledger_supplier_or_404(supplier_id):
    supplier = LedgerSupplier.objects.filter(id=to_int(supplier_id)).first()
    if supplier is None:
        raise ApiError(404, "یافت نشد")
    return supplier


def ledger_invoices_list(supplier_id):
    """Invoice rows for one supplier (404 ``یافت نشد`` for an unknown one).

    Ordered purchase_date desc, then id desc — newest invoices first.
    """
    supplier = ledger_supplier_or_404(supplier_id)
    return LedgerInvoice.objects.filter(supplier=supplier)\
        .order_by("-purchase_date", "-id")


def ledger_invoice_or_404(invoice_id):
    invoice = LedgerInvoice.objects.filter(id=to_int(invoice_id)).first()
    if invoice is None:
        raise ApiError(404, "یافت نشد")
    return invoice


# --------------------------------------------------------------- suppliers
def create_supplier(payload):
    name = clean((payload or {}).get("name"))
    if not name:
        raise ApiError(400, "نام تأمین‌کننده خالی است")
    if LedgerSupplier.objects.filter(name=name).exists():
        raise ApiError(400, "این تأمین‌کننده قبلاً ثبت شده است")
    return LedgerSupplier.objects.create(name=name)


def rename_supplier(supplier, payload):
    name = clean((payload or {}).get("name"))
    if not name:
        raise ApiError(400, "نام تأمین‌کننده خالی است")
    if LedgerSupplier.objects.filter(name=name)\
            .exclude(id=supplier.id).exists():
        raise ApiError(400, "این تأمین‌کننده قبلاً ثبت شده است")
    supplier.name = name
    supplier.save()
    return supplier


def delete_supplier(supplier):
    """Remove the supplier with full cascade: invoices, lines, and photo files."""
    files = set(LedgerInvoiceImage.objects.filter(
        invoice__supplier=supplier).values_list("filename", flat=True))
    LedgerInvoice.objects.filter(supplier=supplier).delete()
    supplier.delete()
    for fname in files:
        remove_image(fname)


# ------------------------------------------------------------------ shared
def _images_from_payload(payload):
    """The ordered ``images`` array (position = page order).

    ``None`` when the key is absent (⇒ keep the current photo set), ``[]``
    for no photos, and ``ApiError(400, عکس معتبر نیست)`` on a blank or
    non-string entry.
    """
    raw = (payload or {}).get("images")
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ApiError(400, "عکس معتبر نیست")
    out = []
    for entry in raw:
        if not isinstance(entry, str) or not entry.strip():
            raise ApiError(400, "عکس معتبر نیست")
        out.append(entry.strip())
    return out


def _lines_from_payload(payload):
    """Normalize the submitted line list (unbounded in length).

    Blank/missing/0/non-numeric quantity ⇒ 1; negative unit price ⇒ 0.
    """
    raw = (payload or {}).get("lines")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ApiError(400, "نام ساعت را وارد کنید")
    rows = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ApiError(400, "نام ساعت را وارد کنید")
        name = clean(entry.get("watch_name"))
        if not name:
            raise ApiError(400, "نام ساعت را وارد کنید")
        quantity = to_int(entry.get("quantity")) or 1
        unit_price = max(0.0, to_float(entry.get("unit_price")))
        rows.append((name, clean(entry.get("reference")), quantity, unit_price))
    return rows


# ------------------------------------------------------------- invoices
def create_invoice(payload):
    payload = payload or {}
    supplier = LedgerSupplier.objects.filter(
        id=to_int(payload.get("supplier_id"))).first()
    if supplier is None:
        raise ApiError(404, "تأمین‌کننده یافت نشد")
    iso = _parse_iso_or_raise(payload.get("purchase_date"), "تاریخ معتبر نیست")
    images = _images_from_payload(payload) or []
    rows = _lines_from_payload(payload)
    with transaction.atomic():
        invoice = LedgerInvoice.objects.create(
            supplier=supplier, purchase_date=iso)
        if rows:
            LedgerLineItem.objects.bulk_create([
                LedgerLineItem(invoice=invoice, watch_name=n, reference=r,
                               quantity=q, unit_price=p)
                for n, r, q, p in rows])
        if images:
            LedgerInvoiceImage.objects.bulk_create([
                LedgerInvoiceImage(invoice=invoice, filename=f, order=i)
                for i, f in enumerate(images)])
    return invoice


def update_invoice(invoice, payload):
    """Full-replace edit in one transaction: date, photos, and the line set.

    Omitted keys keep their current values; ``lines``/``images`` present ⇒
    the whole set is replaced (add / edit / remove / reorder / clear).
    """
    payload = payload or {}
    new_date = None
    if "purchase_date" in payload:
        new_date = _parse_iso_or_raise(
            payload.get("purchase_date"), "تاریخ معتبر نیست")
    images = _images_from_payload(payload)
    rows = None
    if "lines" in payload:
        rows = _lines_from_payload(payload)
    with transaction.atomic():
        if new_date is not None:
            invoice.purchase_date = new_date
            invoice.save()
        if images is not None:
            old_files = set(invoice.images.values_list("filename", flat=True))
            invoice.images.all().delete()
            if images:
                invoice.images.bulk_create([
                    LedgerInvoiceImage(invoice=invoice, filename=f, order=i)
                    for i, f in enumerate(images)])
            for fname in old_files:
                if fname not in images:
                    remove_image(fname)
        if rows is not None:
            invoice.lines.all().delete()
            if rows:
                invoice.lines.bulk_create([
                    LedgerLineItem(invoice=invoice, watch_name=n, reference=r,
                                   quantity=q, unit_price=p)
                    for n, r, q, p in rows])
    return invoice


def delete_invoice(invoice):
    """Remove the invoice, its line items, its image rows, and their files."""
    files = set(invoice.images.values_list("filename", flat=True))
    invoice.delete()
    for fname in files:
        remove_image(fname)