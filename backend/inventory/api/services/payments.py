# -*- coding: utf-8 -*-
"""Payment domain: query, receipts, add installments, settlement, bulk-delete."""

from django.db import transaction
from django.db.models import F, Q, QuerySet

from inventory.jalali import today_iso
from inventory.models import Payment, Product, Sale
from inventory.utils import clean, fa_money, fa_num, to_float, to_int

from .common import (
    ApiError, PAID_METHOD_FIELDS, _clean_ids, _merge_partial, _parse_iso_or_raise,
)
from .sales import _sync_settlement


_PAYMENT_WRITE_FIELDS = (
    "product_name", "customer_name", "customer_phone", "total_amount",
    "paid_amount", "pay_date", "notes",
)


def payment_queryset(params) -> QuerySet:
    """Filtered payment list.

    Parameters: ``status`` = ``unpaid`` | ``paid`` (any other value means
    all) and ``q`` (product/customer name or phone).
    """
    status = clean(params.get("status", ""))
    q = clean(params.get("q", ""))
    qs = Payment.objects.select_related("product").all()
    if status == "unpaid":
        qs = qs.filter(total_amount__gt=F("paid_amount") + 0.001)
    elif status == "paid":
        qs = qs.filter(total_amount__lte=F("paid_amount") + 0.001)
    if q:
        qs = qs.filter(
            Q(product_name__icontains=q) | Q(customer_name__icontains=q)
            | Q(customer_phone__icontains=q))
    return qs.order_by("-id")


def create_payment(payload) -> Payment:
    """Create a standalone payment record (optionally linked to a product)."""
    pid = to_int(payload.get("product_id")) or None
    product_name = clean(payload.get("product_name"))
    if pid:
        name = Product.objects.filter(id=pid).values_list("name", flat=True).first()
        if not name:
            raise ApiError(400, "محصول انتخاب‌شده یافت نشد")
        product_name = name
    if not product_name:
        raise ApiError(400, "نام محصول را وارد یا از انبار انتخاب کنید")
    total = max(0.0, to_float(payload.get("total_amount")))
    paid = max(0.0, to_float(payload.get("paid_amount")))
    if total <= 0:
        raise ApiError(400, "مبلغ کل باید بیشتر از صفر باشد")
    if paid > total:
        raise ApiError(400, "مبلغ پرداخت‌شده نمی‌تواند از مبلغ کل بیشتر باشد")
    pay_date = clean(payload.get("pay_date"))
    if pay_date:
        pay_date = _parse_iso_or_raise(pay_date, "تاریخ معتبر نیست")
    else:
        pay_date = today_iso()
    return Payment.objects.create(
        product_id=pid, product_name=product_name,
        customer_name=clean(payload.get("customer_name")),
        customer_phone=clean(payload.get("customer_phone")),
        total_amount=total, paid_amount=paid, pay_date=pay_date,
        notes=clean(payload.get("notes")),
    )


def update_payment(payment: Payment, payload, partial=False) -> Payment:
    """Edit a payment record.

    Amounts of a receipt that is linked to a sale cannot be edited here —
    they would desynchronise the sale (price / paid breakdown / profit), so
    they may only change through the sale itself or instalment payments.
    Text fields (names, phone, date, notes) stay editable for linked
    receipts.  Settlement is re-derived by the shared helper and synced to
    the linked sale when there is one.
    """
    if partial:
        payload = _merge_partial(payload, payment, _PAYMENT_WRITE_FIELDS)
    total = max(0.0, to_float(payload.get("total_amount"), payment.total_amount))
    paid = max(0.0, to_float(payload.get("paid_amount"), payment.paid_amount))
    if payment.sale_id and (
            abs(total - payment.total_amount) > 0.001
            or abs(paid - payment.paid_amount) > 0.001):
        raise ApiError(400, "مبلغ این فقره به فروش متصل است و از همین‌جا قابل "
                            "تغییر نیست؛ فروش را ویرایش کنید یا از «ثبت پرداخت» "
                            "استفاده کنید")
    if total <= 0:
        raise ApiError(400, "مبلغ کل باید بیشتر از صفر باشد")
    if paid > total:
        raise ApiError(400, "مبلغ پرداخت‌شده نمی‌تواند از مبلغ کل بیشتر باشد")
    pay_date = clean(payload.get("pay_date")) or payment.pay_date
    if pay_date:
        pay_date = _parse_iso_or_raise(pay_date, "تاریخ معتبر نیست")
    payment.product_name = clean(payload.get("product_name")) or payment.product_name
    payment.customer_name = clean(payload.get("customer_name"))
    payment.customer_phone = clean(payload.get("customer_phone"))
    payment.total_amount = total
    payment.paid_amount = paid
    payment.pay_date = pay_date
    payment.notes = clean(payload.get("notes"))
    payment.save(update_fields=[
        "product_name", "customer_name", "customer_phone",
        "total_amount", "paid_amount", "pay_date", "notes",
        "updated_at"])
    # settlement — the date is stamped/cleared when the balance flips
    _sync_settlement(payment.sale if payment.sale_id else None, payment)
    return payment


