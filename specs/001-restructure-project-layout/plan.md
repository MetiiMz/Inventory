# Implementation Plan: بازآرایی چیدمان پروژه و تقسیم ماژول‌های حجیم بک‌اند

**Branch**: `001-restructure-project-layout` | **Date**: 2026-09-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-restructure-project-layout/spec.md`

## Summary

یک Refactor خالص در شش گامِ مستقل و برگشت‌پذیر: نخست یک **ماژول تست مرجع** برای مسیرهای لگاسی `/api/*`, `/export/*`, `/data/images/*` روی کد دست‌نخورده نوشته و سبز می‌شود (گام ۰)؛ سپس لایه‌ی موازی `/api/v1/` و وابستگی DRF حذف می‌شود (گام ۱)؛ ابزارهای production (`gunicorn`/`whitenoise`) حذف و یک مسیر استاتیک صریح **مستقل از DEBUG** جایش می‌نشیند (گام ۲)؛ دو ماژول حجیم به پکیج‌های دامنه‌ای تقسیم می‌شوند (`services.py` → `services/`، `compat.py` → `compat/`؛ گام ۳ و ۴)؛ و در پایان چیدمان به سه محدوده‌ی `db/` (داده) + `backend/` (کد) + `frontend/` (نمایش) جابه‌جا می‌شود (گام ۵). تضمین‌ها: صفر تغییر در URLها، شکل JSON، نام/امضای توابع و داده‌ی کاربر؛ کتابخانه‌های نصب‌شده از ۶ به ۳؛ یک دستور برای اجرا. تصمیم‌های فنی در [research.md](./research.md) و قراردادهای منجمد در [contracts/](./contracts/) ثبت شده‌اند.

## Technical Context

**Language/Version**: Python 3.10+ (محیط تأییدشده: 3.14.4 در `.venv/` ریشه‌ی مخزن)

**Primary Dependencies**: Django 5.2.6 · Jinja2 3.1.6 · openpyxl 3.1.5 — **پس از گام ۲ فقط همین سه**؛ حذف‌شده‌ها: `djangorestframework` 3.18.1، `gunicorn` 23.0.0، `whitenoise` 6.11.0 (FR-018/FR-020)

**Storage**: SQLite (`db/db.sqlite3` با `journal_mode=WAL` + `synchronous=NORMAL` + `transaction_mode=IMMEDIATE`) + فایل‌های روی دیسک (`db/images`، `db/backups`، `db/exports`). بدون سرور دیتابیس، بدون cache server.

**Testing**: تست‌رانر خودِ Django (`manage.py test`) — ۱۴۷ تست موجود در ۱۰ فایل + ماژول تست مرجع جدید (گام ۰). بی‌واسطگی: `tests/test_api_v1.py` (۱۶ تست) تنها فایلی است که حذف می‌شود. pytest استفاده نمی‌شود.

**Target Platform**: تک‌کاربره‌ی محلی (لپ‌تاپ) روی Linux/macOS/Windows؛ اجرا فقط با `runserver`؛ هرگز روی سرور/شبکه با کاربران remote (قانون اساسی پروژه).

**Project Type**: web application تک‌پروژه (Django project `tikotime` + یک اپ `inventory`؛ قالب‌های سرور-رندر Jinja2 + جاوااسکریپت خالص **بدون هیچ build step**). «frontend» در این پروژه یعنی `static/` + `templates/` و نه یک SPA.

**Performance Goals**: هیچ هدف کمی جدیدی تعریف نمی‌شود (رفتار فعلی باید حفظ شود). تنها انتظار کیفی: هیچ کندی محسوسی در لود صفحه‌ها و پاسخ APIها ایجاد نشود.

**Constraints**: صفر وابستگی/ابزار جدید (بدون Docker/auth/CSRF/logging) · صفر تغییر در URLها، شکل JSON، پیام‌های خطا و امضای توابع · صفر مهاجرت و صفر تغییر مدل · صفر تغییر محتوای قالب‌ها و css/js · صفر تغییر در فایل‌های تست موجود · صفر مسیر مطلق هارد‌کد · استاتیک باید مستقل از `DEBUG` لود شود · داده‌ی کاربر جابه‌جا می‌شود ولی محتوایش دست‌نخورده می‌ماند.

**Scale/Scope**: ۱ کاربر، ۴۵ فایل پایتون (~۶٬۶۶۰ خط شامل تست‌ها و مهاجرت‌ها)، ۹ مسیر صفحه (۸ صفحه‌ی مستقل + `/` که به داشبورد ریدایرکت می‌شود)، ۹ قالب، ۹ فایل js + ۱ css + ۴ فونت، ۳۸ endpoint لگاسی، ۶ مدل، ۶ مهاجرت، ۱۳۹ تصویر آپلودی، ۱۴۷ تست. هیچ رشد مقیاس/چندکاربری در آینده‌ی این پروژه پیش‌بینی نمی‌شود.

**NEEDS CLARIFICATION**: ۰ مورد. پنج تصمیم باز با جلسه‌ی شفاف‌سازی (بخش Clarifications سند spec) بسته شد و تصمیم‌های سطح طراحی در [research.md](./research.md) (R1–R12) با شاهد کد/آزمایش ثبت شده‌اند.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | قاعده‌ی قانون اساسی | نتیجه | شاهد / تضمین در این پلن |
|---|---|---|---|
| ۱ | **بدون تغییر رفتار** (هیچ منطق، URL یا شکل JSON عوض نشود) | ✅ PASS | گام ۰ ابتدا رفتار فعلی را در یک ماژول تست مرجع قفل می‌کند؛ انتقال توابع «عیناً» است (FR-024)؛ قرارداد HTTP منجمد در [contracts/legacy-api.md](./contracts/legacy-api.md) |
| ۲ | **بدون حذف غیرمجاز** (فقط فهرست تأییدشده) | ✅ PASS | فهرست بسته در «Approved Removals» سند spec؛ R11 صریحاً می‌گوید چه چیزهایی **می‌مانند** (`wsgi.py`، `STATIC_ROOT`، مدل‌ها/مهاجرت‌ها، پوشه‌های کمکی خالی) |
| ۳ | **تست‌ها منبع حقیقت** (۱۰۰٪ سبز بعد از هر گام) | ✅ PASS | گام‌های ۰..۵ هر کدام با کل مجموعه‌ی تست بسته می‌شوند (R12)؛ تنها فایل حذف‌شده `tests/test_api_v1.py` است؛ هیچ تست دیگری ویرایش نمی‌شود (FR-010) |
| ۴ | **تقسیم بر اساس دامنه** (بدون تغییر امضا؛ `__init__` باز‌export‌کننده) | ✅ PASS | R1/R2 (۱۱+۱۱ ماژول دامنه‌ای) + قاعده‌ی باز‌export در [contracts/python-imports.md](./contracts/python-imports.md) |
| ۵ | **بدون وابستگی/پیچیدگی جدید** | ✅ PASS | کتابخانه‌ها ۶→۳؛ عملیات حذفی؛ مسیر استاتیک با API خودِ Django (بدون بسته‌ی جدید)؛ بدون Docker/auth/CSRF/logging |
| ۶ | **جابه‌جایی فقط با تنظیمات** (نه تغییر منطق) | ⚠️ PASS با دو انحراف ثبت‌شده | تنها تغییرهای منطقیِ مسیر: `utils.py` (منبع مسیرها) و `jinja.py` (مسیر مبدأ مهر نسخه) — هر دو تغییر **منبع مسیر**اند نه منطق کسب‌وکار؛ بدون آن‌ها جابه‌جایی بی‌صدا خراب می‌شود → Complexity Tracking |
| ۷ | **گام‌های کوچک و قابل بازگشت** | ✅ PASS | ۶ گام = ۶ commit مستقل و قابل `git revert`؛ هر گام با دروازه‌های R12 بسته می‌شود |

**نتیجه‌ی گیت پیش از Phase 0**: PASS (بدون نقضِ غیرقابل‌توجیه؛ دو انحراف مسیر در Complexity Tracking با دلیل و جانشینِ رد‌شده ثبت شده‌اند).

**نتیجه‌ی گیت پس از Phase 1 (Re-check)**: PASS — طراحی نهایی (R1–R12 + سه قرارداد منجمد) هیچ قاعده‌ای را نقض نمی‌کند: بدون وابستگی جدید (مسیر استاتیک با API خودِ Django)، بدون تغییر رفتار (انتقال عیناً + قفل مرجع در گام ۰)، بدون حذف غیرمجاز (R11)، و همه‌ی گام‌ها مستقل و برگشت‌پذیر.

## Project Structure

### Documentation (this feature)

```text
specs/001-restructure-project-layout/
├── plan.md              # این فایل
├── spec.md              # مشخصات + بخش Clarifications (۵ تصمیم)
├── research.md           # Phase 0: تصمیم‌های R1–R12 با شاهد کد/آزمایش
├── data-model.md        # Phase 1: مدل چیدمان، پکیج‌ها، مرجع رفتاری، گام‌ها
├── quickstart.md        # Phase 1: راهنمای اعتبارسنجی (V1–V11 + دروازه‌ی هر گام)
├── contracts/
│   ├── legacy-api.md        # قرارداد HTTP لگاسی (منجمد)
│   ├── python-imports.md    # قرارداد importها و باز‌export (منجمد)
│   └── ops-commands.md      # قرارداد اجرا/تست/مسیرها (منجمد)
├── checklists/
│   └── requirements.md  # چک‌لیست کیفیت spec (۱۶/۱۶)
└── tasks.md             # Phase 2 — با `/speckit-tasks` ساخته می‌شود (اینجا نیست)
```

### Source Code (repository root)

**وضعیت فعلی (Before)**

```text
project-root/
├── manage.py · requirements.txt(۶ خط) · README.md · .gitignore
├── tests/                 # ۱۰ فایل، ۱۴۷ تست
├── data/                  # db.sqlite3 · watch_inventory.db · images/(۱۳۹) · backups/ · exports/
├── static/                # css/app.css · js/(۹ فایل) · fonts/(۴ فونت)
├── templates/             # ۹ قالب Jinja2
├── staticfiles/           # خروجی جمع‌آوری‌شده‌ی whitenoise (باید حذف شود)
├── tikotime/              # settings.py · urls.py · jinja.py · wsgi.py
└── inventory/
    ├── models.py · utils.py · dbhelpers.py · excel_io.py · jalali.py · reports.py
    ├── migrations/(۶) · views/pages.py
    └── api/
        ├── services.py    # ۱۱۹۸ خط ← تقسیم می‌شود
        ├── compat.py      # ۶۰۰ خط  ← تقسیم می‌شود
        ├── views.py(۴۹۶) · serializers.py(۴۳۶) · fields.py(۱۹) · exceptions.py(۲۵) · urls.py(۴۹)  ← حذف
        └── services/      # پوشه‌ی خالیِ باقی‌مانده از تلاش قبلی (پاک می‌شود)
```

**وضعیت هدف (After)**

```text
project-root/
├── db/                    # db.sqlite3 · images/ · backups/ · exports/   (نادیده در git)
├── backend/
│   ├── manage.py · requirements.txt(۳ خط)
│   ├── tests/             # ۱۰ فایل موجود + test_legacy_api_baseline.py (جدید) − test_api_v1.py
│   ├── tikotime/          # settings.py · urls.py(+مسیر استاتیک) · jinja.py · wsgi.py
│   └── inventory/
│       ├── models.py · utils.py · dbhelpers.py · excel_io.py · jalali.py · reports.py
│       ├── migrations/(۶، بدون تغییر) · views/pages.py
│       └── api/
│           ├── __init__.py
│           ├── services/      # common products sales payments repairs tracking
│           │                  # settings uploads calendar reports export_import
│           └── compat/        # common products sales payments repairs tracking
│                              # calendar reports settings uploads backups_export
├── frontend/
│   ├── static/            # css/app.css · js/(۹) · fonts/(۴)
│   └── templates/         # ۹ قالب
├── README.md · .gitignore
└── .specify/ · .clinerules/ · .memory/ · .claude/ · .venv/
```

**Structure Decision**: چیدمان سه‌محدوده‌ای انتخاب شد (`db/` داده · `backend/` کد · `frontend/` نمایش) چون برنامه در عمل سه نگرانی کاملاً جدا دارد و تنها ابهام امروز این است که هر سه در ریشه قاطی شده‌اند. `backend/` خودش یک ریشه‌ی import معتبر است (`sys.path[0]` = محل `manage.py`)، پس `tikotime`/`inventory`/`tests` بدون هیچ تغییری در importها زیر آن کار می‌کنند. دو پکیج دامنه‌ای (`services/`, `compat/`) واژگان یکسانی دارند تا «کجاست؟» در هر دو لایه یک‌گامی باشد (SC-009). مسیرهای روی دیسک فقط از `tikotime/settings.py` می‌آیند (R4) و هیچ ماژولی مسیر خودش را از محل فایلش نمی‌سازد.

## Complexity Tracking

> فقط انحراف‌های ثبت‌شده؛ هر ردیف جانشینِ ساده‌تری دارد که به دلیل مشخص رد شده است.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| افزودن دو ماژول `calendar.py` و `reports.py` به پکیج آداپتورها (فهرست FR-022 فقط ۹ دامنه‌ی آداپتور را نام برده) | `compat.py` سه خانواده‌ی endpoint دارد که در فهرست نیامده‌اند (`api_calendar`, `api_calendar_day`, `api_monthly_activity`) و باید جایی بنشینند؛ تقارن با دامنه‌های لایه‌ی قواعد آن‌ها را دو ماژول مستقل می‌کند | ریختن‌شان در `common.py` اصل «یک دامنه = یک ماژول» (FR-021) و SC-009 را نقض می‌کند؛ حذف‌شان غیرمجاز است (حذف غیرتأییدشده) |
| تغییر یک خط کد در `tikotime/jinja.py` (`static_v`) بیرون از بلاک تنظیمات (انحراف از «جابه‌جایی فقط با تنظیمات») | `static_v` مسیر دارایی را هارد‌کد از `BASE_DIR/static` می‌سازد؛ بدون اصلاح، بعد از جابه‌جایی بی‌صدا به «بدون نسخه» سقوط می‌کند و باگ دیده‌نشدن تغییرات CSS/JS برمی‌گردد (FR-013، SC-008) | رها کردن کد به‌حال خودش → رگرسیون بی‌صدا و کش یک‌ساله‌ی کهنه (همان باگی که در `.memory/JOURNAL.md` ثبت شده)؛ افزودن یک ماژول مسیرِ کمکی جدید → سطح عمومی جدید و پیچیدگی بی‌دلیل |
| تغییر منبع دو ثابت در `inventory/utils.py` (`IMG_DIR`/`BACKUP_DIR`) از `__file__` به `settings` | مسیر مشتق‌شده از `__file__` با جابه‌جایی به `backend/` به `backend/data/...` اشاره می‌کند و **۱۳۹ تصویر موجود را یتیم می‌کند** (FR-004، FR-011) | ساختن symlink از `backend/data` به `db/` → کوپلینگ پنهان و شکننده روی ویندوز/مک؛ نگه‌داشتن کد فعلی → داده‌ی کاربر بی‌صدا گم می‌شود |

**Re-check پس از Phase 1**: PASS — طراحی نهایی (R1–R12 + سه قرارداد) هیچ قاعده‌ای را نقض نمی‌کند: هیچ وابستگی جدیدی اضافه نشد (مسیر استاتیک با API خودِ Django)، هیچ رفتاری عوض نشد (انتقال عیناً + قفلِ مرجع در گام ۰)، هیچ حذف غیرمجازی وجود ندارد (R11) و همه‌ی گام‌ها مستقل و برگشت‌پذیرند.

## خلاصه‌ی گام‌ها (ورودی `/speckit-tasks`)

| گام | کار | خروجی همان commit | دروازه |
|---|---|---|---|
| ۰ | ماژول تست مرجع مسیرهای لگاسی (`tests/test_legacy_api_baseline.py`) | تست جدید سبز روی کد دست‌نخورده | `manage.py test` + `git log` = نخستین commit (SC-011) |
| ۱ | حذف `/api/v1/` + DRF + `api_brands_add`/`_page_ctx` + تست‌های v1 + مستندات مربوط | ۵ فایل حذف، `settings.py`/`urls.py`/`requirements.txt`/README تمیز | صفر ارجاع باقی‌مانده؛ ۴۰۴ پیش‌فرض جنگو روی `/api/v1/*` |
| ۲ | حذف `gunicorn`/`whitenoise` + بلاک `STORAGES`/`WHITENOISE_MAX_AGE` + پوشه‌ی `staticfiles/` + افزودن مسیر استاتیک `insecure=True` | ۳ خط مانیفست، `MIDDLEWARE` تمیز، مسیر استاتیک | `200` برای دارایی در `DEBUG=0` |
| ۳ | پاک‌سازی باقی‌مانده + تقسیم `services.py` به ۱۱ ماژول + `__init__` باز‌export | پکیج `services/` | صفر تغییر در صدا‌زننده‌ها؛ ≤۴۰۰ خط |
| ۴ | تقسیم `compat.py` به ۱۱ ماژول + `__init__` باز‌export | پکیج `compat/` | صفر تغییر در `urls.py`/تست‌ها؛ ≤۴۰۰ خط |
| ۵ | پاک‌سازی `__pycache__` + جابه‌جایی به `db/`,`backend/`,`frontend/` + اصلاح مسیرها + `.gitignore` + README | ریشه‌ی سه‌محدوده‌ای | ۸/۸ صفحه، عملیات فایل‌محور، `git status` پاک |

جزئیات اجرایی هر گام، دستورهای دقیق و انتظارها در [quickstart.md](./quickstart.md) آمده است.

## Post-Phase 1 outputs

- [research.md](./research.md) — تصمیم‌های R1–R12، هر یک با **Decision / Rationale / Alternatives considered** و شاهد کد یا آزمایش واقعی.
- [data-model.md](./data-model.md) — محدوده‌های روی دیسک و منبع حقیقت مسیرها، پکیج‌های دامنه‌ای، مرجع رفتاری، اجزای حذف‌شده، انتقال حالت‌ها و «تغییرات صفر».
- [contracts/](./contracts/) — سه قرارداد منجمد: HTTP لگاسی، سطح import پایتون، و اجرا/تست/مسیرها.
- [quickstart.md](./quickstart.md) — دروازه‌ی هر گام + ۱۱ سناریوی اعتبارسنجی (V1–V11) نگاشت‌شده به SC-001…SC-011 و راهنمای بازگشت به عقب.

**گام بعدی**: `/speckit-tasks` — تولید فهرست وظایف دقیق و مرتب (شروع با گام ۰ = ماژول تست مرجع، پیش از هر تغییر ساختاری).


