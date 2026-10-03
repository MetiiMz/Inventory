# -*- coding: utf-8 -*-
"""Dashboard report adapter: monthly activity over /api/reports."""

from inventory.api import services

from .common import _ok, _guard


def api_monthly_activity(request):
    """GET /api/reports/monthly-activity?year=<jy> — 12 months for the chart."""
    def run():
        year, months = services.monthly_activity(request.GET.get("year"))
        return _ok(year=year, months=months)
    return _guard(run)

