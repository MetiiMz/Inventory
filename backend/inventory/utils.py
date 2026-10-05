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
        "purchase_type": r.purchase_type,
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
        "paid_cash": r.paid_cash,
        "paid_pos": r.paid_pos,
        "paid_card2card": r.paid_card2card,
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
        "sale_date_fa": fa_date(r.sale_date),
        "settled_at_fa": fa_date(r.settled_at) if r.settled_at else "",
        "sale_price_display": fa_money(r.sale_price),
        "profit_display": fa_money(r.profit),
        "paid_total": (r.paid_cash or 0) + (r.paid_pos or 0) + (r.paid_card2card or 0),
        "sale_type_fa": SALE_TYPE_FA.get(r.sale_type, r.sale_type),
        "payment_type_fa": "بیعانه" if r.payment_type == "deposit" else "نقدی",
        "customer_phone_fa": fa_num(r.customer_phone),
    }
    d["paid_total_display"] = fa_money(d["paid_total"])
    d["paid_breakdown_fa"] = " + ".join(filter(None, [
        "نقدی" if d["paid_cash"] else "",
        "کارت‌خوان" if d["paid_pos"] else "",
        "کارت به کارت" if d["paid_card2card"] else "",
    ]))
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


# ---------------------------------------------------------------- ledger
def ledger_supplier_dict(r):
    """تأمین‌کننده بایگانی — با تعداد فاکتورهایش (Annotate در service).

    برای نمونه‌های بدون Annotate (جواب create/rename) از شمارش مستقیم
    relations استفاده می‌شود.
    """
    count = getattr(r, "invoice_count", None)
    if count is None:
        count = r.invoices.count()
    return {
        "id": r.id,
        "name": r.name,
        "invoice_count": count or 0,
    }


def ledger_line_dict(r):
    """یک خط فاکتور — line_total همیشه محاسبه می‌شود، هرگز از ذخیره خوانده نمی‌شود."""
    quantity = r.quantity or 1
    unit_price = r.unit_price or 0
    line_total = quantity * unit_price
    return {
        "id": r.id,
        "watch_name": r.watch_name,
        "reference": r.reference or "",
        "quantity": quantity,
        "quantity_display": fa_num(quantity),
        "unit_price": unit_price,
        "unit_price_display": fa_money(unit_price),
        "line_total": line_total,
        "line_total_display": fa_money(line_total),
    }


def ledger_invoice_dict(r, with_lines=False):
    """فاکتور بایگانی — مجموع‌ها همیشه از خطوط فعلی محاسبه می‌شوند (FR-007).

    ``images`` آرایه‌ی مرتبِ نام فایل‌های عکس (ترتیب صفحه) است؛ فرمت‌های
    نمایشی بقیه‌ی همان قرارداد ledger-api.md را دنبال می‌کند.
    """
    lines = list(r.lines.all())
    total_quantity = sum((l.quantity or 1) for l in lines)
    total_amount = sum(((l.quantity or 1) * (l.unit_price or 0)) for l in lines)
    d = {
        "id": r.id,
        "supplier_id": r.supplier_id,
        "purchase_date": r.purchase_date,
        "purchase_date_fa": fa_date(r.purchase_date),
        "images": [
            img.filename for img in r.images.all().order_by("order", "id")
        ],
        "total_quantity": total_quantity,
        "total_quantity_display": fa_num(total_quantity),
        "total_amount": total_amount,
        "total_amount_display": fa_money(total_amount),
    }
    if with_lines:
        d["created_at"] = str(r.created_at or "")
        d["lines"] = [ledger_line_dict(l) for l in lines]
    return d
