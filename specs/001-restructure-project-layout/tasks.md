# Tasks: بازآرایی چیدمان پروژه و تقسیم ماژول‌های حجیم بک‌اند

**Input**: Design documents from `/specs/001-restructure-project-layout/`

**Prerequisites**: [plan.md](./plan.md) · [spec.md](./spec.md) · [research.md](./research.md) · [data-model.md](./data-model.md) · [contracts/](./contracts/) · [quickstart.md](./quickstart.md)

**Tests**: این فیچر «تست‌محور اجباری» است — اما نه به‌معنای تست جدید برای هر داستان. قاعده‌ی پروژه این است که **مجموعه‌ی تست موجود (۱۴۷ تست) منبع حقیقت** است و ویرایش نمی‌شود (FR-010)؛ تنها افزوده‌ی تستی، **ماژول تست مرجع** در فاز ۲ است که تصمیم Q3 + پیگیری کاربر آن را الزامی کرده. پس هر فاز با «اجرای کل مجموعه (موجود + مرجع) و سبز بودن» بسته می‌شود، ولی تست جدید دیگری ساخته نمی‌شود.

**Organization**: فازها یک‌به‌یک به داستان‌های کاربری spec نگاشت شده‌اند، ولی **ترتیب اجرا** از ترتیب فازها پیروی می‌کند نه از اولویت ارزشی — دلیلش در «Phase Ordering Note» آمده است.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: می‌تواند موازی اجرا شود (فایل‌های متفاوت، بدون وابستگی به کار ناتمام)
- **[Story]**: کدام داستان کاربری (US1..US4 مطابق spec.md)
- هر شرح، **مسیر فایل دقیق** و در صورت لزوم **دستور و انتظار** را دارد.

## Path Conventions

- **گام‌های ۰ تا ۴** (فاز ۲ تا ۵): مسیرها همان مسیرهای فعلی از ریشه‌ی مخزن‌اند (`inventory/...`، `tests/...`، `tikotime/...`).
- **گام ۵** (فاز ۶): پیشوند `backend/` اضافه می‌شود و دارایی‌های نمایشی به `frontend/` می‌روند؛ در شرح همان تسک‌ها مسیر «پس از جابه‌جایی» نوشته شده است.
- اجرای تست پیش از گام ۵: `.venv/bin/python manage.py test` — از گام ۵ به بعد: `cd backend && ../.venv/bin/python manage.py test` (⚠️ هرگز `backend/manage.py test` بدون برچسب از ریشه؛ R7).

## Phase Ordering Note

| داستان | اولویت (ارزش) | گام اجرا | چرا این‌جا؟ |
|---|---|---|---|
| US3 — یک قرارداد API | P3 | فاز ۳ (گام ۱) | حذف لایه‌ی بی‌مصرف، تعداد فایل‌های در گردش را کم می‌کند و ریسکش از همه کمتر است |
| US4 — یک دستور اجرا | P4 | فاز ۴ (گام ۲) | پیش از تقسیم، جدول وابستگی‌ها تمیز می‌شود تا تست‌ها روی مجموعه‌ی سبک اجرا شوند |
| US2 — یک فایل، یک دامنه | P2 | فاز ۵ (گام ۳ و ۴) | تقسیم باید **پیش از** جابه‌جایی انجام شود تا درخت در کمترین حجم ممکن منتقل شود |
| US1 — چیدمان سه‌بخشی | P1 | فاز ۶ (گام ۵) | پرریسک‌ترین (همه‌ی مسیرها) و باید آخر بیاید؛ MVPِ این Refactor یک «کد سبک‌شده + قرارداد تثبیت‌شده» است، نه جابه‌جایی |

این ترتیب دقیقاً همان ترتیب پیشنهادی spec و دستور صریح کاربر است («Step 0 … then (1) … (5)»). اولویت‌های P1..P4 بیانگر **ارزش** هستند و در جدول بالا manifest می‌شوند.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: تثبیت وضعیت پایه و ایجاد تور نجات، پیش از هر تغییری

- [x] T001 تثبیت وضعیت پایه و ثبت اعداد مرجع: از ریشه‌ی مخزن `git --no-pager status --short` (انتظار: درخت تمیز) · `.venv/bin/python manage.py check` (انتظار: `no issues`) · `.venv/bin/python manage.py test 2>&1 | tail -4` (انتظار: `Found 147 test(s)` + `OK`) · `ls data/images | wc -l` (انتظار: عدد دقیقِ همان لحظه، نه عدد ثابت) · `ls data/backups | wc -l` و `ls data/exports | wc -l` · `sha256sum data/db.sqlite3`. خروجی همه در `.memory/COMMANDS.md` ثبت می‌شود (عادت پروژه). **اندازه‌گیری واقعی ۲۰۲۶-۱۰-۰۱**: درخت تمیز ✓ · `check` بدون ایراد ✓ · `Found 147 test(s)` + `OK` ✓ · تصاویر = **۱۳۹** (اسناد قدیمی عدد دیگری داشتند و کهنه است) · پشتیبان = ۴۲ · خروجی = ۵۴ · `sha256` پایگاه‌داده ثبت شد. **علت اختلاف عدد تصاویر**: تست‌های موجود `tests/test_services_misc.py:90,100` بدون `override_settings(IMG_DIR=...)` هر اجرا ۲ فایل ۵۸بایتی در `data/images/` واقعی می‌سازند (نقض قاعده‌ی «تست‌ها به داده‌ی واقعی دست نمی‌زنند»؛ ویرایش آن تست‌ها طبق FR-010 مجاز نیست و به‌عنوان یک مسئله‌ی مستقل در `.memory/INDEX.md` ثبت شد). پس دروازه‌ی گام ۵ **مقایسه‌ی مجموعه‌ی تصاویر قبل/بعد** است، نه عدد ثابت.
- [x] T002 تور نجات خارج از مخزن: `mkdir -p /tmp/tiko-preflight && cp -a data /tmp/tiko-preflight/data && tar czf /tmp/tiko-preflight/code.tgz manage.py requirements.txt tikotime inventory tests static templates README.md .gitignore` و سپس بازبینی درستی آرشیو (`tar tzf /tmp/tiko-preflight/code.tgz | wc -l`). **انجام‌شده ۲۰۲۶-۱۰-۰۱**: ۱۷۶ ورودی آرشیو؛ `/tmp/tiko-preflight/data` با **۱۳۹** تصویر (هم‌تعداد با مخزن) و `sha256` پایگاه‌داده یکسان با مخزن (`f753fc1c…`) تأیید شد.
- [x] T003 **انجام‌شده** — commit مستندات پلن: در commit پایه‌ی `19e4975` («spec-kit: constitution + spec + plan + tasks …») ثبت شده است و `.specify/` و `.clinerules/` هم در همان commit وارد نسخه شدند (انتظار قدیمیِ «commit نمی‌شوند» منقضی است). هر ویرایش مستنداتیِ بعدی با یک commit مستندات جدا ثبت شود تا `git log` (SC-011) خوانا بماند.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: **گام ۰** — قفل کردن رفتار فعلی مسیرهای لگاسی، پیش از هر تغییر ساختاری

**⚠️ CRITICAL**: هیچ‌کدام از داستان‌های کاربری (فاز ۳ به بعد) نمی‌تواند شروع شود تا این فاز تمام شود. ترتیب درونی فاز (نوشتن → سبز شدن → commit) همان چیزی است که SC-011 می‌سنجد.

**Independent Test (فاز)**: کل مجموعه‌ی تست روی کد **دست‌نخورده** سبز است و `git show --stat` نخستین commit ساختاری فقط همان یک فایل تست جدید را نشان می‌دهد.

