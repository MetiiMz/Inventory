# -*- coding: utf-8 -*-
"""Legacy-shape API endpoints — the routes ``static/js`` currently calls.

These adapters exist so the (excellent, untouched) frontend keeps working
byte-for-byte: every endpoint below returns the *exact* JSON shape the old
function-based views produced — ``ok(...)`` envelopes, wrapped create
payloads (``{product: {...}}``), plain JSON arrays, ``{items, summary}``
lists and Persian error messages in ``{"ok": false, "error": ...}``.

All of them delegate to :mod:`inventory.api.services`, the single source
of truth for business rules.  Nothing here contains logic of its own.
"""
import json
import mimetypes
import os

from django.conf import settings
from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from inventory.api import services
from inventory.api.services import ApiError
from inventory.dbhelpers import (
    backup_db, clear_database, count_records, delete_backup, list_backups,
    restore_db,
)
from inventory.utils import (
    product_dict, remove_image, repair_dict, sale_dict, tracking_dict,
)


def _body(request):
    """Parse the JSON request body (empty dict on any parse failure)."""
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return {}


def _ok(**data):
    """Legacy success envelope: ``{ok: true, ...data}``."""
    data.setdefault("ok", True)
    return JsonResponse(data)


def _fail(error, status=400):
    """Legacy error envelope: ``{ok: false, error: <persian message>}``."""
    return JsonResponse({"ok": False, "error": error}, status=status)


def _guard(fn):
    """Run ``fn(request, ...)`` and render :class:`ApiError` in legacy shape."""
    try:
        return fn()
    except ApiError as exc:
        return _fail(exc.message, exc.status_code)


# =====================================================================
# Brands / upload / images
# =====================================================================
@csrf_exempt
def api_brands(request):
    """GET lists brands; POST adds one (``{name}``) — legacy contract."""
    if request.method == "POST":
        return _guard(lambda: (services.brands_add(_body(request)), _ok())[1])
    return _guard(lambda: _ok(brands=services.brands_list()))


@csrf_exempt
@require_POST
def api_brands_delete(request):
    """POST /api/brands/delete — remove a brand."""
    return _guard(lambda: (services.brands_delete(_body(request)), _ok())[1])


@csrf_exempt
def api_upload(request):
    """POST /api/upload — image upload (JSON base64 or multipart) → ``{path}``."""
    return _guard(lambda: _ok(path=services.save_upload(request)))


def serve_image(request, fname):
    """GET /data/images/<name> — serve an uploaded image with caching."""
    safe = os.path.basename(fname)
    path = os.path.join(str(settings.IMG_DIR), safe)
    if not os.path.isfile(path):
        return _fail("یافت نشد", 404)
    ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
    resp = FileResponse(open(path, "rb"), content_type=ctype)
    resp["Cache-Control"] = "public, max-age=604800"
    return resp


# =====================================================================
# Products
# =====================================================================
def api_products(request):
    """GET lists products; POST creates one (wrapped in ``product``)."""
    if request.method == "POST":
        def run():
            product = services.create_product(_body(request))
            return _ok(product=product_dict(product))
        return _guard(run)

    rows = services.product_queryset(request.GET)
    return JsonResponse([product_dict(r) for r in rows], safe=False)


def api_product_detail(request, pid):
    """GET returns / PUT updates / DELETE destroys one product."""
    from inventory.models import Product
    product = Product.objects.filter(id=pid).first()
    if product is None:
        return _fail("محصول یافت نشد", 404)
    if request.method == "GET":
        return JsonResponse(product_dict(product), safe=False)
    if request.method == "PUT":
        def run():
            services.update_product(product, _body(request))
            product.refresh_from_db()
            return _ok(product=product_dict(product))
        return _guard(run)
    return _guard(lambda: (services.delete_product(product), _ok())[1])


@csrf_exempt
@require_POST
def api_products_bulk_delete(request):
    """POST /api/products/bulk-delete — ``{ids: [...]}`` → ``{deleted: n}``."""
    def run():
        deleted = services.bulk_delete_products(_body(request).get("ids"))
        return _ok(deleted=deleted)
    return _guard(run)


