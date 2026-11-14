# -*- coding: utf-8 -*-
"""Sale domain: query, invoice codes, CRUD and settlement side effects."""

from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from django.db.models.functions import Lower

from inventory.jalali import parse_jalali_date, today_iso
from inventory.models import Payment, Product, Sale
from inventory.utils import (
    CREDIT_PROVIDERS, SALE_TYPE_FA, clean, fa_money, invoice_code,
    raw_tracking_code, to_en_phone, to_float, to_int,
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

# A4: a cash sale must be paid in full — partial payment is a deposit
_CASH_PARTIAL_MSG = ("برای فروش نقدی جمع پرداخت‌ها باید برابر قیمت فروش باشد؛ "
                     "برای پرداخت ناقص «بیعانه» را انتخاب کنید")

# F1: a deposit needs an upfront amount — same rule on create and edit
_DEPOSIT_MIN_MSG = "برای فروش بیعانه، دست‌کم مبلغ بیعانه را وارد کنید"

# M1: moving straight between deposit and credit is forbidden
_DEPOSIT_CREDIT_SWITCH_MSG = (
    "تغییر مستقیم بین بیعانه و اعتباری ممکن نیست؛ "
    "فروش را حذف و دوباره ثبت کنید"
)

_LEGACY_BUCKETS = ("paid_cash", "paid_pos", "paid_card2card")


def _legacy_paid_sum(payload) -> float:
    """Sum of the legacy method buckets carried by a legacy API payload."""
    return (max(0.0, to_float(payload.get("paid_cash")))
            + max(0.0, to_float(payload.get("paid_pos")))
            + max(0.0, to_float(payload.get("paid_card2card"))))


def _has_legacy_breakdown(payload) -> bool:
    """True when a legacy client still sends the per-method amounts."""
    return any(field in payload for field in _LEGACY_BUCKETS)


def _resolve_credit_code(provider, raw, exclude_id=None) -> str:
    """Validate a raw credit tracking code, prefix it and enforce uniqueness.

    The stored value is ``PREFIX-<raw>`` (e.g. ``D-4546851``).  Uniqueness is
    case-insensitive on the stored value and excludes ``exclude_id`` (the sale
    being edited).  Raises :class:`ApiError` with the exact Persian messages.
    """
    from inventory.utils import build_tracking_code, validate_tracking_code

    stored = build_tracking_code(provider, validate_tracking_code(provider, raw))
    qs = Sale.objects.filter(credit_tracking_code__iexact=stored)
    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)
    if qs.exists():
        raise ApiError(400, "این کد رهگیری قبلاً ثبت شده است")
    return stored


def sale_queryset(params) -> QuerySet:
    """Filtered/ordered sale list.

    Parameters: ``q`` (product/customer/phone/codes/reference/invoice, also
    the stored credit tracking code), ``sale_type``, ``pay_method`` =
    ``cash`` | ``deposit`` | ``credit`` (legacy ``pos``/``card2card`` are
    ignored), ``credit_provider`` = ``snappay`` | ``digipay`` | ``torob``
    (implies credit), ``date_from``/``date_to``, ``sort`` + ``dir``.
    Deposits are always included regardless of settlement state.
    """
    q = clean(params.get("q", ""))
    sale_type = clean(params.get("sale_type", ""))
    pay_method = clean(params.get("pay_method", ""))
    credit_provider = clean(params.get("credit_provider", ""))
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
            | Q(credit_tracking_code__icontains=q)
        )
    if sale_type in SALE_TYPE_FA:
        qs = qs.filter(sale_type=sale_type)
    if pay_method == "cash":
        qs = qs.filter(payment_type="cash")
    elif pay_method == "deposit":
        qs = qs.filter(payment_type="deposit")
    elif pay_method == "credit":
        qs = qs.filter(payment_type="credit")
    # legacy pay_method values (pos / card2card) are ignored: no filter
    if credit_provider in CREDIT_PROVIDERS:
        qs = qs.filter(payment_type="credit", credit_provider=credit_provider)
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


def next_invoice_code(sale_date: str = "") -> str:
    """Preview of the next auto-generated invoice code (TT-<jy><jm>-<id>).

    ``sale_date`` (Jalali or ISO) comes from the form so the preview
    matches the code the sale will actually receive (B1).
    """
    last_id = Sale.objects.order_by("-id").values_list("id", flat=True).first() or 0
    iso = parse_jalali_date(sale_date) if sale_date else None
    return invoice_code(last_id + 1, iso or today_iso())


def _deposit_note(sale_id: int, remaining: float) -> str:
    """The auto-generated note of a deposit sale's receipt (keeps the legacy text)."""
    return (f"بیعانه فروش #{sale_id} — مانده: "
            f"{fa_money(remaining)} تومان")


