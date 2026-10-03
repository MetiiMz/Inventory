# PROGRESS — session status

## جلسه‌ی ۲۰۲۶-۱۰-۰۳ — Restructure layout (spec 001) در حال اجرا
- گام‌های ۰ تا ۵ انجام شد: قفل قرارداد لگاسی، حذف DRF/لایه‌ی موازی، اجرا+استاتیک مستقل از DEBUG، `services/` و `compat/` (پکیج ۱۱ ماژولی)، و **چیدمان سه‌بخشی `db/` + `backend/` + `frontend/`** (تک منبع حقیقت مسیرها = `backend/tikotime/settings.py`).
- اجرای کنونی: `.venv/bin/python backend/manage.py runserver` · ۱۵۳ تست سبز · جابه‌جایی‌ها بازگردان‌پذیرند (`mv db data` / `git mv` بازگشت).
- نکته‌ی آتی: `backend/tests/test_services_misc.py` (کلاس `UploadServiceTests`) در هر اجرای کامل، دو تصویر fixture ۱×۱ را در `db/images/` می‌نویسد چون `IMG_DIR` را ایزوله نمی‌کند؛ FR-010 ویرایش این تست را در این refactor ممنوع می‌کند → پیگیری جدا (خروجی‌ها gitignored هستند و commit نمی‌شوند).

## جلسه‌ی ۲۰۲۶-۰۹-۱۰ — API-first backend + full test suite (آرشیو)

## کارهای امروز (به ترتیب commit)
1. `9668798→96687f8` **refactor(api):** حذف کامل ویوهای تابعی قدیمی (`inventory/views/*` — ۱۲ فایل، ~۱٬۵۵۰ خط). فقط `pages.py` (شِل HTML) ماند. همه‌ی قواعد کسب‌وکار به **`inventory/api/services.py`** (تک منبع حقیقت) منتقل شد؛ `/api/v1/` حالا مستقیم از سرویس‌ها می‌نویسد (PATCH بومی، بدون آداپتور `_legacy`)؛ `exceptions.py` خطای `ApiError` را به `{"error": …, "ok": false}` استاندارد تبدیل می‌کند.
2. همان commit: **`inventory/api/compat.py`** — آداپتورهای نازک `/api/*` با شکل پاسخ قدیمی (قرارداد فرانت‌اند، بدون منطق). باگ واقعی پیدا و رفع شد: برند-اضافه POST باید کار کند (نه فقط GET). رفتارهای عجیب قدیمی عمداً حفظ شدند (بیعانه روی ساعت ناموجود = ۲۰۰، `add` فلگ تسویه‌ی فروش را عوض نمی‌کند).
3. `e7d6628` **test:** ۱۴۷ تست در ۱۰ ماژول داخل `tests/` — برای همه‌ی توابع/کلاس‌ها: جلالی، utils (سریالایزرهای dict)، سه ماژول سرویس (محصول/فروش/زیرساخت)، dbhelpers+reports، تقویم/آپلود/اکسل، لایه‌ی DRF و قرارداد compat. **قانون ایمنی:** تست‌ها هرگز به DB واقعی نمی‌زنند (مسیرهای raw-sqlite به فایل‌های موقتی mock می‌شوند).
4. `cd9cef8`, `aca3162` docs(memory): ورودی‌های ژورنال برای هر دو.

## معماری فعلی بک‌اند
- `/api/v1/` — هسته‌ی اصلی (DRF ViewSet ها + infra) → همه از `services.py` استفاده می‌کنند.
- `/api/*` — همان مسیرهایی که فرانت‌اند فعلی صدا می‌زند (compat، بدون منطق) تا مهاجرت فرانت‌اند.
- `inventory/views/` = فقط `pages.py`؛ `inventory/api/` = services, serializers, views, urls, exceptions, fields, compat.

## تست و اعتبارسنجی
- `manage.py test tests` → **147/147 پاس** · `manage.py check` تمیز · `makemigrations --check` همگام · ۸۶/۸۶ اسموک E2E هر دو لایه روی DB موقتی · دودِ DB واقعی (فقط-خواندن) سالم.

## پس از این
- مهاجرت فرانت‌اند به `/api/v1/` (هر وقت خواستید) — پس از آن `compat.py` حذف می‌شود.
- توجه: `.claude/` فقط `launch.json` دارد؛ حافظه‌ی پروژه در `.memory/` است (این فایل فقط وضعیت جلسه را نگه می‌دارد).

---
--- (آرشیو — PROGRESS.md قبلی در `331defd` حذف شده بود؛ محتوای کامل آن در `git show 331defd^:.claude/PROGRESS.md` موجود است) ---
