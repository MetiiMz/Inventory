# Phase 0 Research — بازآرایی چیدمان پروژه و تقسیم ماژول‌های حجیم

**Feature**: `001-restructure-project-layout` | **Date**: 2026-09-28 | **Spec**: [spec.md](./spec.md)

> همه‌ی «NEEDS CLARIFICATION»های Technical Context پیش از این با پنج تصمیم جلسه‌ی شفاف‌سازی (بخش Clarifications در spec) حل شده‌اند؛ این سند تصمیم‌های باقی‌مانده‌ی سطح طراحی را با شاهدِ کد ثبت می‌کند. هیچ مورد باز (unresolved) باقی نمانده است.

## R1 — فهرست ماژول‌های پکیج قواعد کسب‌وکار (FR-021، FR-022)

**Decision**: `inventory/api/services.py` (۱۱۹۸ خط) به یک پکیج با این ماژول‌ها تقسیم می‌شود؛ تقسیم عیناً روی سرفصل‌های موجود خود فایل انجام می‌شود (بدون بازنویسی):

| ماژول | توابع (طبق سرفصل فعلی) | خطوط فعلی | تخمین پس از تقسیم |
|---|---|---|---|
| `common.py` | `ApiError`، `_clean_ids`، `_merge_partial`، `_parse_iso_or_raise` | ۴۵–۸۶ | ~۷۰ |
| `products.py` | `product_queryset`، `_product_values`، `_check_duplicate_code`، `create_product`، `update_product`، `delete_product`، `bulk_delete_products` | ۸۸–۲۵۷ | ~۲۰۰ |
| `sales.py` | `sale_queryset`، `_validate_buyer`، `next_invoice_code`، `create_sale`، `update_sale`، `delete_sale`، `bulk_delete_sales` | ۲۵۹–۵۱۸ | ~۲۹۰ |
| `payments.py` | `payment_queryset`، `create_payment`، `update_payment`، `delete_payment`، `add_payment`، `settle_payment_full`، `bulk_delete_payments` | ۵۲۰–۶۷۷ | ~۱۸۵ |
| `repairs.py` | `repair_queryset`، `_repair_values`، `create_repair`، `update_repair`، `delete_repair`، `bulk_delete_repairs`، `set_repair_status` | ۶۷۸–۸۰۲ | ~۱۵۵ |
| `tracking.py` | `tracking_queryset`، `_tracking_values`، `create_tracking`، `update_tracking`، `delete_tracking`، `bulk_delete_tracking` | ۸۰۳–۸۹۰ | ~۱۲۰ |
| `settings.py` | `brands_list`، `brands_add`، `brands_delete`، `site_settings`، `save_settings`، `set_site_icon` | ۸۹۱–۹۴۰ | ~۸۰ |
| `uploads.py` | `_save_uploaded`، `save_upload` | ۹۴۱–۱۰۰۲ | ~۹۰ |
| `calendar.py` | `_repair_cell`، `calendar_month`، `calendar_day` | ۱۰۰۳–۱۱۲۰ | ~۱۴۵ |
| `reports.py` | `monthly_activity` | ۱۱۲۱–۱۱۴۱ | ~۵۰ |
| `export_import.py` | `_export_funcs`، `export_data_file`، `import_products_file`، `import_template_file` | ۱۱۴۲–۱۱۹۸ | ~۸۵ |

**Rationale**: سرفصل‌های داخلی `services.py` عملاً همان تقسیم دامنه‌ای مورد نظر spec هستند (عناوین تأییدشده: Products، Sales، Payments، Repairs، Order tracking، Brands & store settings، Image upload، Jalali calendar events، Dashboard report، Excel/CSV export & import). تقسیم مکانیکی = کمترین ریسک تغییر رفتار (FR-024). بزرگ‌ترین ماژول (~۲۹۰ خط) با حاشیه‌ی خوب زیر سقف ۴۰۰ خط می‌ماند (SC-006).

