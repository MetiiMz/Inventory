# -*- coding: utf-8 -*-
"""Business-logic layer — the single source of truth for every write operation.

The legacy-shape adapters in :mod:`inventory.api.compat` (the ``/api/*``
routes the current frontend calls) call the functions in this module.
Rules enforced here, exactly as they behaved before:

* validation with the original Persian error messages (raised as
  :class:`ApiError`),
* transactional side effects (sale + deposit receipt creation, stock
  flip on sale/delete, cascade deletes, settlement sync between
  payments and sales),
* file housekeeping (removing orphaned images).

Reads the adapters share (calendar events, dashboard report
validation, Excel export/import, uploads) also live here, so the
adapter layer only decides *how* to serialize the result.
"""
import base64
import datetime
import json
import os
import secrets

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q, QuerySet
from django.db.models.functions import Lower

from inventory.dbhelpers import add_brand, delete_brand, get_setting, set_setting
from inventory.jalali import (
    MONTH_NAMES, jalali_month_length, jalali_to_gregorian, parse_jalali_date,
    today_iso,
)
from inventory.models import Payment, Product, Repair, Sale, Tracking
from inventory.utils import (
    SALE_TYPE_FA, STATUS_FA, TRACKING_STATUS_FA, clean, fa_money, fa_num,
    invoice_code, remove_image, to_en_phone, to_float, to_int,
)

# Status dictionaries are re-exported for convenience of views/compat layers.
__all__ = ["ApiError"]


class ApiError(Exception):
    """A business-rule violation.

    Raised by every service function.  ``status_code`` is the HTTP status
    the API layers should return and ``message`` is a human-readable
    Persian error message (or a list of messages for the Excel importer).
    """

    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


# ---------------------------------------------------------------- helpers
def _clean_ids(raw_ids):
    """Coerce a raw ``ids`` payload into a list of positive ints."""
    return [to_int(i) for i in (raw_ids or []) if to_int(i)]


def _merge_partial(payload, obj, fields):
    """Fill keys missing from a PATCH payload with the object's current values.

    PUT handlers always receive the full form, so legacy behaviour is
    "replace".  For PATCH (partial update) we pre-merge the instance's
    current values so that omitted fields are preserved instead of wiped.
    """
    payload = dict(payload or {})
    for field in fields:
        if field not in payload:
            payload[field] = getattr(obj, field)
    return payload


def _parse_iso_or_raise(text, message):
    """Parse a Jalali/ISO date string; raise ``ApiError`` when invalid."""
    parsed = parse_jalali_date(text)
    if not parsed:
        raise ApiError(400, message)
    return parsed


# =====================================================================
# Products
# =====================================================================
_PRODUCT_SORT = {
    "office_code": "office_code", "website_code": "website_code", "name": "name",
    "brand": "brand", "supplier": "supplier", "purchase_date": "purchase_date",
    "purchase_price": "purchase_price", "sale_price": "sale_price",
    "available": "available", "created_at": "id",
}
_PRODUCT_NOCASE = {"office_code", "website_code", "name", "brand", "supplier"}
_PRODUCT_WRITE_FIELDS = (
    "name", "reference", "office_code", "website_code", "brand",
    "purchase_price", "sale_price", "supplier", "purchase_date",
    "purchase_type", "notes", "image",
)


def product_queryset(params) -> QuerySet:
    """Filtered/ordered product list.

    Supported query parameters (identical in both API layers):
    ``q`` (name/reference/codes/brand/supplier), ``brand``,
    ``status`` = ``available`` | ``unavailable``, ``date_from``/``date_to``
    (Jalali or ISO, bounds for ``purchase_date``), ``sort`` + ``dir``.
    """
    q = clean(params.get("q", ""))
    brand = clean(params.get("brand", ""))
    status = clean(params.get("status", ""))
    date_from = clean(params.get("date_from", ""))
    date_to = clean(params.get("date_to", ""))
    sort = clean(params.get("sort", "")) or "office_code"
    direction = clean(params.get("dir", "")).lower() or "asc"

    qs = Product.objects.all()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(reference__icontains=q)
            | Q(office_code__icontains=q) | Q(website_code__icontains=q)
            | Q(brand__icontains=q) | Q(supplier__icontains=q)
        )
    if brand:
        qs = qs.filter(brand=brand)
    if status == "available":
        qs = qs.filter(available=True)
    elif status == "unavailable":
        qs = qs.filter(available=False)
    if date_from:
        parsed = parse_jalali_date(date_from)
        if parsed:
            qs = qs.filter(purchase_date__gte=parsed)
    if date_to:
        parsed = parse_jalali_date(date_to)
        if parsed:
            qs = qs.filter(purchase_date__lte=parsed)

    col = _PRODUCT_SORT.get(sort, "office_code")
    desc = direction == "desc"
    if col in _PRODUCT_NOCASE:  # legacy COLLATE NOCASE equivalent
        func = Lower(col)
        order = [func.desc() if desc else func.asc()]
    else:
        order = ["-" + col if desc else col]
    return qs.order_by(*order, "-id")


