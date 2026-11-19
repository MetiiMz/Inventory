# -*- coding: utf-8 -*-
"""گزارش‌های نمایه (Dashboard) — پورت ORM از نسخه‌ی Flask."""
import datetime

from django.db.models import (
    Count, F, Q, Sum, Value, FloatField,
)
from django.db.models.functions import Coalesce

from inventory.jalali import MONTH_NAMES, gregorian_to_jalali, jalali_month_length, jalali_to_gregorian
from inventory.models import Payment, Product, Repair, Sale, Tracking


def get_dashboard_stats():
    # B6: the purchase-value box describes the in-stock inventory only —
    # sold watches no longer count toward it (consistent with the brand
    # table, which also counts available watches)
    prod = Product.objects.aggregate(
        total_purchase_value=Coalesce(
            Sum("purchase_price", filter=Q(available=True)),
            Value(0.0), output_field=FloatField()),
        available_count=Count("id", filter=Q(available=True)),
        product_count=Count("id"),
    )
    # the sales boxes aggregate actual sales of the current Jalali year
    today = datetime.date.today()
    jy_now, _, _ = gregorian_to_jalali(today.year, today.month, today.day)
    gy1, gm1, gd1 = jalali_to_gregorian(jy_now, 1, 1)
    gy2, gm2, gd2 = jalali_to_gregorian(jy_now + 1, 1, 1)
    sales = Sale.objects.filter(
        sale_date__gte=datetime.date(gy1, gm1, gd1).isoformat(),
        sale_date__lt=datetime.date(gy2, gm2, gd2).isoformat(),
    ).aggregate(
        sold_count=Count("id"),
        sold_profit=Coalesce(Sum("profit"), Value(0.0), output_field=FloatField()),
        sold_revenue=Coalesce(Sum("sale_price"), Value(0.0), output_field=FloatField()),
    )
    payments = Payment.objects.filter(total_amount__gt=F("paid_amount") + 0.001).aggregate(
        cnt=Count("id"),
        total_remaining=Coalesce(
            Sum(F("total_amount") - F("paid_amount")), Value(0.0), output_field=FloatField()),
    )
    return {
        "total_purchase_value": prod["total_purchase_value"] or 0,
        "available_count": prod["available_count"] or 0,
        "product_count": prod["product_count"] or 0,
        "sold_count": sales["sold_count"] or 0,
        "sold_profit": sales["sold_profit"] or 0,
        "sold_revenue": sales["sold_revenue"] or 0,
        "open_repairs": Repair.objects.exclude(status="delivered").count(),
        "open_tracking": Tracking.objects.exclude(status__in=["delivered", "cancelled"]).count(),
        "unpaid_count": payments["cnt"] or 0,
        "unpaid_total": payments["total_remaining"] or 0,
        "unavailable_count": Product.objects.filter(available=False).count(),
    }


def get_monthly_activity(jy=None):
    """۱۲ ماه یک سال جلالی (فروردین تا اسفند) برای نمودار خطی.

    اگر سال داده نشود، سال جلالی جاری استفاده می‌شود. ماه‌های بعد از
    ماه جاریِ همان سال با future=True و مقادیر صفر برمی‌گردند تا
    نمودار خط را فقط تا ماه جاری بکشد.
    """
    today = datetime.date.today()
    jy_now, jm_now, _ = gregorian_to_jalali(today.year, today.month, today.day)
    if jy is None:
        jy = jy_now

    ranges = _jalali_month_ranges(jy)

    # سرعت: کل بازه را یک‌باره می‌خوانیم و در پایتون دسته‌بندی می‌کنیم
    sales_rows = Sale.objects.values_list(
        "sale_date", "sale_price", "profit")
    prod_rows = Product.objects.exclude(purchase_date="").values_list("purchase_date", "purchase_price")

    sales_by_month = {}
    for sdate, sale_price, profit in sales_rows:
        if not sdate:
            continue
        key = _month_key(sdate)
        agg = sales_by_month.setdefault(key, [0.0, 0.0, 0])
        agg[0] += sale_price or 0
        agg[1] += profit or 0
        agg[2] += 1

    prod_by_month = {}
    for pdate, pprice in prod_rows:
        key = _month_key(pdate)
        prod_by_month[key] = prod_by_month.get(key, 0.0) + (pprice or 0)

    out = []
    for (jy, jm), start, end in ranges:
        s = sales_by_month.get((jy, jm), [0.0, 0.0, 0])
        future = (jy > jy_now) or (jy == jy_now and jm > jm_now)
        out.append({
            "jy": jy, "jm": jm,
            "label": MONTH_NAMES[jm - 1],
            "revenue": 0 if future else s[0],
            "profit": 0 if future else s[1],
            "count": 0 if future else s[2],
            "purchase_value": 0 if future else prod_by_month.get((jy, jm), 0.0),
            "future": future,
        })
    return out


def _month_key(iso):
    """ISO میلادی (YYYY-MM-DD) → (jy, jm) جلالی."""
    y, m, d = (int(x) for x in iso[:10].split("-"))
    return gregorian_to_jalali(y, m, d)[:2]


def _jalali_month_ranges(jy):
    """[( (jy, jm), start_iso, end_iso )] for فروردین تا اسفند of ``jy``."""
    ranges = []
    for jm in range(1, 13):
        gy1, gm1, gd1 = jalali_to_gregorian(jy, jm, 1)
        last = jalali_month_length(jy, jm)
        gy2, gm2, gd2 = jalali_to_gregorian(jy, jm, last)
        ranges.append((
            (jy, jm),
            datetime.date(gy1, gm1, gd1).isoformat(),
            datetime.date(gy2, gm2, gd2).isoformat(),
        ))
    return ranges


