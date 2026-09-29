# Quickstart — بازآرایی چیدمان و تقسیم ماژول‌ها (راهنمای اعتبارسنجی)

**Feature**: `001-restructure-project-layout` | **Spec**: [spec.md](./spec.md) | **Design**: [plan.md](./plan.md) · [data-model.md](./data-model.md) · [research.md](./research.md) · [contracts/](./contracts/)

> این سند فقط **چطور اعتبارسنجی کنیم** را می‌گوید. جزئیات پیاده‌سازی (محتوای توابع، فهرست وظایف) جای دیگری است. قراردادها در `contracts/` تعریف شده‌اند و این‌جا تکرار نمی‌شوند.

## پیش‌نیازها

- پایتون ۳.۱۰+ (محیط فعلی: ۳.۱۴.۴) و محیط مجازی موجود در **ریشه‌ی مخزن**: `.venv/`
- Django 5.2.6 نصب‌شده در همان venv (پس از گام‌های ۱ و ۲ فقط سه کتابخانه باقی می‌ماند)
- داده‌ی واقعی دست‌نخورده: `db/db.sqlite3` + `db/images/` (۱۳۵ فایل) + `db/backups/` + `db/exports/`
- برنامه **خاموش** در گام ۵ (جابه‌جایی فیزیکی داده‌ها)

## آماده‌سازی (یک‌بار)

```bash
cd '/media/MyShit/Works/Tick O Time/DB/Watch Inventory'
.venv/bin/python backend/manage.py check                            # انتظار: no issues
.venv/bin/python backend/manage.py test backend/tests               # انتظار: همه سبز، Found ≥۱۴۷ (پس از گام ۰: ۱۴۷+N)
```

> پیش از گام ۵ همین دستورها را با مسیرهای فعلی بزنید: `.venv/bin/python manage.py check` و `.venv/bin/python manage.py test`.

## حلقه‌ی دروازه‌ی هر گام (۰ تا ۵)

پس از **هر** گام، به‌ترتیب:

```bash
# 1) کل مجموعه‌ی تست (صورت رسمی — از داخل محدوده‌ی کد)
cd backend && ../.venv/bin/python manage.py test ; cd ..

# 2) سلامت تنظیمات و نبود مهاجرت تازه
.venv/bin/python backend/manage.py check
.venv/bin/python backend/manage.py makemigrations --check --dry-run

# 3) بازگشت‌پذیری: هر گام دقیقاً یک commit
git --no-pager log --oneline -1
```

| گام | کار | دروازه‌ی اضافه‌ی مخصوص همان گام | انتظار |
|---|---|---|---|
| **۰** | افزودن ماژول تست مرجع (فقط مسیرهای لگاسی) | `manage.py test` روی کد دست‌نخورده + `git log` | سبز **پیش از** هر تغییر ساختاری؛ این نخستین commit است (SC-011) |
| **۱** | حذف `/api/v1/` + DRF + دو تابع بی‌استفاده | `grep -rn 'rest_framework\|api/v1' --include=*.py .` + `curl -s -o /dev/null -w '%{http_code}' localhost:8000/api/v1/products` | صفر ارجاع باقی‌مانده؛ پاسخ مسیر حذف‌شده = ۴۰۴ لگاسی `{"ok": false, "error": "یافت نشد"}`؛ تعداد تست = ۱۴۷+N−۱۶ |
| **۲** | حذف gunicorn/whitenoise + مسیر استاتیک صریح | `DJANGO_DEBUG=0 .venv/bin/python backend/manage.py runserver` و درخواست یک دارایی | `200` برای `/static/css/app.css?v=...` در DEBUG=0 (R3)؛ `requirements.txt` سه خطی |
| **۳** | تقسیم `services.py` → پکیج | `git diff --stat` + جست‌وجوی ارتفاع ماژول‌ها | صفر تغییر در صدا‌زننده‌ها؛ هیچ ماژول > ۴۰۰ خط؛ پوشه‌ی خالی قبلی پاک شده |
| **۴** | تقسیم `compat.py` → پکیج | همان + `grep -rn 'api_brands_add\|_page_ctx'` | صفر ارجاع؛ صفر تغییر در `tikotime/urls.py` و تست‌ها |
| **۵** | `db/` + `backend/` + `frontend/` | `git status` + مرورگر + عملیات فایل‌محور | هیچ فایل داده‌ای قابل commit نیست؛ ۸/۸ صفحه بدون ۴۰۴؛ آپلود/بکاپ/اکسپورت کار می‌کند |