- [x] T004 ساخت اسکلت ماژول مرجع در `tests/test_legacy_api_baseline.py`: داک‌استرینگ که هدف را بگوید (قفل‌کردن قرارداد لگاسی پیش از Refactor)، importها (`json`, `django.test.TestCase`, `inventory.models`, کارخانه‌های `tests.helpers`) و یک `setUp` که **داده‌ی ثابت** می‌سازد: یک محصول (`make_product`)، یک فروش نقدی (فروش دوم با `payment_type=deposit`)، یک تعمیر، یک پیگیری، یک برند و چند `Setting`.
- [x] T005 افزودن تست‌های گروه محصولات/فروش/پرداخت به `tests/test_legacy_api_baseline.py`: برای `/api/products`, `/api/products/bulk-delete`, `/api/products/<id>`, `/api/sales`, `/api/sales/bulk-delete`, `/api/sales/<id>`, `/api/payments`, `/api/payments/<id>`, `/api/payments/<id>/add`, `/api/payments/<id>/settle-full`, `/api/payments/bulk-delete` کد وضعیت + **نام و مقدار کلیدهای نام‌دار** را assert کنید (نه ترتیب کلیدهای داخل آبجکت)؛ شامل شکل خطا برای payload نامعتبر (`400` + `{"ok": false, "error": <پیام فارسی>}`).
- [x] T006 افزودن تست‌های گروه تعمیرات/پیگیری/برندها به `tests/test_legacy_api_baseline.py`: `/api/repairs`, `/api/repairs/<id>`, `/api/repairs/<id>/status` (تغییر وضعیت به `delivered` و اثرش روی تاریخ تحویل)، `/api/repairs/bulk-delete`, `/api/tracking`, `/api/tracking/<id>`, `/api/tracking/bulk-delete`, `/api/brands` (GET و POST) و `/api/brands/delete`.
- [x] T007 افزودن تست‌های گروه آپلود/تصویر/تقویم/گزارش به `tests/test_legacy_api_baseline.py`: `POST /api/upload` با بدنه‌ی JSON base64 (انتظار `{ok, path}`)، `GET /data/images/<path>` (انتظار ۲۰۰)، `GET /api/calendar?jy=&jm=`، `GET /api/calendar/day?date=YYYY-MM-DD`، `GET /api/reports/monthly-activity?year=<jy>`. **الزام**: این تست‌ها باید در `override_settings(IMG_DIR=<tmpdir>)` اجرا شوند تا هیچ فایلی در `data/images/` واقعی ساخته نشود (قاعده‌ی پروژه: تست‌ها هرگز به داده‌ی واقعی دست نمی‌زنند).
- [x] T008 افزودن تست‌های گروه خروجی/ورودی/بکاپ/پایگاه‌داده/تنظیمات و رفتار مسیر ناشناخته به `tests/test_legacy_api_baseline.py`: `GET /export/<kind>.<fmt>` (اکسل و CSV)، `GET /api/import/template`، `GET /api/backups`، `GET /api/database/info`، `GET /api/settings`، `POST /api/settings` و `GET /api/unknown-path` و `GET /no-such-page` (انتظار: کد وضعیت `۴۰۴` پیش‌فرض جنگو در هر دو حالت — بدون بدنه‌ی JSON و بدون ریدایرکت؛ چون هیچ `handler404` سفارشی در `ROOT_URLCONF` سیم‌کشی نشده است). برای مسیرهای فایل‌ساز از `override_settings(BACKUP_DIR=<tmpdir>, DATA_DIR=<tmpdir>)` استفاده کنید، نه از پوشه‌های واقعی.
- [x] T009 اجرای کل مجموعه روی کد دست‌نخورده: `.venv/bin/python manage.py test 2>&1 | tail -6` (انتظار: `Found <147+N> test(s)` + `OK` و **نه** `NO TESTS RAN`). اگر تستی شکست خورد همان‌جا اصلاح شود تا سبزِ کامل به‌دست بیاید؛ سپس `git --no-pager status --short` باید فقط یک فایل جدید نشان دهد: `tests/test_legacy_api_baseline.py`. **ثبت `N`**: تعداد تست‌های ماژول مرجع را از همین خروجی بشمارید و در `.memory/COMMANDS.md` ثبت کنید؛ در همه‌ی گیت‌های بعدی `N` همین عدد است (قاعده‌ی شمارش در بخش Notes). **انجام‌شده ۲۰۲۶-۱۰-۰۳**: `Found 169 test(s)` + `OK` (پایه‌ی ۱۴۷ + **N=22** از ماژول مرجع)؛ `git status --short` فقط `tests/test_legacy_api_baseline.py` را نشان داد.
- [x] T010 commit مرجع (نخستین commit ساختاری این تغییر): `git add tests/test_legacy_api_baseline.py && git commit -m 'test(api): freeze the legacy /api/* contract before the restructure'`؛ سپس `git show --stat HEAD` (انتظار: فقط همان یک فایل) و `git --no-pager log --oneline -3` برای ثبت شاهد SC-011. **انجام‌شده ۲۰۲۶-۱۰-۰۳**: commit `443bff6` (یک فایل، ۵۶۳ خط) ثبت شد؛ `git show --stat HEAD` = فقط `tests/test_legacy_api_baseline.py`؛ `git log --oneline --diff-filter=A -- tests/test_legacy_api_baseline.py` هم تأیید می‌کند این نخستین commit افزودن ماژول مرجع است.

**Checkpoint**: قرارداد رفتاری قفل شده است؛ از این نقطه هر تغییری که رفتار عوض کند، خودش را لو می‌دهد.

---

## Phase 3: User Story 3 - فقط یک قرارداد API (Priority: P3)

**Goal**: لایه‌ی موازی `/api/v1/` و وابستگی DRF و دو تابع بی‌استفاده حذف شوند، در حالی‌که قرارداد `/api/*` و همه‌ی صفحه‌ها دست‌نخورده کار می‌کنند.

**Independent Test**: همه‌ی `/api/*`ها همان پاسخ مرجع را می‌دهند (ماژول فاز ۲ سبز)، هر ۸ صفحه بالا می‌آیند، `/api/v1/products` مثل هر مسیر ناشناخته‌ی API رفتار می‌کند و هیچ ارجاعی به لایه/وابستگی حذف‌شده در کد و مستندات نمی‌ماند.