**Alternatives considered**:
- تقسیم لایه‌ای (اعتبارسنجی/خواندن/نوشتن) → رد شد: دامنه‌ها را قاطی می‌کند و FR-021 یک-دامنه-در-یک-فایل را می‌خواهد.
- نگه‌داشتن `services.py` و استخراج فقط بخش‌های بزرگ → رد شد: SC-006 ایجاب می‌کند هر دامنه ماژول خودش را داشته باشد.
- نام‌های تلاش رهاشده (`tracking_items.py`، `backups.py`، `excel_io.py`) → فقط به‌عنوان مرجع: `tracking_items` دامنه‌ای در `services.py` ندارد؛ نام‌های فهرست تأییدشده‌ی spec (`export_import.py`، `uploads.py`) ترجیح داده شد.

## R2 — فهرست ماژول‌های پکیج آداپتورهای فرانت (FR-021، FR-022)

**Decision**: `inventory/api/compat.py` (۶۰۰ خط) به پکیجی با همان واژگان دامنه‌ای پکیج قواعد تقسیم می‌شود:

| ماژول | توابع | خطوط فعلی |
|---|---|---|
| `common.py` | `_body`، `_ok`، `_fail`، `_guard`، `_attachment` | ۳۴–۶۳ و ۴۳۷–۴۴۸ |
| `products.py` | `api_products`، `api_product_detail`، `api_products_bulk_delete` | ۱۳۸–۱۷۹ |
| `sales.py` | `api_sales`، `api_sale_detail`، `api_sales_bulk_delete` | ۱۸۰–۲۳۱ |
| `payments.py` | `api_payments`، `api_payment_detail`، `api_payment_add`، `api_payment_settle_full`، `api_payments_bulk_delete` | ۲۳۲–۳۱۲ |
| `repairs.py` | `api_repairs`، `api_repair_detail`، `api_repairs_bulk_delete`، `api_repair_status` | ۳۱۳–۳۶۸ |
| `tracking.py` | `api_tracking`، `api_tracking_detail`، `api_tracking_bulk_delete` | ۳۶۹–۴۱۰ |
| `calendar.py` | `api_calendar`، `api_calendar_day` | ۴۱۱–۴۲۵ |
| `reports.py` | `api_monthly_activity` | ۴۲۶–۴۳۶ |
| `settings.py` | `api_brands`، `api_brands_delete`، `api_settings`، `api_settings_site_icon` | ۹۶–۱۱۷ و ۵۸۷–۶۰۰ |
| `uploads.py` | `api_upload`، `serve_image` | ۱۱۸–۱۳۷ |
| `backups_export.py` | `export_file`، `api_import_products`، `api_import_template`، `api_backups*`، `api_database_info`، `api_database_clear` | ۴۴۸–۵۸۶ |

**Rationale**: تقارن کامل با پکیج قواعد (SC-009: «یافتن ماژول یک دامنه = ۱ گام»)؛ هر ماژول کوچک است و بزرگ‌ترین‌شان (~۱۴۰ خط) به‌راحتی زیر ۴۰۰ خط می‌ماند. برندها در ماژول `settings.py` می‌نشینند چون در لایه‌ی قواعد هم همان‌جا هستند و ذخیره‌سازی‌شان ردیف‌های `Setting` است.

**Deviation (ثبت‌شده در Complexity Tracking)**: فهرست FR-022 برای پکیج آداپتور فقط ۹ دامنه را نام برده و دو خانواده‌ی موجود در `compat.py` را ذکر نکرده است (`api_calendar`/`api_calendar_day` و `api_monthly_activity`). تصمیم: این‌ها به دو ماژول `calendar.py` و `reports.py` می‌روند (تقارن با دامنه‌های لایه‌ی قواعد) نه به `common.py`؛ چون ریختن‌شان در `common` اصل «یک دامنه = یک ماژول» را نقض می‌کرد و افزودن دو ماژول هیچ رفتاری را تغییر نمی‌دهد (FR-024).