## سناریوهای اعتبارسنجی (نگاشت به SC)

### V1 — صفحه‌ها و دارایی‌ها (SC-001، FR-007)
```bash
.venv/bin/python backend/manage.py runserver &
for p in dashboard products calendar repairs sold tracking payments settings; do
  printf '%s -> %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/$p)"
done
curl -s http://127.0.0.1:8000/dashboard | grep -o 'href="static/[^"]*\|src="static/[^"]*' | sort -u
```
**انتظار**: هر ۸ مسیر `200`؛ هر داراییِ استخراج‌شده با `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/<مسیر>` هم `200`.
**تکمیل دستی (الزامی)**: در مرورگر هر ۸ صفحه را باز کنید و در پنل Network تأیید کنید **۰ درخواست ۴۰۴** برای css/js/فونت/عکس وجود ندارد.

### V2 — برابری پاسخ‌ها با مرجع (SC-002، FR-008)
```bash
cd backend && ../.venv/bin/python manage.py test tests.test_legacy_api_baseline ; cd ..
```
**انتظار**: همه سبز. این ماژول همان «مقایسه‌ی کلید/مقدار» را روی داده‌ی ثابت اجرا می‌کند (تصمیم Q2).

### V3 — تعداد و سلامت کل مجموعه‌ی تست (SC-003)
```bash
cd backend && ../.venv/bin/python manage.py test 2>&1 | tail -4 ; cd ..
```
**انتظار**: `Found N test(s)` با N = ۱۴۷ + تست‌های ماژول مرجع − ۱۶ (تست‌های لایه‌ی حذف‌شده) و `OK`. اگر `NO TESTS RAN` دیدید یعنی برچسب/دایرکتوری اشتباه است (تله‌ی R7).

### V4 — داده‌ی کاربر و عملیات فایل‌محور (SC-004، FR-011)
```bash
ls db/ && ls db/images | wc -l && ls db/backups | head -3 && ls db/exports | head -3
.venv/bin/python -c "import sqlite3;c=sqlite3.connect('db/db.sqlite3');print(c.execute('PRAGMA integrity_check').fetchone()[0])"
```
**انتظار**: `db/db.sqlite3` + `images/` + `backups/` + `exports/` موجود؛ `images` همان ۱۳۵ فایل؛ `integrity_check` = `ok`.
**تکمیل دستی (الزامی)**: در UI یک عکس آپلود کنید، بکاپ بسازید، ریستور کنید، اکسل اکسپورت و ایمپورت کنید؛ هر چهار عملیات موفق و فایل‌های خروجی داخل `db/` ساخته شوند.

### V5 — کمینه بودن وابستگی‌ها (SC-005، FR-020)
```bash
cat backend/requirements.txt
python3 -m venv /tmp/tiko-fresh && /tmp/tiko-fresh/bin/pip -q install -r backend/requirements.txt && echo INSTALL_OK
```
**انتظار**: دقیقاً سه ردیف (`Django`, `Jinja2`, `openpyxl`)؛ نصب از صفر موفق؛ صفر ارجاع به `djangorestframework`/`gunicorn`/`whitenoise` در کد و مستندات.

### V6 — ارتفاع ماژول‌ها (SC-006، FR-021)
```bash
find backend/inventory/api -name '*.py' ! -name '__init__.py' -exec wc -l {} + | sort -n | tail -5
```
**انتظار**: هیچ ماژولی > ۴۰۰ خط؛ هر دامنه دقیقاً یک ماژول؛ `services.py` و `compat.py` دیگر وجود ندارند (جایشان پکیج است).

