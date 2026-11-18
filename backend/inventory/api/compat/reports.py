# -*- coding: utf-8 -*-
"""Dashboard report adapters over /api/reports."""

from inventory.api import services

from .common import _ok, _guard


def api_monthly_activity(request):
    """GET /api/reports/monthly-activity?year=<jy> — 12 months for the chart."""
    def run():
        year, months = services.monthly_activity(request.GET.get("year"))
        return _ok(year=year, months=months)
    return _guard(run)


def api_sales_channels(request):
    """GET /api/reports/sales-channels?year=<jy> — per-month channel counts."""
    def run():
        year, months = services.sales_channels(request.GET.get("year"))
        return _ok(year=year, months=months)
    return _guard(run)