**Alternatives considered**: گذاشتن تقویم/گزارش در `common.py` → رد شد. حذف آن‌ها → غیرمجاز (حذف غیرتأییدشده).

## R3 — سرو دارایی‌های استاتیک مستقل از DEBUG (FR-018، SC-001)

**Decision**: در `tikotime/urls.py` یک مسیر صریح اضافه می‌شود:

```python
from django.contrib.staticfiles.views import serve as serve_static  # noqa: F401
# ...
path("static/<path:path>", serve_static, {"insecure": True}),
```

**Evidence** (کد نصب‌شده‌ی Django 5.2.6، `.venv/.../django/contrib/staticfiles/views.py`):
`def serve(request, path, insecure=False, **kwargs):` → `if not settings.DEBUG and not insecure: raise Http404` و سپس `absolute_path = finders.find(normalized_path)`.
پس با `insecure=True` این ویو از **استایتیک‌فایندرها** (یعنی `STATICFILES_DIRS`) در هر حالتی سرو می‌کند.

**Rationale**: با وایت‌نویز، استاتیک در DEBUG=0 هم سرو می‌شد؛ حذف وایت‌نویز نباید این تضمین را به «فقط اگر DEBUG روشن باشد» تبدیل کند (تصمیم Q1 در spec). این راه بدون هیچ وابستگی جدید، پیشوند `/static/...` و چیدمان فایل‌ها را دست‌نخورده نگه می‌دارد. نکته‌ی مهم: وقتی DEBUG=1 باشد، هندلر خودِ `runserver` (مبتنی بر `django.contrib.staticfiles`) زودتر پاسخ می‌دهد و این مسیر فقط حالت DEBUG=0 را می‌پوشاند.

**Alternatives considered**:
- `django.views.static.serve` با `document_root` → رد شد: فقط یک پوشه را می‌بیند و استایتیک‌فایندرها را دور می‌زند.
- اتکا به هندلر پیش‌فرض `runserver` → رد شد: در DEBUG=0 بی‌صدا ۴۰۴ می‌دهد (دقیقاً حالتی که spec منع کرده).
- ثابت‌کردن DEBUG=True و حذف `DJANGO_DEBUG` → رد شد: همان مین پنهان باقی می‌ماند و مستندات فعلی هنوز توصیه می‌کند روی سرور خاموشش کنید؛ متن مستندات به‌جای آن اصلاح می‌شود.

## R4 — یک منبع حقیقت برای مسیرهای روی دیسک (FR-004، FR-011)

**Decision**: فقط `tikotime/settings.py` مسیرها را درست می‌کند:

```python
BASE_DIR   = Path(__file__).resolve().parent.parent      # -> <root>/backend
DATA_DIR   = BASE_DIR.parent / "db"                       # ریشه‌ی داده‌ی جدید
IMG_DIR    = DATA_DIR / "images"; BACKUP_DIR = DATA_DIR / "backups"
DB_PATH    = os.environ.get("TIKOTIME_DB") or str(DATA_DIR / "db.sqlite3")
STATIC_DIR = BASE_DIR.parent / "frontend" / "static"
TEMPLATES[0]["DIRS"] = [BASE_DIR.parent / "frontend" / "templates"]
```
و `inventory/utils.py` دیگر مسیر نسازد؛ مثل `inventory/dbhelpers.py` فقط از settings بخواند:
`IMG_DIR = settings.IMG_DIR` و `BACKUP_DIR = settings.BACKUP_DIR` (نام‌ها حفظ می‌شوند تا قرارداد تست‌ها نشکند).