- [x] T011 [US3] حذف فایل‌های لایه‌ی موازی: `git rm inventory/api/views.py inventory/api/serializers.py inventory/api/fields.py inventory/api/exceptions.py inventory/api/urls.py`؛ انتظار: در `inventory/api/` فقط `__init__.py`, `services.py`, `compat.py` بماند. · و پاک‌سازی اشاره‌های کهنه به لایه‌ی حذف‌شده از داک‌استرینگ ماژول‌های بازمانده (فقط متن، بدون تغییر کد و رفتار): `inventory/api/services.py`، `inventory/api/compat.py` و خط مربوط به `inventory.api.views` در `inventory/views/__init__.py` (لازمه‌ی FR-016).
- [x] T012 [P] [US3] حذف مسیر نسخه‌بندی‌شده از `tikotime/urls.py`: برداشتن `path("api/v1/", include("inventory.api.urls"))` و `include` بی‌استفاده از importها، و به‌روزرسانی داک‌استرینگ ماژول (از «سه نوع مسیر» به «دو نوع: صفحات + API لگاسی»).
- [x] T013 [P] [US3] پاک‌سازی `tikotime/settings.py`: حذف `"rest_framework"` از `INSTALLED_APPS` و حذف کامل بلاک `REST_FRAMEWORK = {...}` همراه با کامنت‌های توضیحی‌اش.
- [x] T014 [P] [US3] حذف ردیف `djangorestframework==3.18.1` از `requirements.txt` (سه ردیف دیگر دست‌نخورده می‌مانند).
- [x] T015 [US3] حذف دو تابع بی‌استفاده از `inventory/api/compat.py`: حذف `api_brands_add` و `_page_ctx` (به‌همراه importهای بی‌استفاده‌ای که فقط به‌خاطر آن‌ها بودند). **مهم**: `api_brands`، `api_brands_delete` و `services.brands_add` MUST دست‌نخورده بمانند.
- [x] T016 [US3] حذف `tests/test_api_v1.py` (تنها فایلی که منحصراً لایه‌ی حذف‌شده را پوشش می‌دهد؛ ۱۶ تست).
- [x] T017 [P] [US3] به‌روزرسانی `inventory/api/__init__.py`: داک‌استرینگ چیدمان، حذف اشاره به `serializers.py`/`views.py`/`urls.py`/`fields.py`/`exceptions.py` و توضیح اینکه این پکیج اکنون فقط `services` + `compat` دارد.
- [x] T018 [P] [US3] به‌روزرسانی `README.md` (پاراگراف معرفی + بلوک معماری بک‌اند + خط پیش‌نیازها) و `.memory/INDEX.md` (ردیف `tikotime/urls.py` که «API includes pending» را می‌گوید + هر اشاره‌ی دیگر به لایه‌ی `/api/v1/`؛ توجه: INDEX.md ردیف مستقل DRF ندارد) طبق R10.
- [x] T019 [US3] دروازه‌ی تأیید این فاز: `grep -rn 'rest_framework\|api/v1\|djangorestframework' --include=*.py --include=*.md --include=*.txt inventory tikotime tests README.md requirements.txt` → **۰ نتیجه**؛ سپس سرور بالا و `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/api/v1/products` → `404` و بدنه‌ی `{"ok": false, "error": "یافت نشد"}`؛ سپس `.venv/bin/python manage.py test 2>&1 | tail -4` → `Found <131+N> test(s)` + `OK`؛ و بازدید دستی ۸ صفحه در مرورگر (۰ درخواست ۴۰۴ دارایی). · نکته: شرط «۰ نتیجه» فقط پس از پاک‌سازی متن T011 (سه فایل `inventory/api/services.py`، `inventory/api/compat.py` و `inventory/views/__init__.py`) قابل عبور است. **انجام‌شده ۲۰۲۶-۱۰-۰۳**: grep روی `inventory tikotime tests README.md requirements.txt` → تنها رخ‌داد در داک‌استرینگ ماژول مرجعِ **منجمد** `tests/test_legacy_api_baseline.py:7` (ویرایش‌ناپذیر طبق FR-010)؛ **صفر** ارجاع در کد. زنده: `/api/v1/products` = **۴۰۴ پیش‌فرض جنگو (HTML)** — نه بسته‌ی JSON؛ `handler404` در `pages.py` تعریف شده ولی در `ROOT_URLCONF` سیم‌کشی **نمی‌شود** (رفتار منجمد؛ متن «بدنه‌ی JSON» این تسک با quickstart و ماژول مرجع ناسازگار است و پیگیری نشد). `Found 153 test(s)` + `OK` (= ۱۳۱ + ۲۲)؛ ۸/۸ صفحه ۲۰۰؛ `/api/products` = ۲۰۰ JSON.
- [x] T020 [US3] commit این گام: `git add -A && git commit -m 'refactor(api): drop the unused versioned /api/v1 layer and DRF'` و ثبت شاهد `git show --stat HEAD`. **انجام‌شده ۲۰۲۶-۱۰-۰۳**: commit `2aeb840` (۱۶ فایل، ۲۵+/۱۳۲۹−)؛ در `inventory/api/` فقط `__init__.py` + `services.py` + `compat.py` ماند.

**Checkpoint**: فقط یک قرارداد API باقی مانده و همه‌چیز سبز است؛ این نقطه یک increment قابل تحویل است.

---

## Phase 4: User Story 4 - یک دستور برای اجرا، بدون ابزار بی‌استفاده (Priority: P4)

**Goal**: ابزارهای مخصوص production و تنظیمات‌شان حذف شوند و سرو دارایی‌های استاتیک با یک مسیر صریح، **مستقل از کلید DEBUG**، تضمین شود.

**Independent Test**: با `DJANGO_DEBUG=0` هم صفحه‌ها بالا می‌آیند و css/js/فونت با ۲۰۰ لود می‌شوند؛ مانیفست وابستگی فقط سه ردیف دارد؛ هیچ گامی به `collectstatic` نیاز ندارد.

- [ ] T021 [P] [US4] حذف ردیف‌های `gunicorn==23.0.0` و `whitenoise==6.11.0` از `requirements.txt` (نتیجه: فقط `Django`, `Jinja2`, `openpyxl`).
- [ ] T022 [US4] پاک‌سازی `tikotime/settings.py`: حذف `"whitenoise.middleware.WhiteNoiseMiddleware"` از `MIDDLEWARE`، حذف کامل بلاک `STORAGES`، حذف `WHITENOISE_MAX_AGE` و کامنت‌های مربوط. **بماند**: `STATIC_URL`، `STATICFILES_DIRS`، `STATIC_ROOT` و `"django.contrib.staticfiles"` در `INSTALLED_APPS` (R11).
- [ ] T023 [US4] افزودن مسیر استاتیک مستقل از DEBUG به `tikotime/urls.py`: `from django.contrib.staticfiles.views import serve as serve_static` و `path("static/<path:path>", serve_static, {"insecure": True})` همراه کامنتی که دلیل `insecure=True` را بگوید (در `DEBUG=0` هم `finders` سرو کند — R3). مطمئن شوید با مسیرهای موجود تضاد ندارد.
- [ ] T024 [P] [US4] حذف خروجی جمع‌آوری‌شده: `rm -rf staticfiles/` و برداشتن خط `staticfiles/` + کامنت «Django collected static (whitenoise)» از `.gitignore`.
- [ ] T025 [P] [US4] به‌روزرسانی `README.md`: حذف بخش «اجرا در حالت تولید (سرور)»، اصلاح خط پیش‌نیازها (سه کتابخانه) و جدول متغیرهای محیطی — جمله‌ی «روی سرور روی ۰ بگذارید» حذف و به‌جایش نوشته شود که `DJANGO_DEBUG=0` حالت پشتیبانی‌شده است و دارایی‌ها در هر حالتی لود می‌شوند.
- [ ] T026 [P] [US4] به‌روزرسانی `.memory/INDEX.md`: ردیف requirements + ردیف `settings.py` (بدون whitenoise) و ردیف «Entry point» که به gunicorn اشاره می‌کند؛ توجه: INDEX.md هیچ اشاره‌ی `collectstatic` ندارد (موردی برای حذف در آن خصوص وجود ندارد).
- [ ] T027 [US4] دروازه‌ی استقلال از DEBUG: `DJANGO_DEBUG=0 .venv/bin/python manage.py runserver 127.0.0.1:8010` در پس‌زمینه؛ سپس `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8010/static/css/app.css` → **۲۰۰** و همان برای یک فایل js و یک فونت و یک تصویر از `/data/images/...`؛ سپس سرور را ببندید، با `DJANGO_DEBUG=1` تکرار کنید و ۸ صفحه را در مرورگر باز کنید (۰ درخواست ۴۰۴)؛ و `.venv/bin/python manage.py test 2>&1 | tail -4` → همچنان `Found <131+N> test(s)` + `OK`.
- [ ] T028 [US4] commit این گام: `git add -A && git commit -m 'chore: drop gunicorn/whitenoise and serve static independently of DEBUG'` و ثبت `git show --stat HEAD`.

