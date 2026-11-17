# -*- coding: utf-8 -*-
"""Dashboard reports: monthly activity and sales channels."""

from .common import ApiError


def _validate_year(year_value):
    """Validate the ``year`` query parameter → Jalali year int (or None).

    Empty/missing year → None (the report falls back to the current year).
    Non-int → ApiError 400 "سال نامعتبر است".
    Outside 1300..1600 → ApiError 400 "سال خارج از بازه‌ی مجاز است".
    """
    if year_value is None or str(year_value).strip() == "":
        return None
    try:
        jy = int(str(year_value).strip())
    except (TypeError, ValueError):
        raise ApiError(400, "سال نامعتبر است")
    if not 1300 <= jy <= 1600:
        raise ApiError(400, "سال خارج از بازه‌ی مجاز است")
    return jy


def monthly_activity(year_value):
    """Validate the ``year`` query parameter and return ``(year, months)``.

    Empty/missing year → the current Jalali year.
    """
    from inventory.reports import get_monthly_activity
    jy = _validate_year(year_value)
    months = get_monthly_activity(jy)
    return months[0]["jy"], months


def sales_channels(year_value):
    """Validate ``year`` and return ``(year, months)`` for the sales-channels
    report (counts of in-person / online / credit sales per Jalali month).

    Empty/missing year → the current Jalali year. Same validation messages as
    :func:`monthly_activity`.
    """
    from inventory.reports import get_sales_channels
    jy = _validate_year(year_value)
    months = get_sales_channels(jy)
    return months[0]["jy"], months