# =====================================================================
# Sales
# =====================================================================
def api_sales(request):
    """GET lists sales with a summary; POST creates a sale."""
    if request.method == "POST":
        def run():
            sale = services.create_sale(_body(request))
            return _ok(sale=sale_dict(sale, sale.product))
        return _guard(run)

    if request.GET.get("next_code"):
        return JsonResponse(
            {"next_invoice_code": services.next_invoice_code()})

    rows = list(services.sale_queryset(request.GET)[:500])
    items = [sale_dict(s) for s in rows]
    summary = {
        "count": len(items),
        "total_final": sum(x.get("final_price") or 0 for x in items),
        "total_profit": sum(x.get("profit") or 0 for x in items),
    }
    return JsonResponse({"items": items, "summary": summary})


def api_sale_detail(request, sid):
    """GET returns / PUT updates / DELETE destroys one sale."""
    from inventory.models import Sale
    sale = Sale.objects.filter(id=sid).select_related("product").first()
    if sale is None:
        return _fail("فروش یافت نشد", 404)
    if request.method == "GET":
        return JsonResponse({"ok": True, "sale": sale_dict(sale)})
    if request.method == "PUT":
        def run():
            services.update_sale(sale, _body(request))
            sale.refresh_from_db()
            return _ok(sale=sale_dict(sale, sale.product))
        return _guard(run)
    return _guard(lambda: (services.delete_sale(sale), _ok())[1])


@csrf_exempt
@require_POST
def api_sales_bulk_delete(request):
    """POST /api/sales/bulk-delete — ``{ids: [...]}`` → ``{deleted: n}``."""
    def run():
        deleted = services.bulk_delete_sales(_body(request).get("ids"))
        return _ok(deleted=deleted)
    return _guard(run)


# =====================================================================
# Payments
# =====================================================================
def api_payments(request):
    """GET lists payments with a summary; POST creates a record."""
    if request.method == "POST":
        def run():
            payment = services.create_payment(_body(request))
            from inventory.utils import payment_dict
            return _ok(payment=payment_dict(payment))
        return _guard(run)

    from inventory.utils import payment_dict
    rows = services.payment_queryset(request.GET)
    items = [payment_dict(p) for p in rows]
    summary = {
        "count": len(items),
        "total": sum(i["total_amount"] for i in items),
        "paid": sum(i["paid_amount"] for i in items),
        "remaining": sum(i["remaining"] for i in items),
    }
    return _ok(items=items, summary=summary)


def api_payment_detail(request, payid):
    """PUT updates / DELETE destroys one payment record."""
    from inventory.models import Payment
    from inventory.utils import payment_dict
    payment = Payment.objects.filter(id=payid).first()
    if not payment:
        return _fail("یافت نشد", 404)
    if request.method == "PUT":
        def run():
            services.update_payment(payment, _body(request))
            payment.refresh_from_db()
            return _ok(payment=payment_dict(payment))
        return _guard(run)
    if request.method == "DELETE":
        return _guard(lambda: (services.delete_payment(payment), _ok())[1])
    return _fail("متد پشتیبانی نمی‌شود", 405)


@csrf_exempt
@require_POST
def api_payment_add(request, payid):
    """POST /api/payments/<id>/add — pay an installment amount."""
    def run():
        from inventory.models import Payment
        from inventory.utils import payment_dict
        payment = Payment.objects.filter(id=payid).first()
        if not payment:
            raise ApiError(404, "یافت نشد")
        payment = services.add_payment(payment, _body(request))
        return _ok(payment=payment_dict(payment))
    return _guard(run)


@csrf_exempt
@require_POST
def api_payment_settle_full(request, payid):
    """POST /api/payments/<id>/settle-full — settle the whole balance."""
    def run():
        from inventory.models import Payment
        payment = Payment.objects.filter(id=payid).first()
        if not payment:
            raise ApiError(404, "یافت نشد")
        services.settle_payment_full(payment)
        return _ok()
    return _guard(run)


@csrf_exempt
@require_POST
def api_payments_bulk_delete(request):
    """POST /api/payments/bulk-delete — ``{ids: [...]}`` → ``{deleted: n}``."""
    def run():
        deleted = services.bulk_delete_payments(_body(request).get("ids"))
        return _ok(deleted=deleted)
    return _guard(run)


