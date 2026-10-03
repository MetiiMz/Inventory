# -*- coding: utf-8 -*-
"""Business-logic layer — the single source of truth for every write operation.

The legacy-shape adapters in :mod:`inventory.api.compat` (the ``/api/*``
routes the current frontend calls) call the functions in this module.
Rules enforced here, exactly as they behaved before:

* validation with the original Persian error messages (raised as
  :class:`ApiError`),
* transactional side effects (sale + deposit receipt creation, stock
  flip on sale/delete, cascade deletes, settlement sync between
  payments and sales),
* file housekeeping (removing orphaned images).

Reads the adapters share (calendar events, dashboard report
validation, Excel export/import, uploads) also live here, so the
adapter layer only decides *how* to serialize the result.

Split into one module per domain; this package re-exports the full public
surface so callers keep using ``inventory.api.services`` unchanged.
Modules: common, products, sales, payments, repairs, tracking, settings, uploads, calendar, reports, export_import."""

from .common import (
    ApiError, _clean_ids, _merge_partial, _parse_iso_or_raise,
)
from .products import (
    product_queryset, _product_values, _check_duplicate_code, create_product, update_product,
    delete_product, bulk_delete_products,
)
from .sales import (
    sale_queryset, _validate_buyer, next_invoice_code, create_sale, update_sale,
    delete_sale, bulk_delete_sales,
)
from .payments import (
    payment_queryset, create_payment, update_payment, delete_payment, add_payment,
    settle_payment_full, bulk_delete_payments,
)
from .repairs import (
    repair_queryset, _repair_values, create_repair, update_repair, delete_repair,
    bulk_delete_repairs, set_repair_status,
)
from .tracking import (
    tracking_queryset, _tracking_values, create_tracking, update_tracking, delete_tracking,
    bulk_delete_tracking,
)
from .settings import (
    brands_list, brands_add, brands_delete, site_settings, save_settings,
    set_site_icon,
)
from .uploads import _save_uploaded, save_upload
from .calendar import _repair_cell, calendar_month, calendar_day
from .reports import monthly_activity
from .export_import import (
    _export_funcs, export_data_file, import_products_file, import_template_file,
)

__all__ = [
    'ApiError', '_clean_ids', '_merge_partial', '_parse_iso_or_raise', 'product_queryset', '_product_values',
    '_check_duplicate_code', 'create_product', 'update_product', 'delete_product', 'bulk_delete_products', 'sale_queryset',
    '_validate_buyer', 'next_invoice_code', 'create_sale', 'update_sale', 'delete_sale', 'bulk_delete_sales',
    'payment_queryset', 'create_payment', 'update_payment', 'delete_payment', 'add_payment', 'settle_payment_full',
    'bulk_delete_payments', 'repair_queryset', '_repair_values', 'create_repair', 'update_repair', 'delete_repair',
    'bulk_delete_repairs', 'set_repair_status', 'tracking_queryset', '_tracking_values', 'create_tracking', 'update_tracking',
    'delete_tracking', 'bulk_delete_tracking', 'brands_list', 'brands_add', 'brands_delete', 'site_settings',
    'save_settings', 'set_site_icon', '_save_uploaded', 'save_upload', '_repair_cell', 'calendar_month',
    'calendar_day', 'monthly_activity', '_export_funcs', 'export_data_file', 'import_products_file', 'import_template_file',
]
