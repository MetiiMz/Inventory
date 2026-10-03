# -*- coding: utf-8 -*-
"""Sale domain: query, invoice codes, CRUD and settlement side effects."""

from django.db import transaction
from django.db.models import Q, QuerySet
from django.db.models.functions import Lower

from inventory.jalali import parse_jalali_date, today_iso
from inventory.models import Payment, Product, Sale
from inventory.utils import (
    SALE_TYPE_FA, clean, fa_money, invoice_code, to_en_phone,
    to_float, to_int,
)

from .common import (
    ApiError, _clean_ids, _merge_partial, _parse_iso_or_raise,
)


_SALE_SORT = {
    "date": "sale_date", "name": "product__name",
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

    sale_price = to_float(payload.get("sale_price"), 0.0)
    if sale_price <= 0:
        raise ApiError(400, "قیمت فروش را وارد کنید")

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
        if paid_now > sale_price + 0.001:
            raise ApiError(400, "جمع پرداخت‌ها نمی‌تواند از قیمت فروش بیشتر باشد "
                                f"({fa_money(sale_price)} تومان)")
        is_settled = False
    else:
        if paid_now > sale_price + 0.001:
            raise ApiError(400, "جمع پرداخت‌ها نمی‌تواند از قیمت فروش بیشتر باشد "
                                f"({fa_money(sale_price)} تومان)")
        # a complete cash sale; without a breakdown everything counts as cash
        if paid_now <= 0:
            paid_cash, paid_pos, paid_card2card = sale_price, 0.0, 0.0
        payment_kind = "cash"
        is_settled = True

    profit = sale_price - (product.purchase_price or 0)

    with transaction.atomic():
        sale = Sale.objects.create(
            product=product, sale_price=sale_price,
            purchase_price=product.purchase_price, profit=profit,
            sale_date=parsed, customer=customer,
            customer_phone=customer_phone, sale_type=sale_type,
            payment_type=payment_kind,
            paid_cash=paid_cash, paid_pos=paid_pos,
            paid_card2card=paid_card2card, is_settled=is_settled,
            notes=clean(payload.get("notes")), invoice_code=manual_invoice,
        )
        if payment_kind == "deposit":
            Payment.objects.create(
                sale=sale, product=product, product_name=product.name,
                customer_name=customer, customer_phone=customer_phone,
                total_amount=sale_price, paid_amount=paid_now,
                pay_date=parsed,
                notes=f"بیعانه فروش #{sale.id} — مانده: "
                      f"{fa_money(sale_price - paid_now)} تومان",
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
    product = sale.product

    sale_price = to_float(payload.get("sale_price"), 0.0)
    if sale_price <= 0:
        raise ApiError(400, "قیمت فروش را وارد کنید")
    payment_kind = clean(payload.get("payment_type")) or sale.payment_type
    if payment_kind not in ("cash", "deposit"):
        payment_kind = "cash"

    paid_cash = max(0.0, to_float(payload.get("paid_cash"), sale.paid_cash))
    paid_pos = max(0.0, to_float(payload.get("paid_pos"), sale.paid_pos))
    paid_card2card = max(0.0, to_float(payload.get("paid_card2card"), sale.paid_card2card))
    paid_now = paid_cash + paid_pos + paid_card2card
    if paid_now > sale_price + 0.001:
        raise ApiError(400, f"جمع پرداخت‌ها نمی‌تواند از قیمت فروش بیشتر باشد "
                            f"({fa_money(sale_price)} تومان)")
    if paid_now <= 0 and payment_kind == "cash":
        paid_cash, paid_pos, paid_card2card = sale_price, 0.0, 0.0

    purchase_price = to_float(payload.get("purchase_price"),
                              product.purchase_price if product else 0)
    profit = sale_price - purchase_price

    sale_date = clean(payload.get("sale_date")) or sale.sale_date
    parsed = _parse_iso_or_raise(sale_date, "تاریخ فروش معتبر نیست")
    sale_type = clean(payload.get("sale_type")) or sale.sale_type
    if sale_type not in SALE_TYPE_FA:
        sale_type = "person"

    customer = clean(payload.get("customer"))
    customer_phone = to_en_phone(clean(payload.get("customer_phone")))
    _validate_buyer(customer, customer_phone)

    sale.sale_price = sale_price
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
