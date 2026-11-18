# -*- coding: utf-8 -*-
"""Dashboard report: monthly activity and per-channel sale counts."""

from .common import ApiError


def _validated_year(year_value):
    """Shared ``year`` query-parameter validation → Jalali year int.

    Empty/missing year → ``None`` (caller falls back to the current year).
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
    jy = _validated_year(year_value)
    if jy is None:
        months = get_monthly_activity()
        return months[0]["jy"], months
    return jy, get_monthly_activity(jy)


def sales_channels(year_value):
    """Per-month sale counts by channel: ``(year, months)``.

    Same validation as :func:`monthly_activity`; empty/missing year →
    the current Jalali year.
    """
    from inventory.reports import get_sales_channels
    jy = _validated_year(year_value)
    if jy is None:
        months = get_sales_channels()
        return months[0]["jy"], months
    return jy, get_sales_channels(jy)
