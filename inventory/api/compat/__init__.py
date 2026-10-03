# -*- coding: utf-8 -*-
"""Legacy-shape API endpoints — the routes ``static/js`` currently calls.

These adapters exist so the (excellent, untouched) frontend keeps working
byte-for-byte: every endpoint below returns the *exact* JSON shape the old
function-based views produced — ``ok(...)`` envelopes, wrapped create
payloads (``{product: {...}}``), plain JSON arrays, ``{items, summary}``
lists and Persian error messages in ``{"ok": false, "error": ...}``.

All of them delegate to :mod:`inventory.api.services`, the single source
of truth for business rules.  Nothing here contains logic of its own.

Split into one module per domain; this package re-exports the full adapter
surface so callers keep using ``inventory.api.compat`` unchanged.
Modules: common, products, sales, payments, repairs, tracking, calendar, reports, settings, uploads, backups_export."""

from .common import _body, _ok, _fail, _guard, _attachment
from .products import (
    api_products, api_product_detail, api_products_bulk_delete,
)
from .sales import api_sales, api_sale_detail, api_sales_bulk_delete
from .payments import (
    api_payments, api_payment_detail, api_payment_add, api_payment_settle_full, api_payments_bulk_delete,
)
from .repairs import (
    api_repairs, api_repair_detail, api_repairs_bulk_delete, api_repair_status,
)
from .tracking import (
    api_tracking, api_tracking_detail, api_tracking_bulk_delete,
)
from .calendar import api_calendar, api_calendar_day
from .reports import api_monthly_activity
from .settings import (
    api_brands, api_brands_delete, api_settings, api_settings_site_icon,
)
from .uploads import api_upload, serve_image
from .backups_export import (
    export_file, api_import_products, api_import_template, api_backups, api_backups_create,
    api_backups_upload, api_backups_download, api_backups_restore, api_backups_delete, api_database_info,
    api_database_clear,
)

__all__ = [
    '_body', '_ok', '_fail', '_guard', '_attachment', 'api_products',
    'api_product_detail', 'api_products_bulk_delete', 'api_sales', 'api_sale_detail', 'api_sales_bulk_delete', 'api_payments',
    'api_payment_detail', 'api_payment_add', 'api_payment_settle_full', 'api_payments_bulk_delete', 'api_repairs', 'api_repair_detail',
    'api_repairs_bulk_delete', 'api_repair_status', 'api_tracking', 'api_tracking_detail', 'api_tracking_bulk_delete', 'api_calendar',
    'api_calendar_day', 'api_monthly_activity', 'api_brands', 'api_brands_delete', 'api_settings', 'api_settings_site_icon',
    'api_upload', 'serve_image', 'export_file', 'api_import_products', 'api_import_template', 'api_backups',
    'api_backups_create', 'api_backups_upload', 'api_backups_download', 'api_backups_restore', 'api_backups_delete', 'api_database_info',
    'api_database_clear',
]