def _product_values(payload):
    """Validate product fields; returns the clean dict (raises ApiError)."""
    name = clean(payload.get("name"))
    office_code = clean(payload.get("office_code"))
    website_code = clean(payload.get("website_code"))
    if not name:
        raise ApiError(400, "نام ساعت الزامی است")
    if not office_code:
        raise ApiError(400, "کد دفتر فروشگاه الزامی است")
    if not website_code:
        raise ApiError(400, "کد انبار سایت الزامی است")

    purchase_date = clean(payload.get("purchase_date"))
    if purchase_date:
        purchase_date = _parse_iso_or_raise(
            purchase_date, "تاریخ خرید معتبر نیست (نمونه: ۱۴۰۳/۰۵/۱۲)")
    else:
        purchase_date = ""

    return {
        "name": name,
        "reference": clean(payload.get("reference")),
        "office_code": office_code,
        "website_code": website_code,
        "brand": clean(payload.get("brand")),
        "purchase_price": max(0.0, to_float(payload.get("purchase_price"))),
        "sale_price": max(0.0, to_float(payload.get("sale_price"))),
        # one row = one watch; it becomes unavailable once sold
        "available": True,
        "supplier": clean(payload.get("supplier")),
        "purchase_date": purchase_date,
        "notes": clean(payload.get("notes")),
        "image": clean(payload.get("image")),
    }


def _check_duplicate_code(office_code, website_code, exclude_id=None):
    """Reject duplicate office/site codes (case-insensitive), legacy message."""
    cond = Q(office_code__iexact=office_code) | Q(website_code__iexact=website_code)
    if exclude_id:
        cond &= ~Q(id=exclude_id)
    dup = Product.objects.filter(cond).first()
    if not dup:
        return None
    if dup.office_code.lower() == office_code.lower():
        return f"کد دفتر فروشگاه «{office_code}» قبلاً برای ساعت «{dup.name}» ثبت شده است"
    return f"کد انبار سایت «{website_code}» قبلاً برای ساعت «{dup.name}» ثبت شده است"


def create_product(payload) -> Product:
    """Create a product (codes must be unique, stock starts as available)."""
    values = _product_values(payload)
    dup = _check_duplicate_code(values["office_code"], values["website_code"])
    if dup:
        raise ApiError(400, dup)
    with transaction.atomic():
        return Product.objects.create(**values)


def update_product(product: Product, payload, partial=False) -> Product:
    """Update a product.

    The stock flag (``available``) is never touched here — editing a sold
    watch must not flip it back to in-stock (a historic bug).
    """
    if partial:
        payload = _merge_partial(payload, product, _PRODUCT_WRITE_FIELDS)
    values = _product_values(payload)
    dup = _check_duplicate_code(values["office_code"], values["website_code"],
                                exclude_id=product.id)
    if dup:
        raise ApiError(400, dup)
    values.pop("available", None)
    old_image = product.image
    for key, value in values.items():
        setattr(product, key, value)
    product.save()
    if old_image and old_image != values["image"]:
        remove_image(old_image)
    return product


def delete_product(product: Product) -> None:
    """Delete a product and its image file."""
    with transaction.atomic():
        product.delete()
    if product.image:
        remove_image(product.image)


def bulk_delete_products(raw_ids) -> int:
    """Delete many products at once; returns the number deleted."""
    ids = _clean_ids(raw_ids)
    if not ids:
        raise ApiError(400, "موردی انتخاب نشده است")
    images = list(
        Product.objects.filter(id__in=ids)
        .exclude(image="").values_list("image", flat=True)
    )
    with transaction.atomic():
        Product.objects.filter(id__in=ids).delete()
    for img in images:
        remove_image(img)
    return len(ids)


# =====================================================================
# Sales
# =====================================================================
_SALE_SORT = {
    "date": "sale_date", "name": "product__name", "final_price": "final_price",
    "profit": "profit", "office_code": "product__office_code",
    "customer": "customer",
}
_SALE_NOCASE = {"product__name", "product__office_code", "customer"}