**Checkpoint**: نصب سبک شد و اجرای محلی از حالت اشکال‌زدایی مستقل شد؛ آماده‌ی تقسیم ماژول‌ها.

---

## Phase 5: User Story 2 - یک فایل، یک دامنه (Priority: P2)

**Goal**: دو ماژول حجیم (`services.py` ۱۱۹۸ خط، `compat.py` ۶۰۰ خط) به پکیج‌های دامنه‌ای تقسیم شوند، بدون تغییر امضا/شکل خروجی، و با ریشه‌ی پکیجی که همه‌ی نام‌های قبلی را دوباره export می‌کند.

**Independent Test**: `from inventory.api import services` و `from inventory.api.services import ApiError` کار می‌کنند؛ `git diff --stat` هیچ تغییری در صدا‌زننده‌ها (compat، `tikotime/urls.py`، `tests/`) نشان نمی‌دهد؛ هیچ ماژولی > ۴۰۰ خط نیست؛ کل مجموعه‌ی تست سبز است.

> **قاعده‌ی طلایی هر دو گام**: انتقال کد **عیناً** (کپی کاراکتربه‌کاراکتر تابع + importهای موردنیازش)؛ هیچ بازنویسی، هیچ «بهبود» و هیچ تغییر پیام/امضا (FR-024). نگاشت دقیق تابع→ماژول و محدوده‌ی خطوط فعلی در [research.md §R1 و §R2](./research.md) آمده است.

### گام ۳ — تقسیم `services.py`

- [ ] T029 [US2] آماده‌سازی گام ۳: حذف باقی‌مانده‌ی تلاش قبلی تقسیم (`rm -rf inventory/api/services/` — پوشه‌ی خالی با `__pycache__` کهنه، FR-025) و سپس تأیید اینکه ماژول فعلی سالم است: `.venv/bin/python -c "from inventory.api import services; print(services.__file__)"` باید `inventory/api/services.py` را چاپ کند.
- [ ] T030 [US2] ساخت `inventory/api/services/common.py`: انتقال عیناً `ApiError` (خطوط ۴۵–۵۷) و کمکی‌های `_clean_ids`, `_merge_partial`, `_parse_iso_or_raise` (خطوط ۵۹–۸۶) + importهای لازم (`to_int`، `parse_jalali_date`). همچنین سرِ ماژول فعلی (`services.py` خطوط ۱–۴۴) MUST جا بیفتد: داک‌استرینگ ماژول و خط `__all__` (خط ۴۲) به ریشه‌ی پکیج (T035) منتقل می‌شوند و بلاک importها بین ماژول‌های دامنه‌ای تقسیم می‌شود (هر ماژول فقط importهای موردنیاز خودش؛ هیچ import بی‌استفاده‌ای منتقل نمی‌شود).
- [ ] T031 [P] [US2] ساخت `inventory/api/services/products.py` (خطوط ۸۸–۲۵۷: `product_queryset`, `_product_values`, `_check_duplicate_code`, `create_product`, `update_product`, `delete_product`, `bulk_delete_products`) و `inventory/api/services/sales.py` (خطوط ۲۵۹–۵۱۸: `sale_queryset`, `_validate_buyer`, `next_invoice_code`, `create_sale`, `update_sale`, `delete_sale`, `bulk_delete_sales`) با importهای خودشان و `from .common import ApiError` (و `_merge_partial`/`_clean_ids` در صورت نیاز).
- [ ] T032 [P] [US2] ساخت `inventory/api/services/payments.py` (خطوط ۵۲۰–۶۷۷) و `inventory/api/services/repairs.py` (خطوط ۶۷۸–۸۰۲) با همان قاعده.
- [ ] T033 [P] [US2] ساخت `inventory/api/services/tracking.py` (۸۰۳–۸۹۰) و `inventory/api/services/settings.py` (۸۹۱–۹۴۰: `brands_list`, `brands_add`, `brands_delete`, `site_settings`, `save_settings`, `set_site_icon`) و `inventory/api/services/uploads.py` (۹۴۱–۱۰۰۲: `_save_uploaded`, `save_upload`).
- [ ] T034 [P] [US2] ساخت `inventory/api/services/calendar.py` (۱۰۰۳–۱۱۲۰: `_repair_cell`, `calendar_month`, `calendar_day`) و `inventory/api/services/reports.py` (۱۱۲۱–۱۱۴۱: `monthly_activity`) و `inventory/api/services/export_import.py` (۱۱۴۲–۱۱۹۸: `_export_funcs`, `export_data_file`, `import_products_file`, `import_template_file`).
- [ ] T035 [US2] ساخت `inventory/api/services/__init__.py` با باز‌export **همه‌ی** نام‌های فهرست‌شده در [contracts/python-imports.md](../contracts/python-imports.md) — از جمله `ApiError` (تست‌ها `from inventory.api.services import ApiError` می‌زنند) و کمکی‌های `_`دار — به‌همراه `__all__` و داک‌استرینگ چیدمان (فرض: ریشه‌ی پکیج دقیقاً همان سطح عمومی قبلی را دارد). داک‌استرینگ و `__all__` این پکیج MUST هیچ اشاره‌ای به لایه‌ی حذف‌شده (`/api/v1/`, DRF) نداشته باشند (متن در گام ۱ تمیز شده است).
- [ ] T036 [US2] حذف ماژول قدیمی: `git rm inventory/api/services.py`.
- [ ] T037 [US2] دروازه‌ی تأیید گام ۳: `.venv/bin/python -c "from inventory.api import services; print(services.create_sale, services.ApiError)"` · `.venv/bin/python -c "from inventory.api.services import ApiError, product_queryset"` · `.venv/bin/python manage.py check` · `find inventory/api/services -name '*.py' -exec wc -l {} + | sort -n | tail -3` (هیچ ماژولی > ۴۰۰ خط) · `git --no-pager diff --stat` (فقط فایل‌های داخل پکیج) · **اجرای کل مجموعه**: `.venv/bin/python manage.py test 2>&1 | tail -4` → `Found <131+N> test(s)` + `OK`.
- [ ] T038 [US2] commit گام ۳: `git add -A && git commit -m 'refactor(api): split services.py into domain modules'` + ثبت `git show --stat HEAD`.

### گام ۴ — تقسیم `compat.py`

