# Phase 1 Data Model — بازآرایی چیدمان پروژه و تقسیم ماژول‌های حجیم

**Feature**: `001-restructure-project-layout` | **Date**: 2026-09-28 | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

> **هیچ مدل داده‌ای، جدول، مهاجرت یا شکل پاسخ عوض نمی‌شود.** این فیچر Refactor ساختاری است؛ «موجودیت‌های» این سند، ساختار روی دیسک و سطح تماس بیرونی‌اند. مدل‌های `inventory/models.py` و مهاجرت‌های `inventory/migrations/` صفر تغییر دارند.

## ۱. موجودیت: محدوده‌های روی دیسک (On-disk areas)

| محدوده | مسیر پس از تغییر | کلید تنظیمات (منبع حقیقت) | چه‌کسی می‌سازد/می‌خواند | کنترل نسخه |
|---|---|---|---|---|
| داده‌ی اجرایی (ریشه) | `db/` | `DATA_DIR` | `settings.py` در زمان import (mkdir خودکار) | نادیده گرفته می‌شود (`db/`) |
| پایگاه‌داده | `db/db.sqlite3` | `DB_PATH` (قابل override با `TIKOTIME_DB`) | ORM + `dbhelpers` (raw sqlite) | نادیده |
| تصاویر آپلودشده | `db/images/` (۱۳۹ فایل موجود) | `IMG_DIR` | `services.save_upload`، `compat.serve_image`، `utils.remove_image` | نادیده |
| پشتیبان‌ها | `db/backups/` | `BACKUP_DIR` | `dbhelpers`، `compat` | نادیده |
| خروجی‌های اکسپورت | `db/exports/` | `DATA_DIR` + کمکی `_export_dir()` در `services/export_import.py` (**منبع واحد**؛ تنظیم مستقل `EXPORT_DIR` کنار گذاشته شد تا `override_settings(DATA_DIR=...)` — که تست‌های موجود به آن تکیه دارند — بی‌اثر نشود) | `services.export_data_file`, `import_template_file` | نادیده |
| دارایی‌های نمایشی | `frontend/static/{css,js,fonts}` | `STATIC_DIR` + `STATICFILES_DIRS` | استایتیک‌فایندرها + مسیر استاتیک صریح (R3) | **در مخزن** |
| قالب‌ها | `frontend/templates/*.html` (۹ فایل) | `TEMPLATES[0]["DIRS"]` | موتور Jinja2 | **در مخزن** |
| کد برنامه | `backend/{manage.py,requirements.txt,tests/,tikotime/,inventory/}` | `BASE_DIR` | پایتون (`sys.path[0]` = `backend/`) | **در مخزن** |

**قاعده‌ی اعتبارسنجی (FR-004)**: هر مسیر بالا فقط از `tikotime/settings.py` مشتق می‌شود؛ هیچ ماژولی نباید مسیر را از موقعیت فایل خودش بسازد. نقضِ امروزی: `inventory/utils.py:9-12` (از `__file__`) و `tikotime/jinja.py:38` (هارد‌کد `BASE_DIR/static`). و در گام ۵، **مجموعه‌ی** تصاویر پیش/پس از جابه‌جایی MUST صفر اختلاف بدهد (مقایسه با عدد ثابت مجاز نیست؛ چون تست‌های موجود در هر اجرا ۲ فایل ۵۸بایتی در داده‌ی واقعی می‌سازند — بخش Known issues در `.memory/INDEX.md`).

**جابه‌جایی**: `data/` یک‌جا به `db/` منتقل می‌شود (شامل فایل کهنه‌ی Flask `data/watch_inventory.db`)؛ محتوای هیچ فایلی تغییر نمی‌کند (FR-011). مجموعه‌ی داده تحت کنترل نسخه نیست، پس جابه‌جایی `mv` ساده است نه مهاجرت داده.

## ۲. موجودیت: ماژول‌های پکیج قواعد کسب‌وکار

`backend/inventory/api/services/` — یک ماژول برای هر دامنه، با `__init__.py` که **همه‌ی نام‌های عمومی قبلی** را دوباره export می‌کند (FR-023). نگاشت دقیق تابع→ماژول و محدوده‌ی خطوط فعلی در [research.md § R1](./research.md) ثبت شده است.

دامنه‌ها: `common` · `products` · `sales` · `payments` · `repairs` · `tracking` · `settings` · `uploads` · `calendar` · `reports` · `export_import`

**قواعد اعتبارسنجی**: هر ماژول ≤ ۴۰۰ خط (SC-006) · بدون تغییر امضا/شکل خروجی/پیام خطا/مرز تراکنش (FR-024) · انتقال عیناً بدون بازنویسی · `ApiError` در `common.py` و همچنین از ریشه‌ی پکیج قابل import · یک ماژول و یک پکیج هم‌نام هرگز هم‌زمان (FR-025).

## ۳. موجودیت: ماژول‌های پکیج آداپتورهای فرانت

`backend/inventory/api/compat/` — آینه‌ی همان واژگان دامنه‌ای (FR-022 + انحراف ثبت‌شده‌ی `calendar`/`reports`):