def sale_queryset(params) -> QuerySet:
    """Filtered/ordered sale list.

    Parameters: ``q`` (product/customer/phone/codes/reference/invoice),
    ``sale_type``, ``pay_method`` = ``cash`` | ``pos`` | ``card2card``,
    ``date_from``/``date_to``, ``sort`` + ``dir``.  Deposits are always
    included regardless of settlement state.
    """
    q = clean(params.get("q", ""))
    sale_type = clean(params.get("sale_type", ""))
    pay_method = clean(params.get("pay_method", ""))
    date_from = clean(params.get("date_from", ""))
    date_to = clean(params.get("date_to", ""))
    sort = clean(params.get("sort", "")) or "date"
    direction = clean(params.get("dir", "")).lower() or "desc"

    qs = Sale.objects.select_related("product").all()
    if q:
        qs = qs.filter(
            Q(product__name__icontains=q) | Q(customer__icontains=q)
            | Q(customer_phone__icontains=q) | Q(product__office_code__icontains=q)
            | Q(product__website_code__icontains=q) | Q(product__reference__icontains=q)
            | Q(invoice_code__icontains=q)
        )
    if sale_type in SALE_TYPE_FA:
        qs = qs.filter(sale_type=sale_type)
    col = {"cash": "paid_cash", "pos": "paid_pos",
           "card2card": "paid_card2card"}.get(pay_method)
    if col:
        qs = qs.filter(**{col + "__gt": 0})
    if date_from:
        parsed = parse_jalali_date(date_from)
        if parsed:
            qs = qs.filter(sale_date__gte=parsed)
    if date_to:
        parsed = parse_jalali_date(date_to)
        if parsed:
            qs = qs.filter(sale_date__lte=parsed)

    col = _SALE_SORT.get(sort, "sale_date")
    desc = direction == "desc"
    if col in _SALE_NOCASE:
        func = Lower(col)
        order = [func.desc() if desc else func.asc()]
    else:
        order = ["-" + col if desc else col]
    return qs.order_by(*order, "-id")


def _validate_buyer(customer, customer_phone):
    """Buyer name and a valid phone number are mandatory (legacy message)."""
    if not customer:
        raise ApiError(400, "نام خریدار الزامی است")
    digits = customer_phone.replace("+", "").replace(" ", "")
    if not digits.isdigit() or not (10 <= len(digits) <= 13):
        raise ApiError(400, "شماره تماس خریدار معتبر نیست (مثال: 09123456789)")


def next_invoice_code() -> str:
    """Preview of the next auto-generated invoice code (TT-<jy><jm>-<id>)."""
    last_id = Sale.objects.order_by("-id").values_list("id", flat=True).first() or 0
    return invoice_code(last_id + 1, today_iso())


def create_sale(payload) -> Sale:
    """Register a sale — cash (complete) or deposit (creates a receipt).

    Transactional: creates the Sale row, the deposit Payment receipt when
    applicable, and flips the product to out-of-stock.
    """
    pid = to_int(payload.get("product_id"))
    if not pid:
        raise ApiError(400, "محصول انتخاب نشده است")

    payment_kind = "deposit" if clean(payload.get("payment_type")) == "deposit" else "cash"

    product = Product.objects.filter(id=pid).first()
    if product is None:
        raise ApiError(404, "محصول یافت نشد")

    sale_price = to_float(payload.get("sale_price"), product.sale_price)
    discount = to_float(payload.get("discount_price"), 0)
    final_price = discount if discount > 0 else sale_price
    if final_price > sale_price:
        raise ApiError(400, "قیمت نهایی نمی‌تواند از قیمت فروش بیشتر باشد")

    paid_cash = max(0.0, to_float(payload.get("paid_cash")))
    paid_pos = max(0.0, to_float(payload.get("paid_pos")))
    paid_card2card = max(0.0, to_float(payload.get("paid_card2card")))
    paid_now = paid_cash + paid_pos + paid_card2card

    sale_date = clean(payload.get("sale_date"))
    if sale_date:
        parsed = _parse_iso_or_raise(sale_date, "تاریخ فروش معتبر نیست")
    else:
        parsed = today_iso()
    sale_type = clean(payload.get("sale_type")) or "person"
    if sale_type not in SALE_TYPE_FA:
        sale_type = "person"
    customer_phone = to_en_phone(clean(payload.get("customer_phone")))
    customer = clean(payload.get("customer"))
    _validate_buyer(customer, customer_phone)

    # optional manual invoice code; auto TT-code only when left empty
    manual_invoice = clean(payload.get("invoice_code"))
    if len(manual_invoice) > 40:
        raise ApiError(400, "کد فاکتور نمی‌تواند بیش از ۴۰ نویسه باشد")
    if manual_invoice and Sale.objects.filter(invoice_code=manual_invoice).exists():
        raise ApiError(400, f"کد فاکتور «{manual_invoice}» قبلاً استفاده شده است")

    if payment_kind == "deposit":
        if paid_now <= 0:
            raise ApiError(400, "برای فروش بیعانه، دست‌کم مبلغ بیعانه را وارد کنید")
        if paid_now > final_price + 0.001:
            raise ApiError(400, "جمع پرداخت‌ها نمی‌تواند از قیمت نهایی بیشتر باشد "
                                f"({fa_money(final_price)} تومان)")
        is_settled = False
    else:
        if paid_now > final_price + 0.001:
            raise ApiError(400, "جمع پرداخت‌ها نمی‌تواند از قیمت نهایی بیشتر باشد "
                                f"({fa_money(final_price)} تومان)")
        # a complete cash sale; without a breakdown everything counts as cash
        if paid_now <= 0:
            paid_cash, paid_pos, paid_card2card = final_price, 0.0, 0.0
        payment_kind = "cash"
        is_settled = True

    profit = final_price - (product.purchase_price or 0)

    with transaction.atomic():
        sale = Sale.objects.create(
            product=product, sale_price=sale_price,
            purchase_price=product.purchase_price, profit=profit,
            sale_date=parsed, customer=customer,
            customer_phone=customer_phone, sale_type=sale_type,
            payment_type=payment_kind, final_price=final_price,
            paid_cash=paid_cash, paid_pos=paid_pos,
            paid_card2card=paid_card2card, is_settled=is_settled,
            notes=clean(payload.get("notes")), invoice_code=manual_invoice,
        )
        if payment_kind == "deposit":
            Payment.objects.create(
                sale=sale, product=product, product_name=product.name,
                customer_name=customer, customer_phone=customer_phone,
                total_amount=final_price, paid_amount=paid_now,
                pay_date=parsed,
                notes=f"بیعانه فروش #{sale.id} — مانده: "
                      f"{fa_money(final_price - paid_now)} تومان",
            )
        # this watch is sold — it becomes out-of-stock
        Product.objects.filter(id=pid).update(available=False)

    return sale


