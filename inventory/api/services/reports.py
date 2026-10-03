# -*- coding: utf-8 -*-
"""Dashboard report: monthly activity."""

from .common import ApiError


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
