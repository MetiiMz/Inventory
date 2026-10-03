# -*- coding: utf-8 -*-
"""Excel/CSV export and product import (openpyxl + excel_io)."""

import datetime
import os

from django.conf import settings

from .common import ApiError


def _export_funcs():
    from inventory.excel_io import (
        export_payments, export_products, export_repairs, export_sales,
        export_tracking,
    )
    return {
        "products": export_products,
        "repairs": export_repairs,
        "tracking": export_tracking,
        "payments": export_payments,
        "sales": export_sales,
    }


def export_data_file(kind, fmt):
    """Generate an export file; returns ``(path, filename)``."""
    if fmt not in ("xlsx", "csv") or kind not in _export_funcs():
        raise ApiError(404, "یافت نشد")
    export_dir = os.path.join(str(settings.DATA_DIR), "exports")
    os.makedirs(export_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    name = f"{kind}_{stamp}.{fmt}"
    path = os.path.join(export_dir, name)
    _export_funcs()[kind](path, fmt)
    return path, name


def import_products_file(uploaded_file, update_existing=False):
    """Import products from a CSV/XLSX upload; returns ``(stats, errors)``."""
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in (".csv", ".xlsx", ".xlsm"):
        raise ApiError(400, "فقط فایل csv یا xlsx پذیرفته می‌شود")
    from inventory.excel_io import import_products
    export_dir = os.path.join(str(settings.DATA_DIR), "exports")
    os.makedirs(export_dir, exist_ok=True)
    tmp_path = os.path.join(export_dir, "import_tmp" + ext)
    with open(tmp_path, "wb") as out:
        for chunk in uploaded_file.chunks():
            out.write(chunk)
    try:
        good, stats, errors = import_products(tmp_path, update_existing=update_existing)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    if not good:
        # legacy behaviour: the whole error list travels in the error field
        raise ApiError(400, errors)
    return stats, errors[:30]


def import_template_file():
    """Generate the Excel import template; returns ``(path, filename)``."""
    return export_data_file("products", "xlsx")