def update_sale(sale: Sale, payload) -> Sale:
    """Edit a sale (prices, buyer, methods, date, notes).

    Every omitted field falls back to the current value, so PUT and PATCH
    behave identically.  Changing the sale date re-syncs the deposit
    receipt's ``pay_date``.
    """
    payload = _merge_partial(payload, sale, (
        "sale_price", "paid_cash", "paid_pos",
        "paid_card2card", "sale_date", "customer", "customer_phone",
        "sale_type", "payment_type", "purchase_price", "notes",
    ))
    # discount_price is a payload alias of final_price, not a model column
    payload.setdefault("discount_price", sale.final_price or 0)
    product = sale.product

    sale_price = to_float(payload.get("sale_price"), sale.sale_price)
    payment_kind = clean(payload.get("payment_type")) or sale.payment_type
    if payment_kind not in ("cash", "deposit"):
        payment_kind = "cash"
    if payment_kind == "deposit":
        final_price = to_float(payload.get("discount_price"),
                               sale.final_price or sale_price)
    else:
        discount = to_float(payload.get("discount_price"), 0)
        final_price = discount if discount > 0 else sale_price
    if final_price > sale_price:
        raise ApiError(400, "قیمت نهایی نمی‌تواند از قیمت فروش بیشتر باشد")

    paid_cash = max(0.0, to_float(payload.get("paid_cash"), sale.paid_cash))
    paid_pos = max(0.0, to_float(payload.get("paid_pos"), sale.paid_pos))
    paid_card2card = max(0.0, to_float(payload.get("paid_card2card"), sale.paid_card2card))
    paid_now = paid_cash + paid_pos + paid_card2card
    if paid_now > final_price + 0.001:
        raise ApiError(400, f"جمع پرداخت‌ها نمی‌تواند از قیمت نهایی بیشتر باشد "
                            f"({fa_money(final_price)} تومان)")
    if paid_now <= 0 and payment_kind == "cash":
        paid_cash, paid_pos, paid_card2card = final_price, 0.0, 0.0

    purchase_price = to_float(payload.get("purchase_price"),
                              product.purchase_price if product else 0)
    profit = final_price - purchase_price

    sale_date = clean(payload.get("sale_date")) or sale.sale_date
    parsed = _parse_iso_or_raise(sale_date, "تاریخ فروش معتبر نیست")
    sale_type = clean(payload.get("sale_type")) or sale.sale_type
    if sale_type not in SALE_TYPE_FA:
        sale_type = "person"

    customer = clean(payload.get("customer"))
    customer_phone = to_en_phone(clean(payload.get("customer_phone")))
    _validate_buyer(customer, customer_phone)

    sale.sale_price = sale_price
    sale.final_price = final_price
    sale.profit = profit
    sale.notes = clean(payload.get("notes"))
    old_date = sale.sale_date
    sale.sale_date = parsed
    sale.customer = customer
    sale.customer_phone = customer_phone
    sale.sale_type = sale_type
    sale.payment_type = payment_kind
    sale.paid_cash = paid_cash
    sale.paid_pos = paid_pos
    sale.paid_card2card = paid_card2card
    sale.save()
    # keep the linked deposit receipt's date in sync with the sale date
    if parsed != old_date:
        sale.payments.update(pay_date=parsed)
    return sale