**Evidence**:
- `inventory/utils.py:9-12` امروز مسیر تصاویر/پشتیبان را از `os.path.dirname(__file__)` می‌سازد (دو سطح بالاتر = ریشه‌ی پروژه). بعد از جابه‌جایی به `backend/` همان فرمول به `backend/data/...` اشاره می‌کند → **۱۳۵ تصویر موجود یتیم می‌شوند** و `remove_image` بی‌اثر می‌شود.
- `inventory/api/services.py:1162` و `:1177` پوشه‌ی خروجی را دستی از `settings.DATA_DIR` می‌سازند (دو جای موازی برای یک مسیر). در طرح نهایی این دو نقطه به **یک** کمکی `_export_dir()` در `services/export_import.py` تبدیل می‌شوند که همچنان از `settings.DATA_DIR` مشتق می‌شود؛ تنظیم مستقل `EXPORT_DIR` کنار گذاشته شد چون `override_settings(DATA_DIR=...)` — که `tests/test_services_misc.py:145,160,180` به آن تکیه دارند و طبق FR-010 قابل ویرایش نیستند — بی‌اثر می‌شد و تست‌ها در داده‌ی واقعی می‌نوشتند.
- `inventory/api/compat.py:126،513،533` و `views/pages.py` از `settings.*` می‌خوانند (درست).

**Rationale**: FR-004 یک منبع واحد می‌خواهد؛ الگوی درست از قبل در `dbhelpers.py` وجود دارد، پس تغییر «هم‌راستا کردن با الگوی موجود» است نه طراحی جدید. ثابت‌های سطح ماژول حفظ می‌شوند چون تست‌ها همان‌ها را patch می‌کنند (`tests/test_dbhelpers_reports.py:59,60,122,123`) و `override_settings(DATA_DIR=...)` رفتار امروزی را دارد (`tests/test_services_misc.py:145,160,180`).

**Alternatives considered**: ساختن symlink از `backend/data` به `db/` → رد شد (کوپلینگ پنهان و شکننده). انتقال ثابت‌ها به ماژول جدید → رد شد (سطح عمومی جدید و شکستن patch تست‌ها).

## R5 — مهر نسخه‌ی دارایی‌ها (FR-013، SC-008)

**Decision**: `tikotime/jinja.py:static_v` مسیر فایل را از `settings.STATIC_DIR` می‌خواند (نه `os.path.join(settings.BASE_DIR, "static")`).

**Evidence**: `tikotime/jinja.py:38` مسیر را هارد‌کد می‌کند؛ بعد از جابه‌جایی، `os.path.getmtime` با OSError می‌افتد و طبق خط ۴۲ همان تابع، آدرس **بدون `?v=`** برگردانده می‌شود — یعنی باگ «تغییرات CSS/JS دیده نمی‌شود» که در `.memory/JOURNAL.md` ثبت شده، بی‌صدا برمی‌گردد.

**Rationale**: کمترین تغییر (یک خط) با حفظ دقیق شکل خروجی `STATIC_URL + path + "?v=" + mtime`.

**Alternatives considered**: استفاده از `staticfiles.finders.find(path)` برای حل مسیر → رد شد (یک وابستگی اضافه در زمان رندر قالب و رفتار متفاوت برای فایل‌های نبوده)؛ حذف کامل کش‌باستینگ → رد شد (SC-008 آن را لازم دارد).

## R6 — فایل نادیده‌گرفتن‌ها (FR-012، FR-019)

**Decision**:
- در گام ۲: حذف دستور `staticfiles/` همراه با خود پوشه و کامنت مربوط به whitenoise؛
- در گام ۵: `data/` → `db/` و به‌روزرسانی کامنت «SQLite safety net».

**Evidence**: `.gitignore:14-21` (پوشه‌ی جمع‌آوری‌شده + `data/`). اگر محدوده‌ی داده به‌روز نشود، `db.sqlite3`، ۱۳۵ تصویر کاربر و فایل کهنه‌ی Flask (`data/watch_inventory.db`) قابل commit می‌شوند.

