"""کمک‌تابع‌های مشترک — پورت‌شده از app.py قدیمی."""
import datetime
import os

from django.conf import settings

from inventory.jalali import (
    MONTH_NAMES, WEEKDAY_NAMES, fa_num, gregorian_to_jalali, parse_jalali_date,
)

IMG_DIR = settings.IMG_DIR
BACKUP_DIR = settings.BACKUP_DIR

SALE_TYPE_FA = {"person": "حضوری", "online": "آنلاین"}

# «تسویه کامل» / «بیعانه» / «اعتباری» — used by the API, Excel export and
# the frontend (labels travel from the API).
PAYMENT_TYPE_FA = {
    "cash": "تسویه کامل",
    "deposit": "بیعانه",
    "credit": "اعتباری",
}

# Buy-now-pay-later services: key -> (Persian label, code prefix).
# The stored tracking code is ``PREFIX-<raw code>`` so two services with the
# same raw code never collide.
CREDIT_PROVIDERS = {
    "snappay": ("اسنپ‌پی", "S"),
    "digipay": ("دیجی‌پی", "D"),
    "torob": ("ترب‌پی", "T"),
}

# ---------------------------------------------------------------- credit
def credit_provider_fa(provider):
    """Persian label of a credit provider key, or ``""`` when unknown."""
    return CREDIT_PROVIDERS.get(provider, ("", ""))[0]


def credit_prefix(provider):
    """Uppercase tracking-code prefix of a provider (``S``/``D``/``T``)."""
    return CREDIT_PROVIDERS.get(provider, ("", ""))[1]


def normalize_tracking_code(raw):
    """Strip and convert Persian/Arabic digits to English digits."""
    text = str(raw or "").strip()
    return text.translate(
        str.maketrans(
            "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"
        )
    )


def build_tracking_code(provider, raw):
    """``PREFIX-<raw>`` for storage; never doubles an already-present prefix.

    ``provider`` must be a valid CREDIT_PROVIDERS key.  ``raw`` is the raw,
    already-normalized code typed by the user.
    """
    prefix = credit_prefix(provider)
    if not prefix:
        return raw
    if raw.upper().startswith(prefix + "-"):
        return raw
    return f"{prefix}-{raw}"


def raw_tracking_code(stored):
    """The user-typed part of a stored ``PREFIX-<raw>`` tracking code."""
    stored = str(stored or "")
    for prefix in ("S-", "D-", "T-"):
        if stored.upper().startswith(prefix):
            return stored[len(prefix):]
    return stored


_TRACKING_RE = r"^[A-Za-z0-9._-]+$"
_TRACKING_MAX_LEN = 56


def validate_tracking_code(provider, raw):
    """Validate a raw tracking code for ``provider``; return normalized code.

    Raises ``ApiError`` with the exact Persian messages from the spec.
    """
    from inventory.api.services.common import ApiError

    if not provider or provider not in CREDIT_PROVIDERS:
        raise ApiError(400, "سرویس اعتباری را انتخاب کنید")
    code = normalize_tracking_code(raw)
    if not code:
        raise ApiError(400, "کد رهگیری پرداخت را وارد کنید")
    if len(code) > _TRACKING_MAX_LEN:
        raise ApiError(
            400, "کد رهگیری نمی‌تواند بیش از ۵۶ نویسه باشد"
        )
    import re

    if not re.match(_TRACKING_RE, code):
        raise ApiError(
            400,
            "کد رهگیری فقط می‌تواند شامل حروف انگلیسی، عدد، نقطه و خط تیره باشد",
        )
    return code

STATUS_FA = {
    "received": "دریافت شده", "in_progress": "در حال تعمیر",
    "waiting_parts": "انتظار قطعه", "done": "آماده تحویل", "delivered": "تحویل شده",
}
STATUS_COLOR = {
    "received": "blue", "in_progress": "amber", "waiting_parts": "purple",
    "done": "green", "delivered": "gray",
}
TRACKING_STATUS_COLOR = {
    "new": "blue", "ordered": "amber", "found": "green",
    "delivered": "gray", "cancelled": "red",
}
TRACKING_STATUS_FA = {
    "new": "جدید", "ordered": "سفارش داده شد", "found": "پیدا شد",
    "delivered": "تحویل شد", "cancelled": "لغو شد",
}


# ---------------------------------------------------------------- format
def fa_date(iso, with_weekday=False):
    if not iso:
        return ""
    try:
        y, m, d = (int(x) for x in str(iso)[:10].split("-"))
        datetime.date(y, m, d)
    except (ValueError, TypeError):
        return str(iso) if iso else ""
    jy, jm, jd = gregorian_to_jalali(y, m, d)
    if with_weekday:
        wd = WEEKDAY_NAMES[datetime.date(y, m, d).weekday()]
        return f"{wd} {fa_num(jd)} {MONTH_NAMES[jm - 1]} {fa_num(jy)}"
    return f"{fa_num(jy)}/{fa_num(f'{jm:02d}')}/{fa_num(f'{jd:02d}')}"