def delete_sale(sale: Sale) -> None:
    """Delete a sale — the watch becomes available again (FK-cascades)."""
    pid = sale.product_id
    with transaction.atomic():
        sale.delete()
        if pid:
            Product.objects.filter(id=pid).update(available=True)


def bulk_delete_sales(raw_ids) -> int:
    """Bulk-delete sales; every affected watch becomes available again."""
    ids = _clean_ids(raw_ids)
    if not ids:
        raise ApiError(400, "موردی انتخاب نشده است")
    with transaction.atomic():
        Product.objects.filter(
            id__in=Sale.objects.filter(id__in=ids).values("product_id")
        ).update(available=True)
        Sale.objects.filter(id__in=ids).delete()
    return len(ids)


# =====================================================================
# Payments (deposit receipts / installments)
# =====================================================================
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


# =====================================================================
# Repairs
# =====================================================================
_REPAIR_WRITE_FIELDS = (
    "watch_name", "watch_code", "issue", "delivery_date", "return_date",
    "customer_name", "customer_phone", "is_warranty", "status",
    "repair_price", "image", "notes",
)


def repair_queryset(params) -> QuerySet:
    """Filtered repair list. Parameters: ``status``, ``q``."""
    status = clean(params.get("status", ""))
    q = clean(params.get("q", ""))
    qs = Repair.objects.all()
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(watch_name__icontains=q) | Q(watch_code__icontains=q)
            | Q(customer_name__icontains=q) | Q(customer_phone__icontains=q)
        )
    return qs.order_by("-id")


def _repair_values(payload):
    """Validate repair fields (delivery date defaults to today)."""
    watch_name = clean(payload.get("watch_name"))
    if not watch_name:
        raise ApiError(400, "نام ساعت الزامی است")
    customer_phone = clean(payload.get("customer_phone"))
    if customer_phone and not customer_phone.replace("+", "").replace(" ", "").isdigit():
        raise ApiError(400, "شماره تماس معتبر نیست")
    delivery_date = clean(payload.get("delivery_date"))
    if delivery_date:
        delivery_date = _parse_iso_or_raise(delivery_date, "تاریخ تحویل معتبر نیست")
    else:
        delivery_date = today_iso()
    return_date = clean(payload.get("return_date"))
    if return_date:
        return_date = _parse_iso_or_raise(return_date, "تاریخ بازگشت معتبر نیست")
    else:
        return_date = ""
    status = clean(payload.get("status")) or "received"
    if status not in STATUS_FA:
        status = "received"
    return {
        "watch_name": watch_name,
        "watch_code": clean(payload.get("watch_code")),
        "issue": clean(payload.get("issue")),
        "delivery_date": delivery_date,
        "return_date": return_date,
        "customer_name": clean(payload.get("customer_name")),
        "customer_phone": customer_phone,
        "is_warranty": 1 if payload.get("is_warranty") else 0,
        "status": status,
        "repair_price": max(0.0, to_float(payload.get("repair_price"))),
        "image": clean(payload.get("image")),
        "notes": clean(payload.get("notes")),
    }


def create_repair(payload) -> Repair:
    """Create a repair ticket."""
    with transaction.atomic():
        return Repair.objects.create(**_repair_values(payload))


def update_repair(repair: Repair, payload, partial=False) -> Repair:
    """Update a repair ticket (image housekeeping included)."""
    if partial:
        payload = _merge_partial(payload, repair, _REPAIR_WRITE_FIELDS)
    values = _repair_values(payload)
    old_image = repair.image
    for key, value in values.items():
        setattr(repair, key, value)
    repair.save()
    if old_image and old_image != values["image"]:
        remove_image(old_image)
    return repair


def delete_repair(repair: Repair) -> None:
    """Delete a repair ticket and its image file."""
    with transaction.atomic():
        repair.delete()
    if repair.image:
        remove_image(repair.image)


def bulk_delete_repairs(raw_ids) -> int:
    """Bulk-delete repair tickets; returns the number deleted."""
    ids = _clean_ids(raw_ids)
    if not ids:
        raise ApiError(400, "موردی انتخاب نشده است")
    images = list(
        Repair.objects.filter(id__in=ids)
        .exclude(image="").values_list("image", flat=True)
    )
    with transaction.atomic():
        Repair.objects.filter(id__in=ids).delete()
    for img in images:
        remove_image(img)
    return len(ids)


def set_repair_status(repair: Repair, payload) -> Repair:
    """Change a repair's status; ``delivered`` stamps ``return_date``."""
    status = clean(payload.get("status"))
    if status not in STATUS_FA:
        raise ApiError(400, "وضعیت نامعتبر است")
    return_date = clean(payload.get("return_date"))
    if return_date:
        parsed = _parse_iso_or_raise(return_date, "تاریخ بازگشت معتبر نیست")
    elif status == "delivered":
        parsed = today_iso()
    else:
        parsed = ""
    repair.status = status
    if parsed:
        repair.return_date = parsed
    repair.save()
    return repair