**Rationale**: FR-012 صریح است؛ `db/` جانشین `data/` می‌شود و نسخه‌ی کهنه‌ی Flask (`data/watch_inventory.db`) هم جزو همان مجموعه‌ی داده است و با آن جابه‌جا می‌شود.

## R7 — دستورهای اجرای تست پس از جابه‌جایی (FR-026، SC-003) — با شاهد تجربی

**Decision**: دو صورت مستند و هم‌ارز:
1. صورت رسمی هر گام (از داخل محدوده‌ی کد): `cd backend && ../.venv/bin/python manage.py test`
2. صورت از ریشه‌ی مخزن: `.venv/bin/python backend/manage.py test backend/tests`

**Evidence** (آزمایش واقعی روی همین درخت، با اجرای `manage.py` از یک دایرکتوری بیرونی به‌عنوان شبیه‌سازی حالت پس از جابه‌جایی):

| دستور آزمایش‌شده | نتیجه |
|---|---|
| `manage.py test <مسیر-دایرکتوری-تست‌ها> -p test_jalali.py` | `Found 14 test(s)` → `OK` ✅ |
| `manage.py test tests -p test_jalali.py` (برچسب پکیج، بدون مسیر) | `Found 14 test(s)` → `OK` ✅ |
| `manage.py test -p test_jalali.py` (**بدون برچسب**) | `Found 0 test(s)` → **`NO TESTS RAN`** ⚠️ |

مکانیزم (کد نصب‌شده): `DiscoverRunner.load_tests_for_label` در `django/test/runner.py:888-918` وقتی برچسب یک دایرکتوری موجود باشد `top_level_dir` را با `find_top_level()` حساب می‌کند؛ و `build_suite` وقتی برچسبی داده نشود از `"."` (یعنی cwd) کشف می‌کند.

**Rationale**: FR-026 «سبز بودن کل مجموعه بعد از هر گام» را می‌خواهد؛ ‏`backend/manage.py test` بدون برچسب از ریشه‌ی مخزن صفر تست پیدا می‌کند و خطر «سبزِ کاذب» دارد، پس دستور درست باید صریح باشد. صورت ۱ همان معنای امروزیِ `python manage.py test` را حفظ می‌کند (تطابق با معیار پذیرش spec).

**Alternatives considered**: `-t backend` (پرچم `--top-level-directory` وجود دارد، `runner.py:738-744`) → به‌عنوان صورت اصلی انتخاب نشد چون حالت بدون‌برچسبش با آن تأیید نشد و دو صورت بالا مستقیم آزموده شده‌اند. نگه‌داشتن یک `tests/` پوسته در ریشه → رد شد (چیدمان تکراری).

## R8 — ماژول تست مرجع (گام ۰) (FR-015، SC-002، SC-011)

**Decision**: فایل جدید `tests/test_legacy_api_baseline.py`، پیش از هر تغییر ساختاری افزوده و **سبز روی کد دست‌نخورده** commit می‌شود:
- `django.test.TestCase` + `self.client`، داده‌ی ثابت با کارخانه‌های موجود `tests/helpers.py` (`make_product`, `product_payload`, `sale_payload`, `today_iso`, `today_jalali`)؛
- یک متد تست برای هر گروه مسیر: products، sales، payments، repairs، tracking، brands، upload/images، calendar، reports/monthly-activity، export/import، backups، database info/clear، settings؛
- هر تست: کد وضعیت + **برابری کلید/مقدار** (کلیدهای نام‌دار و مقادیرشان، پیام خطای فارسی، ترتیب آیتم‌های لیست) — ترتیب کلیدهای داخل آبجکت اسمی نمی‌شود (تصمیم Q2)؛
- دامنه: فقط مسیرهای `/api/*`, `/export/*`, `/data/images/*`؛ **هیچ تستی برای `/api/v1/`**؛
- هیچ فایل تست موجودی تغییر نمی‌کند؛ تست DB جداگانه و موقت است (بدون دست‌زدن به داده‌ی واقعی، مطابق عادت تست‌های فعلی).