def _sync_settlement(sale: Sale | None, payment: Payment | None = None) -> None:
    """Derive ``is_settled``/``settled_at`` on the sale (and its receipt).

    A balance of ``remaining <= 0.001`` counts as settled: ``settled_at`` is
    stamped with today's date (kept when it is already stamped); any open
    balance clears the stamp.  When a receipt is passed its ``total/paid`` is
    the source of truth; otherwise the sale's own ``paid_amount`` is used.
    Either row may be ``None`` (e.g. a standalone receipt has no sale).
    Must run inside ``transaction.atomic`` — reused by the payment endpoints.
    """
    if payment is not None:
        remaining = payment.total_amount - payment.paid_amount
        settled_at = payment.settled_at
    else:
        remaining = sale.sale_price - sale.paid_amount
        settled_at = sale.settled_at
    is_settled = remaining <= 0.001
    settled_at = (settled_at or today_iso()) if is_settled else ""
    if sale is not None:
        sale.is_settled = is_settled
        sale.settled_at = settled_at
        sale.save(update_fields=["is_settled", "settled_at"])
    if payment is not None:
        payment.settled_at = settled_at
        payment.save(update_fields=["settled_at", "updated_at"])


def create_sale(payload) -> Sale:
    """Register a sale — cash (complete) or deposit (creates a receipt).

    Transactional: creates the Sale row, the deposit Payment receipt when
    applicable, and flips the product to out-of-stock.
    """
    pid = to_int(payload.get("product_id"))
    if not pid:
        raise ApiError(400, "محصول انتخاب نشده است")

    pt = clean(payload.get("payment_type"))
    if pt not in ("cash", "deposit", "credit"):
        pt = "cash"
    payment_kind = pt

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

    paid_amount = 0.0
    credit_provider = ""
    credit_tracking_code = ""

    if payment_kind == "cash":
        # LEGACY API CLIENTS: a payload that still carries the per-method
        # buckets is validated as before, but the values are never stored.
        if _has_legacy_breakdown(payload):
            paid_now = _legacy_paid_sum(payload)
            if paid_now > sale_price + 0.001:
                raise ApiError(400, "جمع پرداخت‌ها نمی‌تواند از قیمت فروش بیشتر باشد "
                                        f"({fa_money(sale_price)} تومان)")
            if 0 < paid_now < sale_price - 0.001:
                raise ApiError(400, _CASH_PARTIAL_MSG)
        if "deposit_amount" in payload:
            deposit_now = max(0.0, to_float(payload.get("deposit_amount")))
            if deposit_now > sale_price + 0.001:
                raise ApiError(400, "جمع پرداخت‌ها نمی‌تواند از قیمت فروش بیشتر باشد "
                                    f"({fa_money(sale_price)} تومان)")
            if 0 < deposit_now < sale_price - 0.001:
                raise ApiError(400, _CASH_PARTIAL_MSG)
        paid_amount = sale_price
    elif payment_kind == "deposit":
        if "deposit_amount" in payload:
            paid_now = max(0.0, to_float(payload.get("deposit_amount")))
        elif _has_legacy_breakdown(payload):
            # LEGACY: the sum of the old buckets counts as the deposit.
            paid_now = _legacy_paid_sum(payload)
        else:
            paid_now = 0.0
        if paid_now <= 0:
            raise ApiError(400, _DEPOSIT_MIN_MSG)
        if paid_now > sale_price + 0.001:
            raise ApiError(400, "جمع پرداخت‌ها نمی‌تواند از قیمت فروش بیشتر باشد "
                                    f"({fa_money(sale_price)} تومان)")
        paid_amount = paid_now
    else:
        # credit: buy-now-pay-later via Snapp Pay / Digi Pay / Torob Pay.
        provider = clean(payload.get("credit_provider"))
        raw = clean(payload.get("credit_tracking_code"))
        credit_tracking_code = _resolve_credit_code(provider, raw)
        credit_provider = provider
        paid_amount = sale_price

    try:
        with transaction.atomic():
            # A7: lock the row and re-check — a stale tab, a second device or a
            # direct API call must not double-sell a watch that is already sold
            product = Product.objects.select_for_update().filter(id=pid).first()
            if product is None:
                raise ApiError(404, "محصول یافت نشد")
            if not product.available:
                raise ApiError(400, "این ساعت قبلاً فروخته شده است")
            profit = sale_price - (product.purchase_price or 0)
            sale = Sale.objects.create(
                product=product, sale_price=sale_price,
                purchase_price=product.purchase_price, profit=profit,
                sale_date=parsed, customer=customer,
                customer_phone=customer_phone, sale_type=sale_type,
                payment_type=payment_kind,
                paid_amount=paid_amount,
                credit_provider=credit_provider,
                credit_tracking_code=credit_tracking_code,
                is_settled=payment_kind != "deposit",
                notes=clean(payload.get("notes")), invoice_code=manual_invoice,
            )
            if not manual_invoice:
                # B1: the auto code is persisted at creation so it can never
                # change when the sale is edited later
                code = invoice_code(sale.id, sale.sale_date)
                # F3: a manual entry may already own this month's slot for this
                # id — append a numeric suffix until the code is unique
                candidate, n = code, 1
                while (Sale.objects.exclude(id=sale.id)
                       .filter(invoice_code=candidate).exists()):
                    n += 1
                    candidate = f"{code}-{n}"
                sale.invoice_code = candidate
                sale.save(update_fields=["invoice_code"])
            payment = None
            if payment_kind == "deposit":
                payment = Payment.objects.create(
                    sale=sale, product=product, product_name=product.name,
                    customer_name=customer, customer_phone=customer_phone,
                    total_amount=sale_price, paid_amount=paid_amount,
                    pay_date=parsed,
                    notes=_deposit_note(sale.id, sale_price - paid_amount),
                )
            # this watch is sold — it becomes out-of-stock
            Product.objects.filter(id=pid).update(available=False)
    except IntegrityError:
        # DB-level uniqueness race on the credit tracking code.
        raise ApiError(400, "این کد رهگیری قبلاً ثبت شده است")

    _sync_settlement(sale, payment)
    return sale