# =====================================================================
# Order tracking
# =====================================================================
_TRACKING_WRITE_FIELDS = (
    "item_name", "item_code", "customer_name", "customer_phone",
    "price", "status", "notes", "image",
)


def tracking_queryset(params) -> QuerySet:
    """Filtered tracking list. Parameters: ``status``, ``q``."""
    status = clean(params.get("status", ""))
    q = clean(params.get("q", ""))
    qs = Tracking.objects.all()
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(item_name__icontains=q) | Q(item_code__icontains=q)
            | Q(customer_name__icontains=q) | Q(customer_phone__icontains=q)
        )
    return qs.order_by("-id")


def _tracking_values(payload):
    """Validate tracking fields (item name is mandatory)."""
    item_name = clean(payload.get("item_name"))
    if not item_name:
        raise ApiError(400, "نام ساعت یا قطعه الزامی است")
    status = clean(payload.get("status")) or "new"
    if status not in TRACKING_STATUS_FA:
        status = "new"
    return {
        "item_name": item_name,
        "item_code": clean(payload.get("item_code")),
        "customer_name": clean(payload.get("customer_name")),
        "customer_phone": clean(payload.get("customer_phone")),
        "price": max(0.0, to_float(payload.get("price"))),
        "status": status,
        "notes": clean(payload.get("notes")),
        "image": clean(payload.get("image")),
    }


def create_tracking(payload) -> Tracking:
    """Create an order-tracking record."""
    with transaction.atomic():
        return Tracking.objects.create(**_tracking_values(payload))


def update_tracking(tracking: Tracking, payload, partial=False) -> Tracking:
    """Update an order-tracking record (image housekeeping included)."""
    if partial:
        payload = _merge_partial(payload, tracking, _TRACKING_WRITE_FIELDS)
    values = _tracking_values(payload)
    old_image = tracking.image
    for key, value in values.items():
        setattr(tracking, key, value)
    tracking.save()
    if old_image and old_image != values["image"]:
        remove_image(old_image)
    return tracking


def delete_tracking(tracking: Tracking) -> None:
    """Delete an order-tracking record and its image file."""
    with transaction.atomic():
        tracking.delete()
    if tracking.image:
        remove_image(tracking.image)


def bulk_delete_tracking(raw_ids) -> int:
    """Bulk-delete tracking records; returns the number deleted."""
    ids = _clean_ids(raw_ids)
    if not ids:
        raise ApiError(400, "موردی انتخاب نشده است")
    images = list(
        Tracking.objects.filter(id__in=ids)
        .exclude(image="").values_list("image", flat=True)
    )
    with transaction.atomic():
        Tracking.objects.filter(id__in=ids).delete()
    for img in images:
        remove_image(img)
    return len(ids)


# =====================================================================
# Brands & store settings (thin wrappers over dbhelpers)
# =====================================================================
def brands_list():
    """All brand names, alphabetically."""
    from inventory.dbhelpers import get_brands
    return get_brands()


def brands_add(payload):
    """Add a brand; raises with the legacy message on duplicates."""
    good, err = add_brand((payload or {}).get("name"))
    if not good:
        raise ApiError(400, err)


def brands_delete(payload):
    """Delete a brand by name."""
    delete_brand((payload or {}).get("name"))


def site_settings() -> dict:
    """Store settings as a dict (the settings page's GET payload)."""
    return {
        "store_name": get_setting("store_name", "") or "Tick O Time",
        "store_phone": get_setting("store_phone", ""),
        "store_address": get_setting("store_address", ""),
        "currency": get_setting("currency", "تومان"),
        "site_icon": get_setting("site_icon", ""),
    }


def save_settings(payload):
    """Persist the whitelisted store-setting keys present in the payload."""
    for key in ("store_name", "store_phone", "store_address", "currency"):
        if key in (payload or {}):
            set_setting(key, clean(payload.get(key)))


def set_site_icon(icon) -> str:
    """Store the site icon filename; removes the previous icon file."""
    from inventory.utils import remove_image
    old = get_setting("site_icon", "")
    icon = clean(icon)
    if icon and icon != old:
        remove_image(old)
    set_setting("site_icon", icon)
    return icon


# =====================================================================
# Image upload
# =====================================================================
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg"}
ICON_EXT = {".png", ".svg", ".ico", ".jpg", ".jpeg", ".webp"}


