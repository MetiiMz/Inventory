# Contract: سطح import پایتون (منجمد)

**Feature**: `001-restructure-project-layout` | **Spec**: [../spec.md](../spec.md) | **انگیزه**: FR-009، FR-023، SC-007

تقسیم ماژول‌های حجیم فقط **درون** پکیج‌ها را عوض می‌کند. هر چیزی که امروز از بیرون قابل import است، باید عیناً با همان نام و همان مسیر کار کند — بدون تغییر حتی یک خط در صدا‌زننده‌ها (شامل تست‌ها).

## قاعده‌ی باز‌export

`backend/inventory/api/services/__init__.py` و `backend/inventory/api/compat/__init__.py` **همه‌ی** نام‌های عمومی قبلی را دوباره export می‌کنند، به‌طوری‌که هر سه شکل زیر کار کند:

```python
from inventory.api import services
services.create_sale(...)                 # صدازننده‌های موجود (compat، tests)
from inventory.api.services import ApiError, product_queryset   # import مستقیم
```

خودِ `compat` نیز داخلاً همان `services` را صدا می‌زند؛ الگوی `from inventory.api import services` در `compat.py:23` حفظ می‌شود.

## نام‌های منجمد که باید از ریشه‌ی پکیج قواعد import شوند

| گروه | نام‌ها |
|---|---|
| خطا | `ApiError` |
| کمکی‌های مشترک | `_clean_ids`, `_merge_partial`, `_parse_iso_or_raise` |
| محصولات | `product_queryset`, `_product_values`, `_check_duplicate_code`, `create_product`, `update_product`, `delete_product`, `bulk_delete_products` |
| فروش | `sale_queryset`, `_validate_buyer`, `next_invoice_code`, `create_sale`, `update_sale`, `delete_sale`, `bulk_delete_sales` |
| پرداخت | `payment_queryset`, `create_payment`, `update_payment`, `delete_payment`, `add_payment`, `settle_payment_full`, `bulk_delete_payments` |
| تعمیرات | `repair_queryset`, `_repair_values`, `create_repair`, `update_repair`, `delete_repair`, `bulk_delete_repairs`, `set_repair_status` |
| پیگیری | `tracking_queryset`, `_tracking_values`, `create_tracking`, `update_tracking`, `delete_tracking`, `bulk_delete_tracking` |
| برند و تنظیمات | `brands_list`, `brands_add`, `brands_delete`, `site_settings`, `save_settings`, `set_site_icon` |
| آپلود | `_save_uploaded`, `save_upload` |
| تقویم | `_repair_cell`, `calendar_month`, `calendar_day` |
| گزارش | `monthly_activity` |
| خروجی/ورودی | `_export_funcs`, `export_data_file`, `import_products_file`, `import_template_file` |

## نام‌های منجمد که باید از ریشه‌ی پکیج آداپتورها import شوند

| گروه | نام‌ها |
|---|---|
| کمکی‌ها | `_body`, `_ok`, `_fail`, `_guard`, `_attachment` |
| برند و تنظیمات | `api_brands`, `api_brands_delete`, `api_settings`, `api_settings_site_icon` |
| آپلود/تصویر | `api_upload`, `serve_image` |
| محصولات | `api_products`, `api_product_detail`, `api_products_bulk_delete` |
| فروش | `api_sales`, `api_sale_detail`, `api_sales_bulk_delete` |
| پرداخت | `api_payments`, `api_payment_detail`, `api_payment_add`, `api_payment_settle_full`, `api_payments_bulk_delete` |
| تعمیرات | `api_repairs`, `api_repair_detail`, `api_repairs_bulk_delete`, `api_repair_status` |
| پیگیری | `api_tracking`, `api_tracking_detail`, `api_tracking_bulk_delete` |
| تقویم/گزارش | `api_calendar`, `api_calendar_day`, `api_monthly_activity` |
| بکاپ/خروجی | `export_file`, `api_import_products`, `api_import_template`, `api_backups`, `api_backups_create`, `api_backups_upload`, `api_backups_download`, `api_backups_restore`, `api_backups_delete`, `api_database_info`, `api_database_clear` |

**تنها استثنا (تصمیم Q4)**: `api_brands_add` و `_page_ctx` حذف می‌شوند (بدون هیچ صدا‌زننده در کد/تست/فرانت؛ با `grep` روی کل درخت مثبت شد). `services.brands_add` **می‌ماند**.

## نام‌های منجمد بیرون از دو پکیج

| ماژول | چه چیزی نباید عوض شود | چه‌کسی مصرف می‌کند |
|---|---|---|
| `inventory.utils` | `product_dict`, `sale_dict`, `payment_dict`, `repair_dict`, `tracking_dict`, `remove_image`, `clean`, `to_int`, `to_float`, `to_en_phone`, `fa_num`, `fa_money`, `fa_date`, `invoice_code`, `SALE_TYPE_FA`, `STATUS_FA`, `TRACKING_STATUS_FA` — و ثابت‌های `IMG_DIR` / `BACKUP_DIR` (فقط منبعشان به settings تغییر می‌کند، نام‌ها و نوعشان می‌ماند) | `compat`, `services`, `tikotime/jinja.py`, `tests/test_utils.py` |
| `inventory.dbhelpers` | `get_setting`, `set_setting`, `get_brands`, `add_brand`, `delete_brand`, `backup_db`, `list_backups`, `restore_db`, `delete_backup`, `clear_database`, `count_records` — و ثابت‌های سطح ماژول `BACKUP_DIR` / `DB_PATH` (تست‌ها همین‌ها را patch می‌کنند) | `compat`, `services`, `views/pages.py`, `tests/test_dbhelpers_reports.py:59,60,122,123` |
| `inventory.models`, `inventory.reports`, `inventory.jalali`, `inventory.excel_io` | همه‌ی نام‌های فعلی | `services`, `compat`, `views/pages.py`, تست‌ها |
| `inventory.views` | `index`, `dashboard`, `products_page`, `calendar_page`, `repairs_page`, `sold_page`, `tracking_page`, `payments_page`, `settings_page`, `handler404` (باز‌export در `__init__.py`) | `tikotime/urls.py` |
| `tikotime.jinja` | globals و فیلترهای محیط قالب: `STATUS_FA`, `STATUS_COLOR`, `TRACKING_STATUS_FA`, `TRACKING_STATUS_COLOR`, `MONTH_NAMES`, `WEEKDAY_NAMES`, `fa_date`, `fa_money`, `fa_num`, `today_jalali`, `static`, `static_v`, `media`, `csrf_token`, `url` | همه‌ی قالب‌ها |
| `tikotime.urls` | همه‌ی مسیرها و نام‌ها + مسیر جدید استاتیک (افزوده می‌شود، چیزی حذف نمی‌شود جز `api/v1/`) | Django |
| `manage.py` | نام فایل و `DJANGO_SETTINGS_MODULE = "tikotime.settings"` (فقط محلش از ریشه به `backend/` می‌رود) | کاربر/CI |

## شیوه‌ی تأیید (SC-007)

پس از گام ۳ و ۴: `git diff --stat` باید فقط فایل‌های پکیج (جدید/حذف‌شده/`__init__.py`) را نشان بدهد و **صفر** تغییر در `compat/`، `tikotime/`، `views/pages.py`، `static/js/`، `templates/` و `tests/`. همچنین جست‌وجوی نامی هر تابع بعد از تقسیم باید فقط محل تعریف و importها را پیدا کند، نه تغییر صدا‌زننده.
