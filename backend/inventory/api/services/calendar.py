# -*- coding: utf-8 -*-
"""Jalali calendar: month grid and per-day event detail."""

import datetime

from inventory.jalali import (
    MONTH_NAMES, jalali_month_length, jalali_to_gregorian,
)
from inventory.models import Product, Repair, Sale
from inventory.utils import clean, fa_money, fa_num, to_int

from .common import ApiError


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
            "price_display": fa_money(s.sale_price),
            "purchase_price_display": fa_money(s.purchase_price),
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