- [ ] T039 [US2] ساخت `inventory/api/compat/common.py`: انتقال عیناً `_body`, `_ok`, `_fail`, `_guard` (خطوط ۳۴–۶۳) و `_attachment` (خطوط ۴۳۷–۴۴۸) + importهای لازم. همچنین سرِ ماژول فعلی (`compat.py` خطوط ۱–۳۳: داک‌استرینگ + بلاک importها) MUST جا بیفتد: داک‌استرینگ به ریشه‌ی پکیج (T043) و بلاک importها بین ماژول‌های آداپتور تقسیم می‌شود (بدون هیچ import بی‌استفاده).
- [ ] T040 [P] [US2] ساخت `inventory/api/compat/products.py` (۱۳۸–۱۷۹)، `inventory/api/compat/sales.py` (۱۸۰–۲۳۱) و `inventory/api/compat/payments.py` (۲۳۲–۳۱۲)؛ هر سه با `from inventory.api import services` و `from .common import _body, _fail, _guard, _ok` تا **بدنه‌ی توابع عیناً** بماند.
- [ ] T041 [P] [US2] ساخت `inventory/api/compat/repairs.py` (۳۱۳–۳۶۸)، `inventory/api/compat/tracking.py` (۳۶۹–۴۱۰)، `inventory/api/compat/calendar.py` (۴۱۱–۴۲۵) و `inventory/api/compat/reports.py` (۴۲۶–۴۳۶).
- [ ] T042 [P] [US2] ساخت `inventory/api/compat/settings.py` (۹۶–۱۱۷ برندها + ۵۸۷–۶۰۰ تنظیمات/آیکون)، `inventory/api/compat/uploads.py` (۱۱۸–۱۳۷: `api_upload`, `serve_image`) و `inventory/api/compat/backups_export.py` (۴۴۸–۵۸۶: `export_file`, `api_import_*`, `api_backups*`, `api_database_*`) — طبق انحراف ثبت‌شده در Complexity Tracking.
- [ ] T043 [US2] ساخت `inventory/api/compat/__init__.py` با باز‌export همه‌ی نام‌های آداپتور فهرست‌شده در [contracts/python-imports.md](../contracts/python-imports.md) (تماس `compat.api_sales(...)` از `tikotime/urls.py` باید بدون تغییر کار کند). داک‌استرینگ این پکیج MUST هیچ اشاره‌ای به لایه‌ی حذف‌شده (`/api/v1/`, DRF) نداشته باشد.
- [ ] T044 [US2] حذف ماژول قدیمی: `git rm inventory/api/compat.py`.
- [ ] T045 [US2] دروازه‌ی تأیید گام ۴: `.venv/bin/python -c "from inventory.api import compat; print(compat.api_products, compat.export_file)"` · `grep -rn 'api_brands_add\|_page_ctx' inventory tests tikotime` → ۰ نتیجه · `git --no-pager diff --stat` (فقط فایل‌های داخل پکیج؛ **صفر تغییر** در `tikotime/urls.py` و `tests/`) · **اجرای کل مجموعه**: `.venv/bin/python manage.py test 2>&1 | tail -4` → `Found <131+N> test(s)` + `OK` · بازدید دستی ۸ صفحه.
- [ ] T046 [US2] commit گام ۴: `git add -A && git commit -m 'refactor(api): split compat.py into domain adapters'` + ثبت `git show --stat HEAD`.

**Checkpoint**: «قاعده‌ی ساخت فروش کجاست؟» = یک فایل (`services/sales.py`) و «آداپتور فروش کجاست؟» = یک فایل (`compat/sales.py`). هر دو گام commit جداگانه دارند.

---

## Phase 6: User Story 1 - چیدمان سه‌بخشی، رفتار دست‌نخورده (Priority: P1) 🎯

**Goal**: **گام ۵** — جابه‌جایی فیزیکی به `db/` + `backend/` + `frontend/` با اصلاح تنها منبع حقیقت مسیرها، بدون هیچ تغییری در URLها، پاسخ‌ها یا داده‌ی کاربر.

**Independent Test**: `cd backend && ../.venv/bin/python manage.py test` سبز است؛ ۸ صفحه در مرورگر بدون هیچ ۴۰۴ دارایی بالا می‌آیند؛ آپلود عکس/بکاپ/ریستور/اکسپورت با مسیرهای جدید کار می‌کنند؛ `git status` هیچ فایل داده‌ای قابل commit نشان نمی‌دهد.

**⚠️ هشدار ترتیب**: `tikotime/settings.py` در زمان import پوشه‌های داده را می‌سازد (`mkdir(parents=True, exist_ok=True)`). پس **تا پایان T051 هیچ دستور Django اجرا نکنید** (نه `check`، نه `test`، نه `runserver`)؛ وگرنه یک `data/` خالی دوباره ساخته می‌شود و بعداً `mv` را خراب می‌کند.