**Rationale**: FR-015 تصریح می‌کند این ماژول نخستین کار و نخستین commit باشد؛ SC-002/SC-011 همین را می‌سنجند. تست‌های موجود برای قرارداد لگاسی پراکنده‌اند (`tests/test_compat_contract.py` ۱۶ تست، `test_calendar_sales.py` ۳، `test_services_misc.py` ۱۵) ولی هیچ‌کدام همه‌ی مسیرها را پوشش نمی‌دهند.

**Alternatives considered**: فایل JSON مرجع ذخیره‌شده → رد شد (کهنه شدن و دیف پرنویز)؛ اسکریپت موقت بیرون از مخزن → رد شد (نگهبان دائمی نمی‌ماند).

## R9 — باقی‌مانده‌های روی دیسک و کش بایت‌کد (FR-025، FR-019)

**Decision**:
- گام ۲: حذف پوشه‌ی `staticfiles/` (خروجی جمع‌آوری‌شده، حتی شامل `rest_framework/` جمع‌آوری‌شده) طبق FR-019؛
- گام ۳: پیش از ساخت پکیج `services/`، حذف پوشه‌ی خالی `inventory/api/services/` و کش `__pycache__` آن که نام ماژول‌های یک تلاش رهاشده را دارد (`products, sales, payments, repairs, tracking, tracking_items, calendar, settings, uploads, backups, excel_io, common`) — هیچ فایل منبعی نظیرشان وجود ندارد؛
- گام ۵: پاک‌سازی همه‌ی `__pycache__/` پیش از جابه‌جایی فیزیکی تا کش کهنه با کد جدید قاطی نشود.

**Evidence**: `ls inventory/api/services/` → فقط `__pycache__` (بدون `__init__.py`)؛ `inventory/api/services.py` هم‌زمان موجود است. امروز پوشه (به‌عنوان namespace package) ماژول را سایه نمی‌اندازد چون ماژول بر namespace package اولویت دارد، ولی این ابهام باید حذف شود و ساخت پکیج واقعی بدون پاک کردنش گیج‌کننده است.

**Alternatives considered**: نگه‌داشتن پوشه (تهی بماند) → رد شد: نقض صریح FR-025 و منبع سردرگمی `git`/ابزارها.

## R10 — هم‌گام نگه‌داشتن مستندات و حافظه‌ی پروژه در هر گام (FR-027)

**Decision**: در هر گام، مستندات همان گام به‌روز می‌شود تا هیچ متن کهنه‌ای باقی نماند:
- گام ۰: هیچ تغییر مستندی لازم نیست (فقط افزودن فایل تست).
- گام ۱: حذف شرح `/api/v1/` و DRF از `README.md` (بولت بالای فایل + بلوک معماری بک‌اند) و از `.memory/INDEX.md`.
- گام ۲: حذف بخش «اجرا در حالت تولید» و ابزارهای production از `README.md`، به‌روزرسانی جدول متغیرهای محیطی (توصیه‌ی «روی سرور روی ۰ بگذارید» منقضی است)، پاک‌کردن ستون whitenoise در `.memory/INDEX.md`.
- گام ۳ و ۴: به‌روزرسانی بلوک چیدمان `inventory/api/` در `README.md` و `.memory/INDEX.md` به شکل پکیج‌ها.
- گام ۵: ریشه‌ی جدید در `README.md` (۳ محدوده)، مسیر داده‌ی پیش‌فرض (`db/db.sqlite3`) و دستور واحد اجرا؛ به‌روزرسانی `.memory/COMMANDS.md` و `.claude/PROGRESS.md` طبق عادت پروژه (هر دستور اجرا‌شده ثبت می‌شود).

