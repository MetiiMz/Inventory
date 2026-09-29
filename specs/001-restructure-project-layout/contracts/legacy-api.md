# Contract: قرارداد HTTP لگاسی (منجمد)

**Feature**: `001-restructure-project-layout` | **Spec**: [../spec.md](../spec.md) | **مرجع قابل اجرا**: `backend/tests/test_legacy_api_baseline.py`

این قرارداد در کل این Refactor **منجمد** است (FR-006، FR-008). تنها مصرف‌کننده‌ی آن فرانت فعلی (`frontend/static/js/*.js` + `frontend/templates/*.html`) است.

## قواعد پوسته‌ی پاسخ

| حالت | شکل بدنه | کد وضعیت |
|---|---|---|
| موفقیت عمومی | `{"ok": true, ...<کلیدهای داده>}` | ۲۰۰ |
| خطای قاعده‌ی کسب‌وکار | `{"ok": false, "error": "<پیام فارسی>"}` | کد خطای `ApiError` (معمولاً ۴۰۰) |
| مسیر ناشناخته | `{"ok": false, "error": "یافت نشد"}` | ۴۰۴ (فقط برای `/api/*` و `/export/*`؛ بقیه به `/dashboard` ریدایرکت می‌شوند) |
| فایل (تصویر/اکسپورت/بکاپ) | بدنه‌ی فایل + هدر `Content-Disposition` در دانلودها | ۲۰۰ |

**تعریف «بدون تغییر» (تصمیم Q2)**: برابری **کلید/مقدار** — کد وضعیت، نام و مقدار هر کلید، پیام‌های خطای فارسی و **ترتیب آیتم‌های داخل لیست‌ها** باید یکسان بمانند؛ ترتیب کلیدهای داخل یک آبجکت آزاد است (فرانت کلیدها را با نام می‌خواند). هیچ کلید جدیدی اضافه و هیچ کلید موجودی حذف یا تغییر نام نمی‌دهد.

## مسیرهای صفحه‌ها (HTML)

| مسیر | نام | توضیح |
|---|---|---|
| `/` | `index` | ریدایرکت به `/dashboard` |
| `/dashboard` | `dashboard` | تنها صفحه‌ای که آمار را سمت سرور رندر می‌کند |
| `/products` `/calendar` `/repairs` `/sold` `/tracking` `/payments` `/settings` | — | پوسته‌ی HTML؛ داده سمت کلاینت از `/api/*` می‌آید |

## مسیرهای API (پیشوندها منجمد: `/api/*`, `/export/*`, `/data/images/*`)

| مسیر | متدها | شکل پاسخ | نکته |
|---|---|---|---|
| `/api/brands` | GET, POST | `{ok, brands:[...]}` / `{ok:true}` | POST همان کاری را می‌کند که آداپتور بی‌استفاده‌ی `api_brands_add` می‌کرد |
| `/api/brands/delete` | POST | `{ok:true}` | `{name}` |
| `/api/upload` | POST | `{ok, path}` | JSON base64 یا multipart |
| `/data/images/<fname>` | GET | فایل | از `settings.IMG_DIR` سرو می‌شود (در گام ۵ به `db/images/`) |
| `/api/products` | GET, POST | `{items, summary}` / `{ok, product:{...}}` | |
| `/api/products/bulk-delete` | POST | `{ok, deleted:n}` | `deleted` = تعداد idهای ارسالی، نه تعداد سطرهای موجود |
| `/api/products/<pid>` | GET, PUT, DELETE | `{ok, product:{...}}` | |
| `/api/sales` | GET, POST | `{items, summary}` / `{ok, sale:{...}}` | ساخت فروش نقدی ← ناموجود؛ بیعانه ← رسید پرداخت وابسته |
| `/api/sales/bulk-delete` | POST | `{ok, deleted:n}` | حذف فروش، موجودی را برمی‌گرداند |
| `/api/sales/<sid>` | GET, PUT, DELETE | `{ok, sale:{...}}` | |
| `/api/payments` | GET, POST | `{items, summary}` / `{ok, payment:{...}}` | |
| `/api/payments/bulk-delete` | POST | `{ok, deleted:n}` | |
| `/api/payments/<payid>` | PUT, DELETE | `{ok, payment:{...}}` | بدون GET (در قرارداد فعلی) |
| `/api/payments/<payid>/add` | POST | `{ok, payment:{...}}` | افزودن قسط |
| `/api/payments/<payid>/settle-full` | POST | `{ok, payment:{...}}` | تسویه‌ی کامل؛ فروش وابسته `is_settled` می‌شود |
| `/api/repairs` | GET, POST | `{items}` / `{ok, repair:{...}}` | |
| `/api/repairs/bulk-delete` | POST | `{ok, deleted:n}` | |
| `/api/repairs/<rid>` | GET, PUT, DELETE | `{ok, repair:{...}}` | |
| `/api/repairs/<rid>/status` | POST | `{ok, repair:{...}}` | `delivered` تاریخ تحویل را روی امروز می‌گذارد |
| `/api/tracking` | GET, POST | `{items}` / `{ok, tracking:{...}}` | |
| `/api/tracking/bulk-delete` | POST | `{ok, deleted:n}` | |
| `/api/tracking/<tid>` | GET, PUT, DELETE | `{ok, tracking:{...}}` | |
| `/api/calendar` | GET | `{ok, ...}` | `?jy=&jm=`؛ رویدادهای ماه شمسی |
| `/api/calendar/day` | GET | `{ok, ...}` | `?date=YYYY-MM-DD` |
| `/api/reports/monthly-activity` | GET | `{ok, ...}` | `?year=<jy>`؛ ۱۲ ماه برای نمودار داشبورد |
| `/export/<kind>.<fmt>` | GET | فایل | اکسل/CSV |
| `/api/import/products` | POST | `{ok, ...}` | multipart؛ upsert با `update_existing` |
| `/api/import/template` | GET | فایل | قالب اکسل ورودی |
| `/api/backups` | GET | `{ok, backups:[...]}` | |
| `/api/backups/create` | POST | `{ok, ...}` | |
| `/api/backups/upload` | POST | `{ok, ...}` | فایل بکاپ آپلودی |
| `/api/backups/download/<fname>` | GET | فایل | |
| `/api/backups/restore` | POST | `{ok, ...}` | بازگردانی پایگاه‌داده |
| `/api/backups/delete` | POST | `{ok, ...}` | |
| `/api/database/info` | GET | `{ok, ...}` | شمارش رکوردها + مسیر پایگاه‌داده |
| `/api/database/clear` | POST | `{ok, ...}` | پاک‌سازی آغاز دوره‌ی جدید |
| `/api/settings` | GET, POST | `{ok, settings:{...}}` | |
| `/api/settings/site-icon` | POST | `{ok, ...}` | آپلود آیکون سایت |

## چیزهایی که این قرارداد **ندارد**

- هیچ مسیری زیر `/api/v1/` (حذف‌شده در گام ۱؛ پاسخش مثل هر مسیر ناشناخته‌ی API است).
- هیچ متد PATCH در لایه‌ی لگاسی (PATCH فقط در لایه‌ی حذف‌شده وجود داشت؛ فرانت از PUT استفاده می‌کند).
- هیچ احراز هویت، CSRF یا کلید API (برنامه‌ی تک‌کاربره‌ی محلی؛ `csrf_exempt` روی آداپتورها دست‌نخورده می‌ماند).
- هیچ نسخه‌بندی در URL یا هدر.