- [ ] T047 [US1] آماده‌سازی گام ۵: خاموش‌کردن هر سرور در حال اجرا (`pgrep -af 'manage.py runserver'` → `pkill -f 'manage.py runserver'`) · تازه‌سازی نسخه‌ی نجات (`rm -rf /tmp/tiko-preflight && mkdir -p /tmp/tiko-preflight && cp -a data /tmp/tiko-preflight/data`) · پاک‌سازی کش بایت‌کد: `find . -name '__pycache__' -not -path './.venv/*' -type d -exec rm -rf {} +`. · **ثبت فهرست «قبل» برای دروازه‌ی SC-004**: `find data/images -maxdepth 1 -type f -printf '%f\n' | sort > /tmp/tiko-images-before.txt` (مبنای مقایسه‌ی مجموعه در T048).
- [ ] T048 [US1] جابه‌جایی داده‌ی اجرایی (اول از همه، چون تحت کنترل نسخه نیست): `mv data db` · تأیید: `ls db/` (باید `db.sqlite3`, `watch_inventory.db`, `images/`, `backups/`, `exports/` را ببینید) · **تأیید مجموعه‌ی تصاویر (نه عدد ثابت)**: `find db/images -maxdepth 1 -type f -printf '%f\n' | sort > /tmp/tiko-images-after.txt && diff /tmp/tiko-images-before.txt /tmp/tiko-images-after.txt` → **صفر خط اختلاف** (فهرست «قبل» در T047 ساخته می‌شود؛ Refactor هیچ تصویری اضافه/کم نمی‌کند) · و `test -d data && echo UNEXPECTED || echo OK` → `OK`.
- [ ] T049 [US1] جابه‌جایی دارایی‌های نمایشی: `mkdir -p frontend && git mv static frontend/static && git mv templates frontend/templates` · تأیید: `ls frontend/static/css frontend/static/js frontend/static/fonts | wc -l` و `ls frontend/templates | wc -l` = ۹.
- [ ] T050 [US1] جابه‌جایی کد برنامه: `mkdir -p backend && git mv manage.py requirements.txt tests tikotime inventory backend/` · تأیید: `ls backend/` (باید `manage.py`, `requirements.txt`, `tests/`, `tikotime/`, `inventory/` را ببینید) و `test -f manage.py && echo LEFTOVER || echo OK` → `OK`.
- [ ] T051 [US1] اصلاح مسیرها در `backend/tikotime/settings.py`: `DATA_DIR = BASE_DIR.parent / "db"` · `IMG_DIR = DATA_DIR / "images"` · `BACKUP_DIR = DATA_DIR / "backups"` · `DB_PATH` با همان override محیطی (`TIKOTIME_DB`) · افزودن `STATIC_DIR = BASE_DIR.parent / "frontend" / "static"` و `STATICFILES_DIRS = [STATIC_DIR]` · `TEMPLATES[0]["DIRS"] = [BASE_DIR.parent / "frontend" / "templates"]` · حذف خط `gunicorn` از داک‌استرینگ بالای فایل و به‌روزرسانی آن به اجرای محلی. `BASE_DIR` دست‌نخورده می‌ماند (`Path(__file__).resolve().parent.parent` = `backend/`).
- [ ] T052 [P] [US1] اصلاح `backend/inventory/utils.py`: حذف مسیرسازی با `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` و جایگزینی با `IMG_DIR = settings.IMG_DIR` و `BACKUP_DIR = settings.BACKUP_DIR` (+ `from django.conf import settings`) — **نام‌ها و نوعشان عوض نمی‌شوند** تا patch تست‌ها سالم بماند (R4).
- [ ] T053 [P] [US1] اصلاح `backend/tikotime/jinja.py`: در `static_v()` مسیر فایل دارایی از `settings.STATIC_DIR` خوانده شود (نه `os.path.join(str(settings.BASE_DIR), "static", path)`)، با حفظ دقیق قالب خروجی `STATIC_URL + path + "?v=" + mtime` (R5).
- [ ] T054 [P] [US1] به‌روزرسانی `.gitignore`: خط `data/` → `db/` + اصلاح کامنت‌ها («Runtime data …»). (خط `staticfiles/` در فاز ۴ حذف شده است.)
- [ ] T055 [P] [US1] به‌روزرسانی `README.md` برای چیدمان جدید: درخت سه‌محدوده‌ای، مسیر داده‌ی پیش‌فرض `db/db.sqlite3`، دستور واحد اجرا `.venv/bin/python backend/manage.py runserver`، دستورهای نصب با `backend/requirements.txt`، و دستور تست (`cd backend && ../.venv/bin/python manage.py test`).
- [ ] T056 [P] [US1] به‌روزرسانی حافظه‌ی پروژه: `.memory/INDEX.md` (مسیرهای `db/`، چیدمان `backend/`+`frontend/`، دستور اجرا) و `.claude/PROGRESS.md` (وضعیت جلسه و ترتیب گام‌ها).
- [ ] T057 [US1] یک‌کردن مسیر پوشه‌ی خروجی (FR-004): در `backend/inventory/api/services/export_import.py` (دقیقاً دو نقطه که امروز در `services.py:1162` و `:1177` هستند: `export_data_file` و `import_products_file`) هر دو ساخت دستی مسیر با **یک** کمکی واحد `_export_dir()` جایگزین می‌شود که همچنان از `settings.DATA_DIR` مشتق می‌شود (`os.path.join(str(settings.DATA_DIR), "exports")`) و پوشه را با `os.makedirs(..., exist_ok=True)` می‌سازد. **الزام**: تنظیم مستقل `EXPORT_DIR` اضافه نمی‌شود، چون تست‌های موجود (`tests/test_services_misc.py:145,160,180`) خروجی را با `override_settings(DATA_DIR=tmp)` به پوشه‌ی موقت هدایت می‌کنند و ویرایش آن فایل‌ها طبق FR-010 مجاز نیست. سپس `grep -rn 'exports' backend/inventory/api/services` و تأیید اینکه فقط همین یک کمکی مسیر خروجی را می‌سازد.
- [ ] T058 [US1] **اجرای کل مجموعه پس از جابه‌جایی** (دستور رسمی R7): `cd backend && ../.venv/bin/python manage.py test 2>&1 | tail -6` → `Found <131+N> test(s)` + `OK` (و نه `NO TESTS RAN`)؛ سپس `../.venv/bin/python manage.py check` → `no issues`؛ `../.venv/bin/python manage.py makemigrations --check --dry-run` → `No changes detected`؛ و بازگشت به ریشه: `cd .. && test -d data && echo 'UNEXPECTED data/ recreated' || echo 'OK: no stray data/'`.
- [ ] T059 [US1] اعتبارسنجی دستی پس از جابه‌جایی: اجرای `.venv/bin/python backend/manage.py runserver` و بازدید ۸ صفحه در مرورگر (۰ درخواست ۴۰۴ برای css/js/فونت/عکس) · آپلود یک عکس (باید در `db/images/` بنشیند و در UI دیده شود) · ساخت بکاپ و ریستور (فایل در `db/backups/`) · اکسپورت و ایمپورت اکسل (فایل در `db/exports/`) · تغییرات `db/` به‌عنوان فایل جدید در `git status` دیده نشوند. **توجه**: آپلود دستی در همین گام یک تصویر **جدید** به `db/images/` اضافه می‌کند (رفتار مورد انتظار کاربر)؛ مقایسه‌ی مجموعه‌ی تصاویر در T048 انجام شده است، پس این افزایش یک-تصویری رگرسیون نیست.
- [ ] T060 [US1] بازبینی و commit گام ۵: `git add -A && git --no-pager status --short` (باید فقط تغییرات کد/مستندات را ببینید و **هیچ** فایل زیر `db/` را) سپس `git commit -m 'refactor: reorganize into db/ backend/ frontend/ with a single path source'` و ثبت `git show --stat HEAD`.

**Checkpoint**: چیدمان نهایی هدف محقق شده است و SC-001، SC-004، SC-005، SC-009 و SC-010 این‌جا اثبات می‌شوند.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: اثبات نهایی «بدون تغییر رفتار» و اتمام مستندات/حافظه‌ی پروژه

- [ ] T061 [P] جست‌وجوی ارجاع کهنه (منجمدشده‌ها را حذف نکنید): `grep -rn 'staticfiles\|collectstatic\|gunicorn\|whitenoise\|rest_framework\|api/v1' --include='*.py' --include='*.md' --include='*.txt' --include='*.html' --include='*.js' backend frontend README.md .gitignore` → انتظار **۰ نتیجه** (پوشه‌های `specs/`، `.memory/JOURNAL.md` و تاریخچه‌ی git از این جست‌وجو مستثنا هستند چون تاریخ را روایت می‌کنند).
- [ ] T062 [P] بررسی ارتفاع ماژول‌ها (SC-006): `find backend/inventory/api -name '*.py' ! -name '__init__.py' -exec wc -l {} + | sort -n` → هیچ ماژولی > ۴۰۰ خط؛ و `ls backend/inventory/api/*.py` نباید دیگر `services.py` یا `compat.py` را نشان بدهد (جایشان پکیج است).
- [ ] T063 نصب از صفر در محیط تازه (SC-005): `python3 -m venv /tmp/tiko-fresh && /tmp/tiko-fresh/bin/pip -q install -r backend/requirements.txt` · `cat backend/requirements.txt` (سه ردیف) · `/tmp/tiko-fresh/bin/python backend/manage.py check` · `cd backend && /tmp/tiko-fresh/bin/python manage.py test tests.test_legacy_api_baseline 2>&1 | tail -4` → سبز · سپس `rm -rf /tmp/tiko-fresh`.
- [ ] T064 اجرای کامل سناریوهای [quickstart.md](./quickstart.md) (V1 تا V11) و ثبت نتیجه‌ی هر کدام در `.memory/COMMANDS.md`؛ هر سناریویی که شکست خورد باید پیش از پایان این فاز رفع شود.
- [ ] T065 تأیید تطابق درخت نهایی با چیدمان هدف: `find . -maxdepth 2 -not -path './.venv*' -not -path './.git*' -not -path './specs*' | sort` و مقایسه با درخت «After» در [plan.md](./plan.md) — انتظار: `db/`, `backend/`, `frontend/`, مستندات، پوشه‌های ابزار و `.venv/`؛ هیچ فایل کد/داده/نمایشی بیرون این‌ها.
- [ ] T066 تأیید قراردادهای منجمد: (الف) [contracts/legacy-api.md](../contracts/legacy-api.md) — `grep -c '    path(' backend/tikotime/urls.py` باید **۴۸** باشد (۳۸ مسیر لگاسی + ۹ مسیر صفحه + ۱ مسیر استاتیک جدید) و `grep -rn 'api/v1' backend 2>/dev/null` هیچ نتیجه‌ای نداشته باشد؛ پیشوندهای فرانت (`frontend/static/js`, `frontend/templates`) دست‌نخورده بمانند. (ب) [contracts/python-imports.md](../contracts/python-imports.md) — همه‌ی نام‌های فهرست‌شده از ریشه‌ی هر دو پکیج import شوند: `cd backend && ../.venv/bin/python -c "from inventory.api import services, compat; n1=[n for n in dir(services) if not n.startswith('__')]; n2=[n for n in dir(compat) if not n.startswith('__')]; print(len(n1), len(n2))"` بدون `ImportError` و با شمارش بزرگ‌تر از ۳۵ و ۴۰.
- [ ] T067 به‌روزرسانی حافظه‌ی پروژه و commit پایانی اسناد: افزودن دستورهای اجرا‌شده به `.memory/COMMANDS.md`، یک ورودی ژورنال به سبک commit در `.memory/JOURNAL.md` (چکیده‌ی گام‌ها + اعداد قبل/بعد: ۶→۳ کتابخانه، ۱۴۷+N تست، ۱۳۹ تصویر، ۱۱۹۸+۶۰۰ خط → ۲۲ ماژول دامنه‌ای) و وضعیت نهایی در `.claude/PROGRESS.md`؛ سپس `git add -A && git commit -m 'docs(memory): journal entry for the layout restructure and module split'`.
- [ ] T068 بازبینی بازگشت‌پذیری و ترتیب (SC-011): `git --no-pager log --oneline -12` → انتظار ترتیب: `spec-kit: …` (commit مستندات، از قبل ثبت‌شده در `19e4975`) → `test(api) baseline` → `refactor(api) drop v1` → `chore drop gunicorn/whitenoise` → `refactor(api) split services` → `refactor(api) split compat` → `refactor: reorganize` → `docs(memory)`؛ و برای هر گام تأیید اینکه `git revert <sha>` تنها همان گام را برمی‌گرداند.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: بدون وابستگی؛ همان ابتدا.
- **Phase 2 (Foundational / گام ۰)**: وابسته به Phase 1 — **همه‌ی داستان‌ها را قفل می‌کند** (SC-011). بدون آن «بدون تغییر رفتار» قابل اثبات نیست.
- **Phase 3 (US3 / گام ۱)**: وابسته به Phase 2.
- **Phase 4 (US4 / گام ۲)**: وابسته به Phase 3 (اول DRF حذف شود تا جدول وابستگی‌ها یک‌بار تمیز شود).
- **Phase 5 (US2 / گام ۳ و ۴)**: وابسته به Phase 4؛ داخل خودش گام ۳ سپس گام ۴ (دو commit جدا).
- **Phase 6 (US1 / گام ۵)**: وابسته به Phase 5 (درخت سبک‌شده جابه‌جا می‌شود).
- **Phase 7 (Polish)**: وابسته به همه‌ی فازها.