def fa_money(value):
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        n = 0
    s = f"{int(round(n)):,}".replace(",", "٬")
    return fa_num(s)


# ---------------------------------------------------------------- parse
def clean(value):
    return str(value or "").strip()


def to_int(value, default=0):
    try:
        return int(float(str(value).replace(",", "").replace("٬", "").strip() or default))
    except (TypeError, ValueError):
        return default


def to_float(value, default=0.0):
    try:
        return float(str(value).replace(",", "").replace("٬", "").strip() or default)
    except (TypeError, ValueError):
        return default


def to_en_digits(value):
    return str(value or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))


def to_en_phone(value):
    return str(value or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).strip()
# ---------------------------------------------------------------- files
def remove_image(fname):
    if not fname:
        return
    safe = os.path.basename(str(fname))
    p = os.path.join(IMG_DIR, safe)
    if os.path.isfile(p):
        try:
            os.remove(p)
        except OSError:
            pass


# ---------------------------------------------------------------- dicts
def product_dict(r):
    d = {
        "id": r.id,
        "name": r.name,
        "reference": r.reference,
        "office_code": r.office_code,
        "website_code": r.website_code,
        "brand": r.brand,
        "purchase_price": r.purchase_price,
        "available": 1 if r.available else 0,
        "is_available": bool(r.available),
        "supplier": r.supplier,
        "purchase_date": r.purchase_date,
        "notes": r.notes,
        "image": r.image,
        "created_at": str(r.created_at or ""),
        "updated_at": str(r.updated_at or ""),
        "purchase_date_fa": fa_date(r.purchase_date),
        "purchase_date_weekday": fa_date(r.purchase_date, with_weekday=True),
        "purchase_price_display": fa_money(r.purchase_price),
    }
    d["total_value"] = r.purchase_price or 0
    d["total_value_display"] = fa_money(d["total_value"])
    d["availability_fa"] = "موجود" if r.available else "ناموجود"
    return d


def today_iso():
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------- invoice
def invoice_code(sale_id, sale_date):
    """کد فاکتور نمایشی و پایدار: TT-<سال/ماه شمسی>-<شناسه فروش>."""
    if not sale_id:
        return ""
    try:
        y, m, d = (int(x) for x in str(sale_date)[:10].split("-"))
        jy, jm, _jd = gregorian_to_jalali(y, m, d)
        return f"TT-{jy}{jm:02d}-{sale_id:04d}"
    except (ValueError, TypeError):
        return f"TT-{sale_id:04d}"


def sale_dict(r, product=None):
    p = product or getattr(r, "product", None)
    paid_amount = float(r.paid_amount or 0)
    remaining = max(0.0, float(r.sale_price or 0) - paid_amount)
    d = {
        "id": r.id,
        "product_id": r.product_id,
        "sale_price": r.sale_price,
        "purchase_price": r.purchase_price,
        "profit": r.profit,
        "sale_date": r.sale_date,
        "customer": r.customer,
        "customer_phone": r.customer_phone,
        "sale_type": r.sale_type,
        "payment_type": r.payment_type,
        # the single amount paid so far
        "paid_amount": paid_amount,
        "paid_total": paid_amount,
        "paid_total_display": fa_money(paid_amount),
        "is_settled": 1 if r.is_settled else 0,
        "settled_at": r.settled_at or "",
        "notes": r.notes,
        "created_at": str(r.created_at or ""),
        "product_name": p.name if p else "",
        "product_image": p.image if p else "",
        "website_code": p.website_code if p else "",
        "office_code": p.office_code if p else "",
        "reference": p.reference if p else "",
        "brand": p.brand if p else "",
        "supplier": p.supplier if p else "",
        # تاریخ خرید محصول (تاریخ خرید ساعت) — برای کارت «اطلاعات ساعت»
        "purchase_date_fa": fa_date(p.purchase_date) if (p and p.purchase_date) else "",
        "sale_date_fa": fa_date(r.sale_date),
        "settled_at_fa": fa_date(r.settled_at) if r.settled_at else "",
        "sale_price_display": fa_money(r.sale_price),
        "profit_display": fa_money(r.profit),
        "sale_type_fa": SALE_TYPE_FA.get(r.sale_type, r.sale_type),
        "payment_type_fa": PAYMENT_TYPE_FA.get(r.payment_type, r.payment_type),
        "payment_remaining": remaining,
        "payment_remaining_display": fa_money(remaining),
        "customer_phone_fa": fa_num(r.customer_phone),
        # credit sale fields (empty unless payment_type == "credit")
        "credit_provider": r.credit_provider or "",
        "credit_provider_fa": credit_provider_fa(r.credit_provider or ""),
        "credit_tracking_code": r.credit_tracking_code or "",
        "credit_tracking_code_raw": raw_tracking_code(r.credit_tracking_code or ""),
    }
    d["paid_breakdown_fa"] = ""
    d["purchase_price_display"] = fa_money(r.purchase_price)
    # ریز بیعانه: سند پرداخت مرتبط (یک سند به‌ازای هر فروش بیعانه‌ای)
    pay = r.payments.first() if r.payment_type == "deposit" else None
    dep_total = pay.total_amount if pay else None
    dep_paid = pay.paid_amount if pay else None
    dep_remaining = max(0.0, (dep_total or 0) - (dep_paid or 0)) if pay else None
    d["deposit_total_amount"] = dep_total
    d["deposit_paid_amount"] = dep_paid
    d["deposit_remaining"] = dep_remaining
    d["deposit_total_amount_display"] = fa_money(dep_total)
    d["deposit_paid_amount_display"] = fa_money(dep_paid)
    d["deposit_remaining_display"] = fa_money(dep_remaining)
    d["deposit_settled_at_fa"] = fa_date(pay.settled_at) if (pay and pay.settled_at) else ""
    d["invoice_code"] = r.invoice_code or invoice_code(r.id, r.sale_date)
    return d