def _save_uploaded(kind, ext, content):
    """Write uploaded bytes under a unique name; returns (fname, error)."""
    allowed = ICON_EXT if kind == "icon" else ALLOWED_EXT
    if ext not in allowed:
        return None, "فرمت فایل پشتیبانی نمی‌شود"
    fname = ("icon_" if kind == "icon" else "img_") + \
        datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + \
        secrets.token_hex(4) + ext
    os.makedirs(settings.IMG_DIR, exist_ok=True)
    with open(os.path.join(str(settings.IMG_DIR), fname), "wb") as out:
        out.write(content)
    return fname, None


def save_upload(request) -> str:
    """Handle an image/icon upload from either transport and return the filename.

    Preferred path: JSON body ``{kind, name, data}`` with a base64 (or
    data-URI) payload.  Fallback: classic multipart form with a ``file``
    field.  Files are capped at 2 MB.
    """
    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads(request.body or b"{}")
        except Exception:
            raise ApiError(400, "بدنه‌ی درخواست نامعتبر است")
        kind = clean(payload.get("kind")) or "image"
        name = clean(payload.get("name")) or "file"
        data = payload.get("data") or ""
        if isinstance(data, str) and data.startswith("data:"):
            _, _, data = data.partition(",")
        try:
            content = base64.b64decode(data)
        except Exception:
            raise ApiError(400, "محتوای فایل قابل خواندن نیست")
        if not content:
            raise ApiError(400, "فایلی انتخاب نشده است")
        if len(content) > 2 * 1024 * 1024:
            raise ApiError(400, "حجم فایل باید کمتر از ۲ مگابایت باشد")
        fname, err = _save_uploaded(kind, os.path.splitext(name)[1].lower(), content)
        if err:
            raise ApiError(400, err)
        return fname

    f = request.FILES.get("file")
    kind = clean(request.POST.get("kind")) or "image"
    if not f or not f.name:
        raise ApiError(400, "فایلی انتخاب نشده است")
    fname, err = _save_uploaded(
        kind, os.path.splitext(f.name)[1].lower(), b"".join(f.chunks()))
    if err:
        raise ApiError(400, err)
    return fname


# =====================================================================
# Jalali calendar events
# =====================================================================
def _repair_cell(repair, key):
    """One repair cell in the month grid."""
    return {
        "type": key, "id": repair.id, "name": repair.watch_name,
        "image": repair.image, "customer": repair.customer_name,
        "code": repair.watch_code,
        "price_display": fa_money(repair.repair_price),
    }


def calendar_month(jy_raw, jm_raw) -> dict:
    """All events of one Jalali month, laid out on the month grid.

    Invalid/missing ``jy``/``jm`` fall back to the current month.  The
    returned dict is ``{jy, jm, month_name, cells}`` where ``cells`` is a
    flat, week-aligned list (``None`` padding) of
    ``{day, iso, is_today, purchases, sales, repairs_in, repairs_out}``.
    """
    from inventory.utils import product_dict
    jy = to_int(jy_raw, 0)
    jm = to_int(jm_raw, 0)
    if not jy or not jm or jm < 1 or jm > 12:
        from inventory.jalali import today_jalali
        jy, jm, _ = today_jalali()
    gy1, gm1, gd1 = jalali_to_gregorian(jy, jm, 1)
    last = jalali_month_length(jy, jm)
    gy2, gm2, gd2 = jalali_to_gregorian(jy, jm, last)
    start = datetime.date(gy1, gm1, gd1).isoformat()
    end = datetime.date(gy2, gm2, gd2).isoformat()

    days = {}

    def bucket(iso):
        return days.setdefault(iso, {
            "purchases": [], "sales": [], "repairs_in": [], "repairs_out": []})

    purchases = Product.objects.filter(
        purchase_date__gte=start, purchase_date__lte=end).order_by("purchase_date")
    for p in purchases:
        bucket(p.purchase_date)["purchases"].append({
            "type": "purchase", "id": p.id, "name": p.name, "image": p.image,
            "office_code": p.office_code, "website_code": p.website_code,
            "price_display": fa_money(p.purchase_price),
        })
    sales = Sale.objects.select_related("product").filter(
        sale_date__gte=start, sale_date__lte=end).order_by("sale_date")
    for s in sales:
        bucket(s.sale_date)["sales"].append({
            "type": "sale", "id": s.id,
            "name": s.product.name if s.product else "محصول حذف‌شده",
            "image": s.product.image if s.product else "",
            "customer": s.customer,
            "customer_phone": s.customer_phone or "",
            "customer_phone_fa": fa_num(s.customer_phone or ""),
            "price_display": fa_money(s.final_price or s.sale_price),
        })
    repairs_in = Repair.objects.filter(
        delivery_date__gte=start, delivery_date__lte=end).order_by("delivery_date")
    for r in repairs_in:
        bucket(r.delivery_date)["repairs_in"].append(_repair_cell(r, "repairs_in"))
    repairs_out = Repair.objects.filter(
        return_date__gte=start, return_date__lte=end).order_by("return_date")
    for r in repairs_out:
        bucket(r.return_date)["repairs_out"].append(_repair_cell(r, "repairs_out"))

    # Saturday is the first day of the week
    first_weekday = datetime.date(gy1, gm1, gd1).weekday()
    weekday_index = (first_weekday + 2) % 7

    cells = [None] * weekday_index
    for day in range(1, last + 1):
        gy, gm, gd = jalali_to_gregorian(jy, jm, day)
        iso = datetime.date(gy, gm, gd).isoformat()
        info = days.get(iso)
        cells.append({
            "day": day,
            "iso": iso,
            "is_today": iso == datetime.date.today().isoformat(),
            "purchases": info["purchases"] if info else [],
            "sales": info["sales"] if info else [],
            "repairs_in": info["repairs_in"] if info else [],
            "repairs_out": info["repairs_out"] if info else [],
        })
    while len(cells) % 7 != 0:
        cells.append(None)

    return {"jy": jy, "jm": jm, "month_name": MONTH_NAMES[jm - 1], "cells": cells}