def delete_payment(payment: Payment) -> None:
    """Delete a standalone payment record.

    A receipt linked to a sale is part of that sale — removing it alone
    would strand an unsettled deposit, so it must go with its sale.
    """
    if payment.sale_id:
        raise ApiError(400, "این فقره به فروش متصل است؛ برای حذف، فاکتور فروش "
                            "را از بخش فروش‌ها حذف کنید")
    payment.delete()


def add_payment(payment: Payment, payload) -> Payment:
    """Add a new instalment amount to an existing payment record.

    ``method`` (``cash`` | ``pos`` | ``card2card``, default ``cash``) routes
    the amount into the matching paid bucket of the linked sale, keeping the
    per-method totals correct.
    """
    amount = to_float(payload.get("amount"))
    if amount <= 0:
        raise ApiError(400, "مبلغ باید بیشتر از صفر باشد")
    method = clean(payload.get("method")) or "cash"
    if method not in PAID_METHOD_FIELDS:
        method = "cash"
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(id=payment.id)
        remaining = payment.total_amount - payment.paid_amount
        if amount > remaining + 0.001:
            raise ApiError(400, f"بیشتر از مانده‌ی فقره است (مانده: {fa_money(remaining)} تومان)")
        sale = None
        if payment.sale_id:
            sale = Sale.objects.select_for_update().get(id=payment.sale_id)
            field = PAID_METHOD_FIELDS[method]
            setattr(sale, field, (getattr(sale, field) or 0) + amount)
            sale.save(update_fields=[field])
        payment.paid_amount = payment.paid_amount + amount
        payment.save(update_fields=["paid_amount", "updated_at"])
        _sync_settlement(sale, payment)
    return payment


def settle_payment_full(payment: Payment, payload=None) -> Payment:
    """Settle the whole remaining balance in one shot.

    The remainder is added to the linked sale's matching paid bucket
    (``method``, default ``cash``); sale and receipt are marked settled
    through the shared helper.
    """
    method = clean((payload or {}).get("method")) or "cash"
    if method not in PAID_METHOD_FIELDS:
        method = "cash"
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(id=payment.id)
        remaining = payment.total_amount - payment.paid_amount
        if remaining <= 0.001:
            raise ApiError(400, "این فقره قبلاً تسویه شده است")
        sale = None
        if payment.sale_id:
            sale = Sale.objects.select_for_update().get(id=payment.sale_id)
            field = PAID_METHOD_FIELDS[method]
            setattr(sale, field, (getattr(sale, field) or 0) + remaining)
            sale.save(update_fields=[field])
        payment.paid_amount = payment.total_amount
        payment.save(update_fields=["paid_amount", "updated_at"])
        _sync_settlement(sale, payment)
    return payment


def bulk_delete_payments(raw_ids) -> int:
    """Bulk-delete standalone payment records.

    Sale-linked receipts are rejected as a whole (all-or-nothing): they are
    removed together with their sale, never on their own.
    """
    ids = _clean_ids(raw_ids)
    if not ids:
        raise ApiError(400, "موردی انتخاب نشده است")
    linked = Payment.objects.filter(id__in=ids, sale_id__isnull=False).count()
    if linked:
        raise ApiError(
            400, f"{fa_num(linked)} فقره‌ی انتخاب‌شده به فروش متصل است و از "
                 "همین‌جا حذف نمی‌شود؛ فاکتور فروش مربوطه را حذف کنید")
    Payment.objects.filter(id__in=ids).delete()
    return len(ids)