### V7 — صفر تغییر در صدا‌زننده‌ها و تست‌ها (SC-007، FR-009)
```bash
git --no-pager diff --stat <commit-گام-۲>..<commit-گام-۳>    # و همان برای گام ۴
git --no-pager status --short --untracked-files=all frontend/ tests/ tikotime/
```
**انتظار**: در گام‌های ۳ و ۴ فقط فایل‌های داخل پکیج‌های `services/` و `compat/` تغییر کرده‌اند؛ `frontend/`، `tests/` و `tikotime/` صفر تغییر.

### V8 — دیده شدن تغییر دارایی بدون گام انتشار (SC-008)
یک فاصله/رنگ در `frontend/static/css/app.css` را عوض کنید، صفحه را در مرورگر رفرش کنید و تغییر را ببینید؛ سپس تغییر را برگردانید.
**انتظار**: بدون هیچ `collectstatic` یا گام اضافه، تغییر دیده می‌شود (مهر `?v=` از mtime واقعی فایل می‌آید، R5).

### V9 — یافتن سریع هر چیز (SC-009)
```bash
ls          # فقط db/ backend/ frontend/ + مستندات + .specify/ .clinerules/ .memory/ .claude/ .venv/
grep -rln 'def create_sale' backend/inventory/api/services/ | head
```
**انتظار**: محدوده‌ها در یک نگاه؛ قاعده‌ی ساخت فروش فقط در `services/sales.py` (یک گام).

### V10 — پیشوندهای URL بدون تغییر (SC-010، FR-006)
```bash
grep -rn '/data/images/\|/static/\|/api/' frontend/static/js frontend/templates | wc -l   # فقط برای مقایسه با قبل
grep -rn 'api/v1' frontend/ backend/ tikotime/ 2>/dev/null | wc -l                        # انتظار: 0
```
**انتظار**: هیچ مسیر فرانت‌محوری عوض نشده؛ صفر ارجاع به `api/v1`.

### V11 — ترتیب و برگشت‌پذیری commitها (SC-011، FR-026)
```bash
git --no-pager log --oneline -8
git show --stat $(git log --format=%H --reverse | head -1)   # نخستین commit این کار
```
**انتظار**: نخستین commit = افزودن ماژول تست مرجع (فقط همان فایل)؛ سپس به‌ترتیب گام‌های ۱..۵، هر کدام یک commit مستقل و قابل `git revert`.

## بازگشت به عقب (در صورت شکست هر گام)

```bash
git revert <commit-همان-گام>       # بازگشت فقط همان گام
cd backend && ../.venv/bin/python manage.py test   # تأیید سبز شدن دوباره
```
اگر گام ۵ نیمه‌کاره ماند: چون جابه‌جایی در یک commit انجام می‌شود، `git revert` کد را برمی‌گرداند و باید `db/` را دستی به `data/` برگرداند (برنامه خاموش، `mv db data`).

## وضعیت نهایی مورد انتظار

```text
project-root/
├── db/         # db.sqlite3 · images/ (۱۳۵) · backups/ · exports/     ← نادیده در git
├── backend/    # manage.py · requirements.txt (۳ خط) · tests/ · tikotime/
│   └── inventory/
│       ├── models.py · utils.py · dbhelpers.py · excel_io.py · jalali.py · reports.py
│       ├── views/pages.py
│       └── api/
│           ├── services/   # ۱۱ ماژول دامنه‌ای + __init__ (re-export همه‌چیز)
│           ├── compat/     # ۱۱ ماژول دامنه‌ای + __init__ (re-export همه‌چیز)
│           └── __init__.py
├── frontend/   # static/ (css, js, fonts) · templates/ (۹ قالب)
├── README.md · .gitignore · .memory/ · .specify/ · .clinerules/ · .claude/ · .venv/
```
اجرا: `.venv/bin/python backend/manage.py runserver` — تست: `cd backend && ../.venv/bin/python manage.py test`

