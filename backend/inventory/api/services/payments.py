# -*- coding: utf-8 -*-
"""Payment domain: query, receipts, add installments, settlement, bulk-delete."""

from django.db import transaction
from django.db.models import F, Q, QuerySet

from inventory.jalali import today_iso
from inventory.models import Payment, Product, Sale
from inventory.utils import clean, fa_money, to_float, to_int

from .common import (
    ApiError, _clean_ids, _merge_partial, _parse_iso_or_raise,
)


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

    Settlement status is re-evaluated after the edit and synced to the
    linked sale (``is_settled``/``settled_at``).
    """
    if partial:
        payload = _merge_partial(payload, payment, _PAYMENT_WRITE_FIELDS)
    total = max(0.0, to_float(payload.get("total_amount"), payment.total_amount))
    paid = max(0.0, to_float(payload.get("paid_amount"), payment.paid_amount))
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
    # settlement — the date is stamped/cleared when the balance flips
    now_settled = total - paid <= 0.001
    if now_settled and not payment.settled_at:
        payment.settled_at = today_iso()
    elif not now_settled:
        payment.settled_at = ""
    if payment.sale_id:
        Sale.objects.filter(id=payment.sale_id).update(
            is_settled=now_settled, settled_at=payment.settled_at)
    payment.notes = clean(payload.get("notes"))
    payment.save(update_fields=[
        "product_name", "customer_name", "customer_phone",
        "total_amount", "paid_amount", "pay_date", "settled_at", "notes",
        "updated_at"])
    return payment


def delete_payment(payment: Payment) -> None:
    """Delete a payment record."""
    payment.delete()


def add_payment(payment: Payment, payload) -> Payment:
    """Add a new instalment amount to an existing payment record."""
    amount = to_float(payload.get("amount"))
    if amount <= 0:
        raise ApiError(400, "مبلغ باید بیشتر از صفر باشد")
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(id=payment.id)
        remaining = payment.total_amount - payment.paid_amount
        if amount > remaining + 0.001:
            raise ApiError(400, f"بیشتر از مانده‌ی فقره است (مانده: {fa_money(remaining)} تومان)")
        payment.paid_amount = payment.paid_amount + amount
        now_settled = payment.total_amount - payment.paid_amount <= 0.001
        if now_settled and not payment.settled_at:
            payment.settled_at = today_iso()
        payment.save(update_fields=["paid_amount", "settled_at", "updated_at"])
        # fully settled → mark the linked deposit sale as settled
        if payment.sale_id and now_settled:
            Sale.objects.filter(id=payment.sale_id).update(
                is_settled=True, settled_at=payment.settled_at)
    return payment


def settle_payment_full(payment: Payment) -> Payment:
    """Settle the whole remaining balance in one shot.

    The remainder is added to the linked sale's ``paid_cash`` and the sale
    is marked settled.
    """
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(id=payment.id)
        remaining = payment.total_amount - payment.paid_amount
        if remaining <= 0.001:
            raise ApiError(400, "این فقره قبلاً تسویه شده است")
        payment.paid_amount = payment.total_amount
        if not payment.settled_at:
            payment.settled_at = today_iso()
        payment.save(update_fields=["paid_amount", "settled_at", "updated_at"])
        if payment.sale_id:
            Sale.objects.filter(id=payment.sale_id).update(
                is_settled=True, paid_cash=F("paid_cash") + remaining,
                settled_at=payment.settled_at)
    return payment


def bulk_delete_payments(raw_ids) -> int:
    """Bulk-delete payment records; returns the number deleted."""
    ids = _clean_ids(raw_ids)
    if not ids:
        raise ApiError(400, "موردی انتخاب نشده است")
    Payment.objects.filter(id__in=ids).delete()
    return len(ids)