### زنجیره‌ی بحرانی (خطی، بدون شاخه)

```text
T001..T003 (Setup)
   └─► T004..T010 (گام ۰: ماژول مرجع — قفل رفتار)
          └─► T011..T020 (گام ۱: حذف /api/v1 + DRF + دو تابع بی‌استفاده)
                 └─► T021..T028 (گام ۲: حذف gunicorn/whitenoise + مسیر استاتیک)
                        └─► T029..T038 (گام ۳: تقسیم services.py)
                               └─► T039..T046 (گام ۴: تقسیم compat.py)
                                      └─► T047..T060 (گام ۵: جابه‌جایی به db/ backend/ frontend/)
                                             └─► T061..T068 (اعتبارسنجی نهایی + مستندات)
```

**هیچ داستانی موازی با دیگری نیست**: همه روی همان درخت کار می‌کنند و ترتیبشان با spec و دستور کاربر تثبیت شده است (هر گام یک commit و یک اجرای کامل تست). موازی‌سازی فقط **درون** هر فاز ممکن است (فایل‌های مستقل).

### قواعد درونی هر فاز

- تا اجرای کامل تست و سبز نشدن، commit انجام نمی‌شود؛ پیام commit هر گام در همان فاز مشخص شده است.
- در گام ۳ و ۴، تست‌ها و `tikotime/urls.py` نباید ویرایش شوند — تنها معیار موفقیت همین است.
- در گام ۵ (فاز ۶) ترتیب درونی الزامی است: خاموش‌کردن سرور → جابه‌جایی داده → دارایی‌ها → کد → اصلاح مسیرها → تست → بازدید مرورگر → commit.

### Parallel Opportunities

| فاز | وظایف موازی [P] | چرا موازی‌اند |
|---|---|---|
| Phase 1 | T002 | تور نجات مستقل از بازبینی وضعیت است |
| Phase 3 (US3) | T012 · T013 · T014 · T017 · T018 | پنج فایل متفاوت (`urls.py`، `settings.py`، `requirements.txt`، `api/__init__.py`، README/INDEX) |
| Phase 4 (US4) | T021 · T024 · T025 · T026 | `requirements.txt` · پوشه/`.gitignore` · `README.md` · `.memory/INDEX.md` |
| Phase 5 (US2) — گام ۳ | T031 · T032 · T033 · T034 | چهار گروه ماژول تازه در `services/` (فایل‌های جدا) |
| Phase 5 (US2) — گام ۴ | T040 · T041 · T042 | سه گروه ماژول تازه در `compat/` (فایل‌های جدا) |
| Phase 6 (US1) | T052 · T053 · T054 · T055 · T056 | `utils.py` · `jinja.py` · `.gitignore` · `README.md` · حافظه‌ی پروژه |
| Phase 7 | T061 · T062 | جست‌وجوی ارجاع کهنه و شمارش خطوط، هر دو فقط-خواندن |

**نکته**: فازهای ۲ و ۵ (`T004..T010` و `T035`/`T043`) و فاز ۶ به‌ترتیب `T047..T051` و `T057..T060` **موازی‌پذیر نیستند** چون یا یک فایل واحد را می‌سازند یا زنجیره‌ی وابسته‌اند (`__init__.py` پس از ماژول‌ها، حذف ماژول قدیمی پس از آن، تست پس از جابه‌جایی).

### Parallel Example: Phase 5 — گام ۳ (تقسیم `services.py`)

```bash
# پس از T029 (آماده‌سازی) و T030 (common.py)، چهار گروه زیر را با هم شروع کنید:
Task: "T031 [P] [US2] ساخت services/products.py (88–257) و services/sales.py (259–518)"
Task: "T032 [P] [US2] ساخت services/payments.py (520–677) و services/repairs.py (678–802)"
Task: "T033 [P] [US2] ساخت services/tracking.py (803–890), settings.py (891–940), uploads.py (941–1002)"
Task: "T034 [P] [US2] ساخت services/calendar.py (1003–1120), reports.py (1121–1141), export_import.py (1142–1198)"
# سپس ترتیبی: T035 (__init__.py) → T036 (حذف services.py) → T037 (دروازه) → T038 (commit)
```

### Parallel Example: Phase 5 — گام ۴ (تقسیم `compat.py`)

```bash
Task: "T040 [P] [US2] ساخت compat/products.py, sales.py, payments.py"
Task: "T041 [P] [US2] ساخت compat/repairs.py, tracking.py, calendar.py, reports.py"
Task: "T042 [P] [US2] ساخت compat/settings.py, uploads.py, backups_export.py"
# سپس ترتیبی: T043 (__init__.py) → T044 (حذف compat.py) → T045 (دروازه) → T046 (commit)
```

### Parallel Example: Phase 3 (US3)

```bash
Task: "T012 [P] [US3] حذف include نسخه‌بندی‌شده از tikotime/urls.py"
Task: "T013 [P] [US3] حذف rest_framework و بلاک REST_FRAMEWORK از tikotime/settings.py"
Task: "T014 [P] [US3] حذف ردیف djangorestframework از requirements.txt"
Task: "T017 [P] [US3] به‌روزرسانی داک‌استرینگ inventory/api/__init__.py"
Task: "T018 [P] [US3] به‌روزرسانی README.md و .memory/INDEX.md"
# T011 (حذف ۵ فایل)، T015 (compat.py)، T016 (تست v1) قبل/کنار این‌ها؛ T019 دروازه و T020 commit.
```