def payment_dict(r):
    remaining = max(0.0, (r.total_amount or 0) - (r.paid_amount or 0))
    p = getattr(r, "product", None)
    d = {
        "id": r.id,
        "sale_id": r.sale_id,
        "product_id": r.product_id,
        "product_name": r.product_name,
        "customer_name": r.customer_name,
        "customer_phone": r.customer_phone,
        "total_amount": r.total_amount,
        "paid_amount": r.paid_amount,
        "pay_date": r.pay_date,
        "settled_at": r.settled_at or "",
        "notes": r.notes,
        "created_at": str(r.created_at or ""),
        "updated_at": str(r.updated_at or ""),
        "remaining": remaining,
        "paid_percent": (
            round(100 * (r.paid_amount / r.total_amount))
            if r.total_amount else 0
        ),
        "total_amount_display": fa_money(r.total_amount),
        "paid_amount_display": fa_money(r.paid_amount),
        "remaining_display": fa_money(remaining),
        "pay_date_fa": fa_date(r.pay_date),
        "settled_at_fa": fa_date(r.settled_at) if r.settled_at else "",
        "customer_phone_fa": fa_num(r.customer_phone),
    }
    if p:
        d["product_image"] = p.image or ""
        d["reference"] = p.reference or ""
        d["website_code"] = p.website_code or ""
        d["office_code"] = p.office_code or ""
        d["purchase_price"] = p.purchase_price or 0
        d["purchase_price_display"] = fa_money(p.purchase_price)
        d["purchase_date"] = p.purchase_date or ""
        d["purchase_date_fa"] = fa_date(p.purchase_date) if p.purchase_date else ""
    return d


def repair_dict(r):
    return {
        "id": r.id,
        "watch_name": r.watch_name,
        "watch_code": r.watch_code,
        "issue": r.issue,
        "delivery_date": r.delivery_date,
        "return_date": r.return_date,
        "customer_name": r.customer_name,
        "customer_phone": r.customer_phone,
        "is_warranty": 1 if r.is_warranty else 0,
        "is_warranty_fa": "بله" if r.is_warranty else "خیر",
        "status": r.status,
        "repair_price": r.repair_price,
        "image": r.image,
        "notes": r.notes,
        "created_at": str(r.created_at or ""),
        "delivery_date_fa": fa_date(r.delivery_date),
        "delivery_date_weekday": fa_date(r.delivery_date, with_weekday=True),
        "return_date_fa": fa_date(r.return_date),
        "status_fa": STATUS_FA.get(r.status, r.status),
        "status_color": STATUS_COLOR.get(r.status, "gray"),
        "repair_price_display": fa_money(r.repair_price),
        "customer_phone_fa": fa_num(r.customer_phone),
    }


def tracking_dict(r):
    return {
        "id": r.id,
        "item_name": r.item_name,
        "item_code": r.item_code,
        "customer_name": r.customer_name,
        "customer_phone": r.customer_phone,
        "price": r.price,
        "status": r.status,
        "notes": r.notes,
        "image": r.image,
        "created_at": str(r.created_at or ""),
        "price_display": fa_money(r.price),
        "status_fa": TRACKING_STATUS_FA.get(r.status, r.status),
        "status_color": TRACKING_STATUS_COLOR.get(r.status, "gray"),
        "customer_phone_fa": fa_num(r.customer_phone),
    }