**Evidence**: `README.md:5` (شرح DRF)، `:11-23` (بلوک معماری)، `:30` (پیش‌نیازها)، `:64-79` (اجرا در حالت تولید + جدول متغیرها)؛ `.memory/INDEX.md:17` («Django settings (SQLite in `data/`, whitenoise)»)، `:38-39` (مسیرهای `data/`)، و `.memory/INDEX.md:74,77` که مسیرهای قدیمی را نقل می‌کنند.

**Rationale**: FR-027 و قانون پروژه («هر دستور اجرا‌شده در `.memory/COMMANDS.md` ثبت شود»). مستندی که وضعیت گذشته را توصیف کند، خودش یک باگ است چون دستورها/مسیرهای نادرست را به آینده منتقل می‌کند.

## R11 — چیزهایی که عمداً دست‌نخورده می‌مانند

**Decision**: این‌ها حذف/تغییر نمی‌شوند چون در فهرست «حذف‌های تأییدشده» نیستند (قانون اساسی، قاعده‌ی ۲):
- `tikotime/wsgi.py` (فقط کامنت/داک‌استرینگش به gunicorn اشاره می‌کند؛ متنش به اجرای محلی اصلاح می‌شود، خودش می‌ماند)؛
- `django.contrib.staticfiles` در `INSTALLED_APPS` (فایندرها و سرو استاتیک به آن وابسته‌اند) و `STATIC_URL` / `STATICFILES_DIRS` / `STATIC_ROOT` (فقط مقدار مسیرها به‌روز می‌شود؛ `STATIC_ROOT` بی‌استفاده ولی بی‌ضرر می‌ماند و روی هیچ عملیاتی اثر ندارد)؛
- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `ALLOWED_HOSTS=["*"]`, `DEFAULT_AUTO_FIELD`, تنظیمات SQLite (WAL/`IMMEDIATE`), سقف‌های ۳۲ مگابایتی آپلود، `LANGUAGE_CODE`/`TIME_ZONE`؛
- پوشه‌های کمکی `inventory/management/commands/` و `inventory/templatetags/` (فقط `__init__.py` خالی دارند)؛ مدل‌ها و مهاجرت‌ها؛
- `manage.py` (بدون تغییر منطقی؛ بعد از جابه‌جایی فقط محلش عوض می‌شود).

**Rationale**: قاعده‌ی ۲ قانون اساسی «بدون حذف غیرمجاز» را سخت می‌گیرد و FR-020 هیچ چیز جدیدی هم نمی‌پذیرد؛ پس هر چیز بی‌مصرفی که در فهرست تأییدشده نیست، سر جایش می‌ماند. تنها متن‌ها (داک‌استرینگ/README) اصلاح می‌شوند.

**Alternatives considered**: پاک‌سازی «تمیزکاری» فرصت‌طلبانه (حذف `wsgi.py`، حذف پوشه‌های خالی، حذف `STATIC_ROOT`) → رد شد: خارج از فهرست تأییدشده و در تناقض با معیار SC-007 (۰ تغییر غیرضروری).

## R12 — روند تأیید هر گام (SC-001…SC-011)

**Decision**: هر گام دقیقاً این دروازه‌ها را رد می‌کند (با دستور صریح، مطابق R7):

