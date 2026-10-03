# -*- coding: utf-8 -*-
"""Calendar adapters: month grid and per-day over /api/calendar."""

from inventory.api import services

from .common import _ok, _guard


def api_calendar(request):
    """GET /api/calendar?jy=&jm= — one Jalali month on the grid."""
    def run():
        return _ok(**services.calendar_month(
            request.GET.get("jy"), request.GET.get("jm")))
    return _guard(run)



def api_calendar_day(request):
    """GET /api/calendar/day?date=YYYY-MM-DD — full detail of one day."""
    def run():
        return _ok(**services.calendar_day(request.GET.get("date")))
    return _guard(run)