# =====================================================================
# Repairs
# =====================================================================
def api_repairs(request):
    """GET lists repairs; POST creates one (wrapped in ``repair``)."""
    if request.method == "POST":
        def run():
            repair = services.create_repair(_body(request))
            return _ok(repair=repair_dict(repair))
        return _guard(run)

    rows = services.repair_queryset(request.GET)
    return JsonResponse([repair_dict(r) for r in rows], safe=False)


def api_repair_detail(request, rid):
    """GET returns / PUT updates / DELETE destroys one repair ticket."""
    from inventory.models import Repair
    repair = Repair.objects.filter(id=rid).first()
    if repair is None:
        return _fail("یافت نشد", 404)
    if request.method == "GET":
        return JsonResponse(repair_dict(repair), safe=False)
    if request.method == "PUT":
        def run():
            services.update_repair(repair, _body(request))
            repair.refresh_from_db()
            return _ok(repair=repair_dict(repair))
        return _guard(run)
    return _guard(lambda: (services.delete_repair(repair), _ok())[1])


@csrf_exempt
@require_POST
def api_repairs_bulk_delete(request):
    """POST /api/repairs/bulk-delete — ``{ids: [...]}`` → ``{deleted: n}``."""
    def run():
        deleted = services.bulk_delete_repairs(_body(request).get("ids"))
        return _ok(deleted=deleted)
    return _guard(run)


@csrf_exempt
@require_POST
def api_repair_status(request, rid):
    """POST /api/repairs/<id>/status — change status (+ return date)."""
    def run():
        from inventory.models import Repair
        repair = Repair.objects.filter(id=rid).first()
        if repair is None:
            raise ApiError(404, "یافت نشد")
        repair = services.set_repair_status(repair, _body(request))
        return _ok(repair=repair_dict(repair))
    return _guard(run)


# =====================================================================
# Tracking
# =====================================================================
def api_tracking(request):
    """GET lists tracking records; POST creates one (wrapped in ``tracking``)."""
    if request.method == "POST":
        def run():
            tracking = services.create_tracking(_body(request))
            return _ok(tracking=tracking_dict(tracking))
        return _guard(run)

    rows = services.tracking_queryset(request.GET)
    return JsonResponse([tracking_dict(r) for r in rows], safe=False)


def api_tracking_detail(request, tid):
    """GET returns / PUT updates / DELETE destroys one tracking record."""
    from inventory.models import Tracking
    tracking = Tracking.objects.filter(id=tid).first()
    if tracking is None:
        return _fail("یافت نشد", 404)
    if request.method == "GET":
        return JsonResponse(tracking_dict(tracking), safe=False)
    if request.method == "PUT":
        def run():
            services.update_tracking(tracking, _body(request))
            tracking.refresh_from_db()
            return _ok(tracking=tracking_dict(tracking))
        return _guard(run)
    return _guard(lambda: (services.delete_tracking(tracking), _ok())[1])


@csrf_exempt
@require_POST
def api_tracking_bulk_delete(request):
    """POST /api/tracking/bulk-delete — ``{ids: [...]}`` → ``{deleted: n}``."""
    def run():
        deleted = services.bulk_delete_tracking(_body(request).get("ids"))
        return _ok(deleted=deleted)
    return _guard(run)


# =====================================================================
# Calendar / dashboard report
# =====================================================================
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


def api_monthly_activity(request):
    """GET /api/reports/monthly-activity?year=<jy> — 12 months for the chart."""
    def run():
        year, months = services.monthly_activity(request.GET.get("year"))
        return _ok(year=year, months=months)
    return _guard(run)


# =====================================================================
# Export / import
# =====================================================================
def _attachment(path, name, mimetype):
    """File download response with UTF-8 safe Content-Disposition."""
    from urllib.parse import quote
    resp = FileResponse(open(path, "rb"), content_type=mimetype)
    quoted = quote(name)
    resp["Content-Disposition"] = (
        f"attachment; filename=\"{quoted}\"; filename*=UTF-8''{quoted}")
    return resp


@require_GET
def export_file(request, kind, fmt):
    """GET /export/<kind>.<fmt> — Excel/CSV download."""
    def run():
        path, name = services.export_data_file(kind, fmt)
        mime = ("application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet" if fmt == "xlsx" else "text/csv")
        return _attachment(path, name, mime)
    return _guard(run)