def update_sale(sale: Sale, payload) -> Sale:
    """Edit a sale (prices, buyer, methods, date, notes).

    Every omitted field falls back to the current value, so PUT and PATCH
    behave identically.  The linked deposit receipt is kept in sync with the
    sale: editing a deposit updates its receipt, switching cash→deposit
    creates one (an upfront amount is required, as on create), and switching
    deposit→cash settles the unpaid remainder into ``paid_amount``.  Settlement
    on the sale and the receipt is re-derived by ``_sync_settlement``.
    """
    # ``deposit_amount`` is a payload-only key (not stored), so it is excluded
    # from _merge_partial (which does getattr on the instance) and handled
    # below with an explicit fallback to the current paid amount.
    payload = _merge_partial(payload, sale, (
        "sale_price", "sale_date", "customer", "customer_phone",
        "sale_type", "payment_type", "purchase_price", "notes",
        "credit_provider", "credit_tracking_code",
    ))
    product = sale.product

    sale_price = to_float(payload.get("sale_price"), 0.0)
    if sale_price <= 0:
        raise ApiError(400, "قیمت فروش را وارد کنید")
    payment_kind = clean(payload.get("payment_type")) or sale.payment_type
    if payment_kind not in ("cash", "deposit", "credit"):
        payment_kind = "cash"
    was_deposit = sale.payment_type == "deposit"
    was_credit = sale.payment_type == "credit"

    # direct credit <-> deposit is forbidden
    if (was_deposit and payment_kind == "credit"
            or was_credit and payment_kind == "deposit"):
        raise ApiError(400, _DEPOSIT_CREDIT_SWITCH_MSG)

    paid_amount = float(sale.paid_amount or 0)
    credit_provider = sale.credit_provider or ""
    credit_tracking_code = sale.credit_tracking_code or ""
    sale_price_changed = sale_price != float(sale.sale_price or 0)

    if payment_kind == "cash":
        # LEGACY: legacy buckets are validated as before but never stored.
        if _has_legacy_breakdown(payload):
            legacy_sum = _legacy_paid_sum(payload)
            if legacy_sum > sale_price + 0.001:
                raise ApiError(400, f"جمع پرداخت‌ها نمی‌تواند از قیمت فروش بیشتر باشد "
                                    f"({fa_money(sale_price)} تومان)")
            if 0 < legacy_sum < sale_price - 0.001:
                raise ApiError(400, _CASH_PARTIAL_MSG)
            paid_amount = legacy_sum
        if "deposit_amount" in payload:
            deposit_now = max(0.0, to_float(payload.get("deposit_amount")))
            if deposit_now > sale_price + 0.001:
                raise ApiError(400, f"جمع پرداخت‌ها نمی‌تواند از قیمت فروش بیشتر باشد "
                                    f"({fa_money(sale_price)} تومان)")
            if 0 < deposit_now < sale_price - 0.001:
                raise ApiError(400, _CASH_PARTIAL_MSG)
            paid_amount = deposit_now
        # price change or deposit → cash: the full amount is settled now
        if sale_price_changed or was_deposit:
            paid_amount = sale_price
        credit_provider = ""
        credit_tracking_code = ""
        # a cash sale must be fully paid — reject partial legacy rows
        if paid_amount != sale_price:
            raise ApiError(400, _CASH_PARTIAL_MSG)
    elif payment_kind == "deposit":
        if "deposit_amount" in payload:
            paid_now = max(0.0, to_float(payload.get("deposit_amount")))
        elif _has_legacy_breakdown(payload):
            paid_now = _legacy_paid_sum(payload)
        else:
            paid_now = paid_amount
        if paid_now <= 0:
            raise ApiError(400, _DEPOSIT_MIN_MSG)
        if paid_now > sale_price + 0.001:
            raise ApiError(400, f"جمع پرداخت‌ها نمی‌تواند از قیمت فروش بیشتر باشد "
                                f"({fa_money(sale_price)} تومان)")
        paid_amount = paid_now
        credit_provider = ""
        credit_tracking_code = ""
    else:
        # credit: buy-now-pay-later; paid_amount == sale_price, settled.
        provider = clean(payload.get("credit_provider")) or credit_provider
        raw = clean(payload.get("credit_tracking_code")) or raw_tracking_code(credit_tracking_code)
        if not provider or provider not in CREDIT_PROVIDERS:
            raise ApiError(400, "سرویس اعتباری را انتخاب کنید")
        if not raw:
            raise ApiError(400, "کد رهگیری پرداخت را وارد کنید")
        credit_tracking_code = _resolve_credit_code(
            provider, raw, exclude_id=sale.id)
        credit_provider = provider
        paid_amount = sale_price

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
    sale.purchase_price = purchase_price
    sale.profit = profit
    sale.notes = clean(payload.get("notes"))
    sale.sale_date = parsed
    sale.customer = customer
    sale.customer_phone = customer_phone
    sale.sale_type = sale_type
    sale.payment_type = payment_kind
    sale.paid_amount = paid_amount
    sale.credit_provider = credit_provider
    sale.credit_tracking_code = credit_tracking_code

    # the receipt the sale pays in instalments against (deposit sales)
    receipt_paid = paid_amount if payment_kind == "deposit" else sale_price
    with transaction.atomic():
        payment = sale.payments.first()
        if payment is None:
            if payment_kind == "deposit":
                # cash/credit → deposit (or a receipt that was deleted)
                payment = Payment.objects.create(
                    sale=sale, product=product,
                    product_name=product.name if product else "",
                    customer_name=customer, customer_phone=customer_phone,
                    total_amount=sale_price, paid_amount=paid_amount,
                    pay_date=parsed,
                    notes=_deposit_note(sale.id, sale_price - paid_amount),
                )
        else:
            if payment_kind != "deposit":
                # deposit → cash/credit: close the receipt as settled today
                payment.total_amount = sale_price
                payment.paid_amount = sale_price
                payment.customer_name = customer
                payment.customer_phone = customer_phone
                payment.pay_date = parsed
                payment.notes = _deposit_note(sale.id, 0)
                payment.save(update_fields=[
                    "total_amount", "paid_amount", "customer_name",
                    "customer_phone", "pay_date", "notes", "updated_at"])
            else:
                # keep the receipt a faithful mirror of the deposit sale
                payment.total_amount = sale_price
                payment.paid_amount = paid_amount
                payment.customer_name = customer
                payment.customer_phone = customer_phone
                payment.pay_date = parsed
                if (not payment.notes
                        or payment.notes.startswith(f"بیعانه فروش #{sale.id}")):
                    payment.notes = _deposit_note(sale.id, sale_price - paid_amount)
                payment.save(update_fields=[
                    "total_amount", "paid_amount", "customer_name",
                    "customer_phone", "pay_date", "notes", "updated_at"])
        sale.save()
        _sync_settlement(sale, payment)

    return sale


def delete_sale(sale: Sale) -> None:
    """Delete a sale — the watch becomes available again (FK-cascades)."""
    pid = sale.product_id
    with transaction.atomic():
        sale.delete()
        # A7: the watch stays sold while any other sale still references it
        # (legacy double-sold rows from before the create_sale guard)
        if pid and not Sale.objects.filter(product_id=pid).exists():
            Product.objects.filter(id=pid).update(available=True)


def bulk_delete_sales(raw_ids) -> int:
    """Bulk-delete sales; every watch with no remaining sale becomes
    available again."""
    ids = _clean_ids(raw_ids)
    if not ids:
        raise ApiError(400, "موردی انتخاب نشده است")
    with transaction.atomic():
        pids = set(Sale.objects.filter(id__in=ids)
                   .values_list("product_id", flat=True))
        Sale.objects.filter(id__in=ids).delete()
        # A7: watches still referenced by another sale stay sold
        still_sold = set(Sale.objects.filter(product_id__in=pids)
                         .values_list("product_id", flat=True))
        free = pids - still_sold
        if free:
            Product.objects.filter(id__in=free).update(available=True)
    return len(ids)
