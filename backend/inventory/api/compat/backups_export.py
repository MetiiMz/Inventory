# -*- coding: utf-8 -*-
"""Backup/export/import/database adapters: Excel in/out, db backups, database clear."""

import os
import io
import zipfile

from django.conf import settings
from django.http import FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from inventory.api import services
from inventory.api.services import ApiError
from inventory.dbhelpers import (
    backup_db, clear_database, count_records, delete_backup, list_backups,
    restore_db, _images_zip_path, _zip_name_is_safe,
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



def _validate_sqlite_db(path):
    """True if ``path`` is a readable TikoTime sqlite database."""
    import sqlite3
    try:
        conn = sqlite3.connect(path)
        conn.execute("SELECT COUNT(*) FROM products")
        conn.close()
    except sqlite3.Error:
        return False
    return True


def _write_images_zip(db_path, images):
    """Write ``images`` (list of ``(name, bytes)``) to the sidecar zip next to ``db_path``."""
    zip_path = _images_zip_path(db_path)
    directory = os.path.dirname(zip_path)
    tmp = os.path.join(
        directory, ".%s.%d.tmp" % (os.path.basename(zip_path), os.getpid()))
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED) as zf:
            for name, data in images:
                zf.writestr(name, data)
        os.replace(tmp, zip_path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _upload_zip(f, fname):
    """Handle a ``.zip`` upload: extract ``<stem>.db`` and the image files."""
    stem = os.path.splitext(fname)[0]
    db_name = stem + ".db"
    db_content = None
    images = []
    try:
        with zipfile.ZipFile(f) as zf:
            for member in zf.infolist():
                name = member.filename
                if member.is_dir():
                    continue
                if not _zip_name_is_safe(name):
                    return _fail("نام فایل در بکاپ نامعتبر است")
                if name == db_name:
                    db_content = zf.read(member)
                elif name.endswith(".db"):
                    return _fail("بکاپ حاوی چندین فایل پایگاه‌داده است")
                else:
                    images.append((name, zf.read(member)))
    except zipfile.BadZipFile:
        return _fail("فایل انتخاب‌شده یک فایل ZIP معتبر نیست")
    if db_content is None:
        return _fail("بکاپ حاوی فایل پایگاه‌داده (.db) نیست")
    os.makedirs(str(settings.BACKUP_DIR), exist_ok=True)
    target = os.path.join(str(settings.BACKUP_DIR), db_name)
    with open(target, "wb") as out:
        out.write(db_content)
    _write_images_zip(target, images)
    if not _validate_sqlite_db(target):
        os.remove(target)
        images_zip = _images_zip_path(target)
        if os.path.isfile(images_zip):
            os.remove(images_zip)
        return _fail("فایل انتخاب‌شده یک نسخه‌ی پشتیبان معتبر TikoTime نیست")
    return _ok(name=db_name)


@csrf_exempt
@require_POST
def api_backups_upload(request):
    """POST /api/backups/upload — upload a ``.db`` or ``.zip`` backup file."""
    f = request.FILES.get("file")
    if not f or not f.name:
        return _fail("فایلی انتخاب نشده است")
    fname = os.path.basename(f.name)
    if fname.endswith(".zip"):
        return _upload_zip(f, fname)
    if not fname.endswith(".db"):
        fname += ".db"
    os.makedirs(str(settings.BACKUP_DIR), exist_ok=True)
    target = os.path.join(str(settings.BACKUP_DIR), fname)
    with open(target, "wb") as out:
        for chunk in f.chunks():
            out.write(chunk)
    if not _validate_sqlite_db(target):
        os.remove(target)
        return _fail("فایل انتخاب‌شده یک نسخه‌ی پشتیبان معتبر TikoTime نیست")
    return _ok(name=fname)


def _backup_bundle_response(db_path, images_zip, safe):
    """Bundle ``<stem>.db`` + its images into a single in-memory ``<stem>.zip``."""
    stem = os.path.splitext(os.path.basename(db_path))[0]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.write(db_path, arcname=f"{stem}.db")
        with zipfile.ZipFile(images_zip) as izf:
            for member in izf.infolist():
                name = member.filename
                if member.is_dir() or not _zip_name_is_safe(name):
                    continue
                zf.writestr(f"images/{name}", izf.read(name))
    buf.seek(0)
    resp = FileResponse(buf, content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="{stem}.zip"'
    return resp


@require_GET
def api_backups_download(request, fname):
    """GET /api/backups/download/<fname> — attachment download."""
    safe = os.path.basename(fname)
    path = os.path.join(str(settings.BACKUP_DIR), safe)
    if not os.path.isfile(path):
        return _fail("یافت نشد", 404)
    images_zip = _images_zip_path(path)
    if os.path.isfile(images_zip):
        return _backup_bundle_response(path, images_zip, safe)
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