def calendar_day(date_value) -> dict:
    """Full detail of one day (purchases, sales, repairs in/out)."""
    from inventory.utils import product_dict, repair_dict, sale_dict
    iso = clean(date_value)
    if not iso:
        raise ApiError(400, "تاریخ مشخص نشده")
    purchases = Product.objects.filter(purchase_date=iso).order_by("id")
    sales = Sale.objects.select_related("product").filter(sale_date=iso).order_by("id")
    repairs_in = Repair.objects.filter(delivery_date=iso).order_by("id")
    repairs_out = Repair.objects.filter(return_date=iso).order_by("id")
    from inventory.utils import fa_date
    return {
        "date_iso": iso,
        "date_fa": fa_date(iso, with_weekday=True),
        "purchases": [product_dict(p) for p in purchases],
        "sales": [
            {**sale_dict(s),
             "name": s.product.name if s.product else "محصول حذف‌شده",
             "image": s.product.image if s.product else ""}
            for s in sales
        ],
        "repairs_in": [repair_dict(r) for r in repairs_in],
        "repairs_out": [repair_dict(r) for r in repairs_out],
    }


# =====================================================================
# Dashboard report (monthly activity chart)
# =====================================================================
def monthly_activity(year_value):
    """Validate the ``year`` query parameter and return ``(year, months)``.

    Empty/missing year → the current Jalali year.
    """
    from inventory.reports import get_monthly_activity
    if year_value is None or str(year_value).strip() == "":
        months = get_monthly_activity()
        return months[0]["jy"], months
    try:
        jy = int(str(year_value).strip())
    except (TypeError, ValueError):
        raise ApiError(400, "سال نامعتبر است")
    if not 1300 <= jy <= 1600:
        raise ApiError(400, "سال خارج از بازه‌ی مجاز است")
    return jy, get_monthly_activity(jy)


# =====================================================================
# Excel / CSV export & import
# =====================================================================
def _export_funcs():
    from inventory.excel_io import (
        export_payments, export_products, export_repairs, export_sales,
        export_tracking,
    )
    return {
        "products": export_products,
        "repairs": export_repairs,
        "tracking": export_tracking,
        "payments": export_payments,
        "sales": export_sales,
    }


def export_data_file(kind, fmt):
    """Generate an export file; returns ``(path, filename)``."""
    if fmt not in ("xlsx", "csv") or kind not in _export_funcs():
        raise ApiError(404, "یافت نشد")
    export_dir = os.path.join(str(settings.DATA_DIR), "exports")
    os.makedirs(export_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    name = f"{kind}_{stamp}.{fmt}"
    path = os.path.join(export_dir, name)
    _export_funcs()[kind](path, fmt)
    return path, name


def import_products_file(uploaded_file, update_existing=False):
    """Import products from a CSV/XLSX upload; returns ``(stats, errors)``."""
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in (".csv", ".xlsx", ".xlsm"):
        raise ApiError(400, "فقط فایل csv یا xlsx پذیرفته می‌شود")
    from inventory.excel_io import import_products
    export_dir = os.path.join(str(settings.DATA_DIR), "exports")
    os.makedirs(export_dir, exist_ok=True)
    tmp_path = os.path.join(export_dir, "import_tmp" + ext)
    with open(tmp_path, "wb") as out:
        for chunk in uploaded_file.chunks():
            out.write(chunk)
    try:
        good, stats, errors = import_products(tmp_path, update_existing=update_existing)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    if not good:
        # legacy behaviour: the whole error list travels in the error field
        raise ApiError(400, errors)
    return stats, errors[:30]


def import_template_file():
    """Generate the Excel import template; returns ``(path, filename)``."""
    return export_data_file("products", "xlsx")