@csrf_exempt
@require_POST
def api_import_products(request):
    """POST /api/import/products — Excel/CSV product import."""
    def run():
        f = request.FILES.get("file")
        if not f or not f.name:
            raise ApiError(400, "فایلی انتخاب نشده است")
        stats, errors = services.import_products_file(
            f, request.POST.get("update_existing") == "1")
        return _ok(stats=stats, errors=errors)
    return _guard(run)


@require_GET
def api_import_template(request):
    """GET /api/import/template — the Excel import template download."""
    def run():
        path, name = services.import_template_file()
        return _attachment(
            path, "قالب_ورود_اطلاعات.xlsx",
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet")
    return _guard(run)


# =====================================================================
# Backups & database clear
# =====================================================================
@require_GET
def api_backups(request):
    """GET /api/backups — list available database backups."""
    return _guard(lambda: _ok(backups=list_backups()))


@csrf_exempt
@require_POST
def api_backups_create(request):
    """POST /api/backups/create — create a backup → ``{name}``."""
    from django.db import close_old_connections
    close_old_connections()
    target = backup_db()
    return _ok(name=os.path.basename(target))


@csrf_exempt
@require_POST
def api_backups_upload(request):
    """POST /api/backups/upload — upload a ``.db`` backup file."""
    f = request.FILES.get("file")
    if not f or not f.name:
        return _fail("فایلی انتخاب نشده است")
    fname = os.path.basename(f.name)
    if not fname.endswith(".db"):
        fname += ".db"
    os.makedirs(str(settings.BACKUP_DIR), exist_ok=True)
    target = os.path.join(str(settings.BACKUP_DIR), fname)
    with open(target, "wb") as out:
        for chunk in f.chunks():
            out.write(chunk)
    import sqlite3
    try:
        conn = sqlite3.connect(target)
        conn.execute("SELECT COUNT(*) FROM products")
        conn.close()
    except sqlite3.Error:
        os.remove(target)
        return _fail("فایل انتخاب‌شده یک نسخه‌ی پشتیبان معتبر TikoTime نیست")
    return _ok(name=fname)


@require_GET
def api_backups_download(request, fname):
    """GET /api/backups/download/<fname> — attachment download."""
    safe = os.path.basename(fname)
    path = os.path.join(str(settings.BACKUP_DIR), safe)
    if not os.path.isfile(path):
        return _fail("یافت نشد", 404)
    resp = FileResponse(open(path, "rb"), content_type="application/octet-stream")
    resp["Content-Disposition"] = f'attachment; filename="{safe}"'
    return resp


@csrf_exempt
@require_POST
def api_backups_restore(request):
    """POST /api/backups/restore — restore a backup (auto-backs up first)."""
    def run():
        from django.db import close_old_connections
        close_old_connections()
        good, err = restore_db(_body(request).get("name"))
        if not good:
            raise ApiError(400, err)
        return _ok()
    return _guard(run)


@csrf_exempt
@require_POST
def api_backups_delete(request):
    """POST /api/backups/delete — delete a backup file."""
    def run():
        good, err = delete_backup(_body(request).get("name"))
        if not good:
            raise ApiError(400, err)
        return _ok()
    return _guard(run)


@require_GET
def api_database_info(request):
    """GET /api/database/info — per-table record counts (clear preview)."""
    return _ok(counts=count_records())


@csrf_exempt
@require_POST
def api_database_clear(request):
    """POST /api/database/clear — wipe data for a new period (auto backup)."""
    from django.db import close_old_connections
    close_old_connections()
    counts = clear_database()
    return _ok(cleared=counts)


# =====================================================================
# Settings
# =====================================================================
@csrf_exempt
def api_settings(request):
    """GET reads store settings; POST persists the whitelisted keys."""
    if request.method == "POST":
        services.save_settings(_body(request))
        return _ok()
    return _ok(**services.site_settings())


@csrf_exempt
@require_POST
def api_settings_site_icon(request):
    """POST /api/settings/site-icon — ``{icon: "<filename>"}``."""
    icon = services.set_site_icon(_body(request).get("icon"))
    return _ok(icon=icon)