def get_sales_channels(jy=None):
    """تعداد فروش هر ماه جلالی به تفکیک نوع فروش و نحوه‌ی پرداخت.

    حضوری/آنلاین از ``sale_type`` و اعتباری از ``payment_type`` شمرده
    می‌شوند؛ این‌ها ابعاد مستقلی هستند، پس یک فروشِ آنلاینِ اعتباری در
    هر دو شمارنده می‌آید. فروش با ``sale_type`` ناشناخته در هیچ‌یک از
    دو نوع شمرده نمی‌شود. مثل ``get_monthly_activity``، ماه‌های بعد
    از ماه جاری با future=True و صفر برمی‌گردند.
    """
    today = datetime.date.today()
    jy_now, jm_now, _ = gregorian_to_jalali(today.year, today.month, today.day)
    if jy is None:
        jy = jy_now

    ranges = _jalali_month_ranges(jy)

    # سرعت: کل سال را یک‌باره می‌خوانیم و در پایتون دسته‌بندی می‌کنیم
    sales_rows = Sale.objects.values_list(
        "sale_date", "sale_type", "payment_type", "credit_provider")

    counts_by_month = {}
    for sdate, sale_type, payment_type, credit_provider in sales_rows:
        if not sdate:
            continue
        key = _month_key(sdate)
        agg = counts_by_month.setdefault(key, {"person": 0, "online": 0,
            "credit": 0, "credit_snappay": 0, "credit_digipay": 0,
            "credit_torob": 0})
        if sale_type == "person":
            agg["person"] += 1
        elif sale_type == "online":
            agg["online"] += 1
        if payment_type == "credit":
            agg["credit"] += 1
            if credit_provider == "snappay":
                agg["credit_snappay"] += 1
            elif credit_provider == "digipay":
                agg["credit_digipay"] += 1
            elif credit_provider == "torob":
                agg["credit_torob"] += 1

    out = []
    for (jy, jm), start, end in ranges:
        c = counts_by_month.get((jy, jm), {"person": 0, "online": 0,
            "credit": 0, "credit_snappay": 0, "credit_digipay": 0,
            "credit_torob": 0})
        future = (jy > jy_now) or (jy == jy_now and jm > jm_now)
        out.append({
            "jy": jy, "jm": jm,
            "label": MONTH_NAMES[jm - 1],
            "person_count": 0 if future else c["person"],
            "online_count": 0 if future else c["online"],
            "credit_count": 0 if future else c["credit"],
            "credit_snappay_count": 0 if future else c["credit_snappay"],
            "credit_digipay_count": 0 if future else c["credit_digipay"],
            "credit_torob_count": 0 if future else c["credit_torob"],
            "future": future,
        })
    return out


def get_brand_breakdown():
    """موجودی انبار و فروش‌های ثبت‌شده به تفکیک برند.

    دو دسته‌ی جدا:
    - موجودی انبار (Product با available=True): تعداد و جمع قیمت خرید —
      هر برندی که ساعت موجود داشته حتماً در خروجی حضور دارد.
    - فروش‌ها (Sale به تفکیک برندِ محصول): تعداد فروش‌رفته، جمع قیمت
      خریدِ همان فروش‌ها، جمع قیمت فروش و جمع سود.
      برندی که هیچ فروشی نداشته، هر چهار فیلد
      sold_count/sold_purchase_value/sold_value/sold_profit با هم
      None می‌شوند (در رابط کاربری خالی/— نمایش داده می‌شوند، نه صفر).
    برندی که فروشی داشته ولی دیگر موجودی نداشته هم نمایش داده
    می‌شود (موجودی صفر + اعداد واقعی فروش).
    """
    stock = {}
    for r in (
        Product.objects.filter(available=True)
        .values("brand")
        .annotate(
            in_stock_count=Count("id"),
            in_stock_value=Coalesce(Sum("purchase_price"), Value(0.0), output_field=FloatField()),
        )
    ):
        stock[r["brand"] or ""] = r

    sold = {}
    for r in Sale.objects.values("product__brand").annotate(
        sold_count=Count("id"),
        sold_purchase_value=Sum("purchase_price"),
        sold_value=Sum("sale_price"),
        sold_profit=Sum("profit"),
    ):
        sold[r["product__brand"] or ""] = r

    out = [
        {"brand": brand, "in_stock_count": r["in_stock_count"], "sold_count": None,
         "in_stock_value": r["in_stock_value"], "sold_purchase_value": None,
         "sold_value": None, "sold_profit": None}
        for brand, r in stock.items()
    ]
    by_brand = {row["brand"]: row for row in out}
    for brand, r in sold.items():
        row = by_brand.get(brand)
        if row is None:
            row = {"brand": brand, "in_stock_count": 0, "sold_count": None,
                   "in_stock_value": 0, "sold_purchase_value": None,
                   "sold_value": None, "sold_profit": None}
            by_brand[brand] = row
            out.append(row)
        row["sold_count"] = r["sold_count"]
        row["sold_purchase_value"] = r["sold_purchase_value"]
        row["sold_value"] = r["sold_value"]
        row["sold_profit"] = r["sold_profit"]
    out.sort(key=lambda row: (-row["in_stock_value"], row["brand"] or ""))
    return out

