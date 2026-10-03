# -*- coding: utf-8 -*-
"""Backup/export/import/database adapters: Excel in/out, db backups, database clear."""

import os

from django.conf import settings
from django.http import FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from inventory.api import services
from inventory.api.services import ApiError
from inventory.dbhelpers import (
    backup_db, clear_database, count_records, delete_backup, list_backups,
    restore_db,
)

from .common import _body, _ok, _fail, _guard, _attachment


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

