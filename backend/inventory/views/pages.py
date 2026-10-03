# -*- coding: utf-8 -*-
"""HTML pages — server-rendered templates, no business logic.

The pages exist only to serve the (untouched) frontend shell; every piece
of data on them is fetched client-side from the API endpoints in
:mod:`inventory.api.compat`.  The dashboard is the one page with
server-rendered data (first paint without a fetch round-trip).
"""
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import redirect, render

from inventory.dbhelpers import get_setting
from inventory.models import Payment, Product, Repair, Sale, Tracking
from inventory.reports import (
    get_brand_breakdown, get_dashboard_stats, get_monthly_activity,
)
from inventory.utils import product_dict, sale_dict


def page_ctx(request, active):
    """Base-template context — site identity plus the sidebar nav badges."""
    ctx = {
        "site_icon": get_setting("site_icon", ""),
        "store_name": get_setting("store_name", "") or "Tick O Time",
        "active": active,
    }
    if active:
        ctx.update(
            nav_badge_low=Product.objects.filter(available=False).count() or None,
            nav_badge_repairs=(
                Repair.objects.exclude(status="delivered").count() or None),
            nav_badge_unpaid=(
                Payment.objects.filter(
                    total_amount__gt=F("paid_amount") + 0.001).count() or None),
            nav_badge_tracking=(
                Tracking.objects.exclude(
                    status__in=["delivered", "cancelled"]).count() or None),
        )
    return ctx


def index(request):
    """Redirect ``/`` to the dashboard."""
    return redirect("/dashboard")


def dashboard(request):
    """Dashboard page — stats, 12-month chart, brand table, recent rows."""
    stats = get_dashboard_stats()
    monthly = get_monthly_activity()
    brands = get_brand_breakdown()
    sales_rows = (
        Sale.objects.select_related("product")
        .order_by("-sale_date", "-id")[:8]
    )
    purchase_rows = (
        Product.objects.exclude(purchase_date="")
        .order_by("-purchase_date", "-id")[:8]
    )
    ctx = page_ctx(request, "dashboard")
    ctx.update(
        stats=stats, monthly=monthly, brands=brands,
        recent_sales=[sale_dict(s) for s in sales_rows],
        recent_purchases=[product_dict(p) for p in purchase_rows],
    )
    return render(request, "dashboard.html", ctx)


def products_page(request):
    """Inventory page shell."""
    return render(request, "products.html", page_ctx(request, "products"))


def calendar_page(request):
    """Calendar page shell."""
    return render(request, "calendar.html", page_ctx(request, "calendar"))


def repairs_page(request):
    """Repairs page shell."""
    return render(request, "repairs.html", page_ctx(request, "repairs"))


def sold_page(request):
    """Sales page shell."""
    return render(request, "sold.html", page_ctx(request, "sold"))


def tracking_page(request):
    """Order-tracking page shell."""
    return render(request, "tracking.html", page_ctx(request, "tracking"))


def payments_page(request):
    """Payments page shell."""
    return render(request, "payments.html", page_ctx(request, "payments"))


def settings_page(request):
    """Settings page shell."""
    return render(request, "settings.html", page_ctx(request, "settings"))


def handler404(request, exception=None):
    """Unknown URL — JSON for API paths, redirect to the dashboard otherwise."""
    if request.path.startswith("/api/") or request.path.startswith("/export/"):
        return JsonResponse({"ok": False, "error": "یافت نشد"}, status=404)
    return redirect("/dashboard")