### Parallel Example: Phase 6 (US1) — پس از جابه‌جایی

```bash
Task: "T052 [P] [US1] اصلاح IMG_DIR/BACKUP_DIR در backend/inventory/utils.py"
Task: "T053 [P] [US1] اصلاح static_v در backend/tikotime/jinja.py"
Task: "T054 [P] [US1] به‌روزرسانی .gitignore (data/ → db/)"
Task: "T055 [P] [US1] به‌روزرسانی README.md برای چیدمان جدید"
Task: "T056 [P] [US1] به‌روزرسانی .memory/INDEX.md و .claude/PROGRESS.md"
```

---

## Implementation Strategy

### درباره‌ی «MVP» در این فیچر

الگوی معمول «فقط User Story 1 = MVP» این‌جا **اعمال نمی‌شود**: US1 (چیدمان سه‌بخشی) با اولویت P1، عمداً **آخرین** گام است چون پرریسک‌ترین است و باید روی درختی انجام شود که قبلاً سبک و تثبیت شده است. در عوض، این Refactor یک **زنجیره‌ی افزایشی** است و هر فاز خودش یک increment قابل تحویل و قابل بازگشت است:

| Increment | شامل | چه چیزی تحویل می‌دهد | اثبات |
|---|---|---|---|
| **I1** | T001..T010 | قفل قرارداد لگاسی روی کد دست‌نخورده (نخستین commit ساختاری) | `git show --stat HEAD` = یک فایل تست؛ `Found 147+N` سبز |
| **I2** | T011..T020 | فقط یک قرارداد API؛ DRF و لایه‌ی موازی حذف شد | صفر ارجاع؛ `131+N` سبز؛ `/api/v1/*` = ۴۰۴ پیش‌فرض جنگو |
| **I3** | T021..T028 | نصب سه‌کتابخانه‌ای + اجرا و استاتیک مستقل از DEBUG | ۲۰۰ برای دارایی در `DEBUG=0` |
| **I4** | T029..T038 | `services/` دامنه‌ای (۱۱ ماژول) | صفر تغییر در صدا‌زننده‌ها؛ ≤۴۰۰ خط |
| **I5** | T039..T046 | `compat/` دامنه‌ای (۱۱ ماژول) | صفر تغییر در `urls.py`/تست‌ها |
| **I6** | T047..T060 | چیدمان `db/` + `backend/` + `frontend/` | ۸/۸ صفحه، عملیات فایل‌محور، `git status` پاک |
| **I7** | T061..T068 | اعتبارسنجی نهایی + مستندات/حافظه | quickstart V1–V11 سبز |

**نقطه‌ی شروع پیشنهادی (اولین تحویل معنادار)**: I1+I2 (پایه‌ی امن + یک قرارداد API). این نقطه بدون هیچ ریسکی روی چیدمان، ارزش واقعی می‌دهد.

### Stop-and-Validate

پس از هر increment (یعنی پس از هر commit) توقف و اعتبارسنجی مستقل انجام می‌شود: اجرای کل مجموعه‌ی تست + بازدید ۸ صفحه + (برای I3 و I6) بررسی‌های ویژه‌ی همان گام. اگر چیزی سبز نبود، **گام بعد شروع نمی‌شود**؛ ابتدا همان گام اصلاح یا `git revert` می‌شود.

### Parallel Team Strategy

زنجیره‌ی کلی خطی است (هر گام روی همان درخت و وابسته به گام قبل)، پس تقسیم فازها بین چند نفر معنا ندارد. تنها شکل موازی‌سازی، گروه‌های `[P]` **درون** یک فاز است (جدول Parallel Opportunities). اگر دو نفر کار می‌کنند: یک نفر گام جاری را می‌برد و نفر دوم می‌تواند گروه‌های `[P]` همان فاز را بردارد (مثلاً ساخت ماژول‌های `services/`)، ولی commit و دروازه‌ی تست همیشه در یک نقطه‌ی واحد بسته می‌شود.

### محدودیت‌های سخت این فیچر (تکرار تأکیدها)

- **تست‌ها هرگز به داده‌ی واقعی دست نمی‌زنند**: هر تستی که فایل/بکاپ/تصویر می‌سازد باید `override_settings` روی پوشه‌ی موقت داشته باشد (T007/T008).
- **در گام‌های ۳ و ۴ هیچ صدا‌زننده‌ای ویرایش نمی‌شود**؛ اگر لازم شد، یعنی طراحی تقسیم اشتباه است و باید اصلاح شود، نه اینکه صدا‌زننده عوض شود (SC-007).
- **در بازه‌ی جابه‌جایی (T047 تا T051) هیچ دستور Django اجرا نمی‌شود**؛ وگرنه `settings.py` پوشه‌ی `data/` را دوباره می‌سازد و `mv` بعدی را خراب می‌کند.

---

## Notes

- `[P]` یعنی فایل‌های متفاوت و بدون وابستگی به کار ناتمام؛ در غیر این صورت وظیفه ترتیبی است.
- برچسب‌های `[US1]..[US4]` به داستان‌های spec.md نگاشت می‌شوند: US1 = چیدمان سه‌بخشی، US2 = تقسیم دامنه‌ای، US3 = یک قرارداد API، US4 = اجرای سبک و مستقل از DEBUG.
- **گام ۰ (فاز ۲) پیش از هر تغییر ساختاری است** و نخستین commit این تغییر محسوب می‌شود (FR-015، FR-026، SC-011).
- **قاعده‌ی شمارش تست (`N`)**: `N` = تعداد تست‌های ماژول مرجع جدید (همان عدد ثابت‌شده در T009). هر جا در این سند `<147+N>` یا `<131+N>` آمده، شرط پذیرش «عدد گزارش‌شده ≥ عدد پایه + N» است (عدد پایه پیش از گام ۱ = ۱۴۷ و پس از حذف ۱۶ تست لایه‌ی v1 = ۱۳۱) و همه‌ی تست‌ها MUST سبز باشند.
- **پس از هر گام ساختاری، یک اجرای کامل تست** به‌عنوان دروازه انجام می‌شود (T019، T027، T037، T045، T058) و تنها در صورت سبز بودن commit می‌شود (FR-026).
- تنها فایل تستی که حذف می‌شود `tests/test_api_v1.py` است؛ تنها فایل تستی که اضافه می‌شود `tests/test_legacy_api_baseline.py` است؛ هیچ فایل تست دیگری ویرایش نمی‌شود (FR-010 + تصمیم Q3).
- قراردادهای منجمد را پیش از هر گام مرور کنید: [contracts/legacy-api.md](../contracts/legacy-api.md) · [contracts/python-imports.md](../contracts/python-imports.md) · [contracts/ops-commands.md](../contracts/ops-commands.md).
- تله‌ی عملیاتی: `backend/manage.py test` **بدون برچسب از ریشه** = `NO TESTS RAN`؛ همیشه یکی از دو صورت تأییدشده‌ی R7 استفاده شود.
- پرهیزها: بازنویسی توابع هنگام انتقال · ویرایش صدا‌زننده‌ها در گام‌های ۳ و ۴ · افزودن وابستگی جدید · تغییر محتوای قالب‌ها و css/js · دست‌زدن به داده‌ی واقعی در تست‌ها · انجام دو گام در یک commit.