| # | دروازه | دستور / کار | انتظار |
|---|---|---|---|
| ۱ | کل مجموعه‌ی تست | `cd backend && ../.venv/bin/python manage.py test` (پیش از گام ۵: `./.venv/bin/python manage.py test`) | تعداد پایه (۱۴۷) یا پایه منهای تست‌های لایه‌ی حذف‌شده، به‌علاوه‌ی تست‌های ماژول مرجع؛ همه سبز، بدون `NO TESTS RAN` |
| ۲ | سلامت تنظیمات | `python manage.py check` | `no issues` |
| ۳ | بازدید صفحه‌ها | دستی در مرورگر: ۸ صفحه + پنل Network | ۸/۸ رندر، ۰ درخواست ۴۰۴ برای css/js/فونت/عکس |
| ۴ | عملیات فایل‌محور | آپلود عکس، ساخت بکاپ، ریستور، اکسپورت/ایمپورت اکسل | موفق؛ فایل‌ها داخل محدوده‌ی داده |
| ۵ | استقلال از DEBUG (گام ۲) | `DJANGO_DEBUG=0 python manage.py runserver` سپس درخواست یک مسیر `/static/...` | ۲۰۰ (نه ۴۰۴) |
| ۶ | کم‌شدن وابستگی‌ها (گام ۱ و ۲) | نصب از صفر در venv موقت + جست‌وجوی ارجاع به حذف‌شده‌ها | نصب موفق با ۳ کتابخانه؛ ۰ ارجاع باقی‌مانده |
| ۷ | بی‌تغییری importها (گام ۳ و ۴) | `git diff` روی نقاط صدا‌زدن و فایل‌های تست | فقط فایل‌های پکیج جدید/قدیم + `__init__.py`؛ ۰ تغییر در صدا‌زننده‌ها |
| ۸ | بازگشت‌پذیری | یک commit مستقل برای هر گام با پیام روشن | `git log` قابل بازگشت با `git revert` |

**Rationale**: یکی‌یکی کردن دروازه‌ها با FR/SC مانع «سبزِ کاذب» می‌شود (خطر واقعی: اجرای تست بدون برچسب از ریشه، R7) و اثبات SC-002/SC-004/SC-011 را تکرارشدنی می‌کند. گام ۵ علاوه بر این‌ها سه بررسی ویژه دارد: آرگومان‌های path درخواست‌های واقعی، `TIKOTIME_DB=/tmp/...` برای تست بدون دست‌زدن به داده‌ی واقعی، و بررسی `git status` برای اطمینان از اینکه محدوده‌ی داده نادیده گرفته می‌شود.

## خلاصه‌ی تصمیم‌ها

| # | موضوع | تصمیم در یک خط |
|---|---|---|
| R1 | پکیج قواعد | ۱۱ ماژول دامنه‌ای + ` __init__.py` باز‌export‌کننده‌ی همه‌چیز (بزرگ‌ترین ~۲۹۰ خط) |
| R2 | پکیج آداپتورها | ۱۱ ماژول آینه‌وار؛ تقویم/گزارش دو ماژول مستقل (انحراف ثبت‌شده از فهرست FR-022) |
| R3 | استاتیک | مسیر صریح `static/<path:path>` با `staticfiles.views.serve(insecure=True)` |
| R4 | مسیرها | تنها منبع: `settings.py`؛ `utils.py` از settings می‌خواند، نه از `__file__` |
| R5 | کش‌باستینگ | `static_v()` از `settings.STATIC_DIR` می‌خواند |
| R6 | ignore | `data/`→`db/`؛ حذف `staticfiles/` |
| R7 | تست | از `backend/` → `python manage.py test`؛ از ریشه → `... test backend/tests` (بدون برچسب = ۰ تست) |
| R8 | مرجع | `tests/test_legacy_api_baseline.py` در گام ۰، فقط مسیرهای لگاسی، سبز روی کد دست‌نخورده |
| R9 | باقی‌مانده‌ها | حذف پوشه‌ی خالی `services/` + کش بایت‌کد؛ پاک‌سازی `__pycache__`ها پیش از جابه‌جایی |
| R10 | مستندات | هر گام مستندات همان گام را به‌روز می‌کند (README + حافظه‌ی پروژه) |
| R11 | دست‌نخورده‌ها | `wsgi.py`، `staticfiles` app، `STATIC_ROOT`، مدل‌ها/مهاجرت‌ها، پوشه‌های کمکی خالی |
| R12 | تأیید | ۸ دروازه‌ی صریح در هر گام (تست، check، مرورگر، فایل‌محور، DEBUG=0، وابستگی‌ها، دیف importها، commit)