دامنه‌ها: `common` · `products` · `sales` · `payments` · `repairs` · `tracking` · `calendar` · `reports` · `settings` · `uploads` · `backups_export`

**قواعد اعتبارسنجی**: هیچ منطق کسب‌وکاری در این پکیج نیست (فقط آداپتور) · شکل پوسته‌ها (`_ok`/`_fail`) و کدهای وضعیت دست‌نخورده · برندها داخل `settings.py` (چون ردیف‌های `Setting` هستند) · دو حذف مجاز: `api_brands_add`، `_page_ctx` (بدون صدا‌زننده؛ مثبت‌شده با `grep` روی کد/تست/فرانت).

## ۴. موجودیت: مرجع رفتاری (Regression baseline)

| جزء | مسیر | قواعد |
|---|---|---|
| ماژول تست مرجع | `backend/tests/test_legacy_api_baseline.py` (جدید) | فقط مسیرهای لگاسی؛ سبز روی کد دست‌نخورده **پیش از گام ۱**؛ نخستین commit (SC-011)؛ داده‌ی ثابت با کارخانه‌های `tests/helpers.py` |
| مجموعه‌ی تست موجود | `backend/tests/*` (۱۰ فایل، ۱۴۷ تست) | فقط حذف `test_api_v1.py` (۱۶ تست، تنها فایل وابسته به `/api/v1/`)؛ هیچ ویرایش دیگری (FR-010) |
| مقایسه‌ی «یکسان» | — | برابری **کلید/مقدار**: کد وضعیت، نام و مقدار کلیدها، پیام خطای فارسی، ترتیب آیتم‌های لیست؛ ترتیب کلیدهای آبجکت آزاد (تصمیم Q2) |

## ۵. موجودیت: اجزای حذف‌شده (Removed components)

| جزء | مصداق دقیق | گام | جانشین/تضمین |
|---|---|---|---|
| لایه‌ی موازی API | `inventory/api/{views,serializers,fields,exceptions}.py` · `inventory/api/urls.py` · مسیر `api/v1/` در `tikotime/urls.py` · اپ `rest_framework` + بلاک `REST_FRAMEWORK` · ردیف `djangorestframework` · `tests/test_api_v1.py` | ۱ | قرارداد لگاسی دست‌نخورده (`contracts/legacy-api.md`) |
| دو تابع بی‌استفاده | `api_brands_add`، `_page_ctx` | ۱ | کارکردشان از قبل با `api_brands` (POST) پوشش داده شده؛ `services.brands_add` می‌ماند |
| ابزار production | ردیف‌های `gunicorn`/`whitenoise` · `WhiteNoiseMiddleware` · بلاک `STORAGES` + `WHITENOISE_MAX_AGE` · بخش «اجرا در حالت تولید» در README · پوشه‌ی `staticfiles/` + خط آن در `.gitignore` | ۲ | مسیر استاتیک صریح و مستقل از DEBUG (R3) |
| باقی‌مانده‌ی تلاش قبلی تقسیم | پوشه‌ی خالی `inventory/api/services/` + کش بایت‌کدش | ۳ | پکیج واقعی `services/` |

## ۶. انتقال حالت‌ها (ترتیب گام‌ها)

```
[وضعیت فعلی: ۱۴۷ تست سبز، یک API + یک لایه‌ی موازی]
   │
   ├─ گام ۰  + tests/test_legacy_api_baseline.py   → ۱۴۷+N سبز، commit #1   (پیش‌نیاز همه‌ی گام‌ها)
   ├─ گام ۱  − /api/v1/ + DRF + دو تابع بی‌استفاده  → ۱۴۷+N−۱۶ سبز، commit #2
   ├─ گام ۲  − gunicorn/whitenoise + مسیر استاتیک   → سبز (DEBUG=1 و DEBUG=0)، commit #3
   ├─ گام ۳  services.py → services/                → سبز، commit #4
   ├─ گام ۴  compat.py   → compat/                  → سبز، commit #5
   └─ گام ۵  db/ + backend/ + frontend/ (+ مسیرها)   → سبز + مرورگر + عملیات فایل، commit #6
                                                    ↓
                                 [وضعیت نهایی: ۳ محدوده، ۳ کتابخانه، یک قرارداد API]
```

**هر انتقال برگشت‌پذیر است**: هر گام یک commit مستقل؛ در صورت شکست، `git revert` همان commit و ادامه از حالت سبز قبلی. هیچ گامی «نیمه‌کاره» رها نمی‌شود (جابه‌جایی داده‌ها در گام ۵ یک‌جا و با برنامه‌ی خاموش انجام می‌شود).

## ۷. تغییرات صریحاً صفر

- مدل‌ها (`Product`, `Sale`, `Payment`, `Repair`, `Tracking`, `Setting`): صفر تغییر.
- مهاجرت‌ها: صفر فایل جدید (`makemigrations --check` باید «no changes» بدهد).
- شکل پاسخ‌ها، پیام‌های خطا، مسیرهای URL، نام توابع و امضاها: صفر تغییر (فقط نام ماژول‌های داخلی عوض می‌شود که از بیرون دیده نمی‌شود).
- تعداد کتابخانه‌های نصب‌شده: از ۶ به ۳ (`Django`, `Jinja2`, `openpyxl`).

