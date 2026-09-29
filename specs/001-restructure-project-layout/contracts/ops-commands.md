# Contract: قرارداد اجرا و عملیات (منجمد)

**Feature**: `001-restructure-project-layout` | **Spec**: [../spec.md](../spec.md) | **تصمیم‌های مرتبط**: Q1 (استاتیک مستقل از DEBUG)، Q5 (دستور واحد اجرا)، R7 (دستور تست)

## ۱. نصب (از صفر)

محیط مجازی **در ریشه‌ی مخزن** می‌ماند (جابه‌جا نمی‌شود؛ venv جابه‌جاشدنی نیست) و فقط سه کتابخانه نصب می‌شود:

```bash
python3 -m venv .venv                                   # فقط بار اول
.venv/bin/pip install -r backend/requirements.txt        # Django, Jinja2, openpyxl
.venv/bin/python backend/manage.py migrate
```

**منجمد**: مانیفست وابستگی **نباید** شامل `djangorestframework`، `gunicorn` یا `whitenoise` باشد (FR-018، SC-005). هیچ گامی نباید به `collectstatic` نیاز داشته باشد (FR-019).

## ۲. اجرا (یک دستور، از ریشه‌ی مخزن)

```bash
.venv/bin/python backend/manage.py runserver
```

سپس در مرورگر: `http://127.0.0.1:8000` (پورت/میزبان پیش‌فرض بدون تغییر). هیچ صورت دومی مستند نمی‌شود (FR-005، FR-027).

**استقلال از DEBUG**: فایل‌های `frontend/static/**` در هر حالتی سرو می‌شوند — چه `DEBUG=1` (هندلر خود `runserver`) و چه `DEBUG=0` (مسیر استاتیک صریح، R3). پس تغییر `DJANGO_DEBUG` نباید هیچ ۴۰۴ استاتیکی بسازد (FR-018، SC-001).

## ۳. تست (دو صورت تأییدشده — یکی را انتخاب کنید)

```bash
# صورت رسمی هر گام (از داخل محدوده‌ی کد؛ همان معنای امروزیِ `python manage.py test`)
cd backend && ../.venv/bin/python manage.py test

# صورت از ریشه‌ی مخزن
.venv/bin/python backend/manage.py test backend/tests
```

⚠️ **تله‌ی صفر-تست**: اجرای `.venv/bin/python backend/manage.py test` از ریشه **بدون برچسب** نتیجه‌اش `Found 0 test(s)` و `NO TESTS RAN` است (Django از cwd کشف می‌کند، نه از محل `manage.py`). این «سبزِ کاذب» است و مبنای پذیرش نیست (SC-003، SC-011).

## ۴. بررسی‌های سلامت

```bash
.venv/bin/python backend/manage.py check                       # انتظار: no issues
.venv/bin/python backend/manage.py makemigrations --check --dry-run   # انتظار: No changes detected
```

## ۵. متغیرهای محیطی

| متغیر | پیش‌فرض جدید | توضیح |
|---|---|---|
| `TIKOTIME_DB` | `db/db.sqlite3` | مسیر جایگزین پایگاه‌داده (برای تست: `TIKOTIME_DB=/tmp/test.db`) — هرگز به داده‌ی واقعی دست نزنید |
| `DJANGO_DEBUG` | `1` | `0` هم حالت پشتیبانی‌شده است (استاتیک باید لود شود) |
| `DJANGO_SECRET_KEY` | کلید توسعه | بدون تغییر |

## ۶. محل فایل‌های تولیدشده توسط عملیات‌ها (پس از گام ۵)

| عملیات | محل خروجی | مسیر HTTP (بدون تغییر) |
|---|---|---|
| آپلود عکس | `db/images/` | `/data/images/<name>` |
| ساخت بکاپ | `db/backups/` | دانلود از `/api/backups/download/<fname>` |
| اکسپورت اکسل/CSV | `db/exports/` | `/export/<kind>.<fmt>` |
| پایگاه‌داده | `db/db.sqlite3` | — |
| css/js/فونت | `frontend/static/**` | `/static/<path>` |
| قالب‌ها | `frontend/templates/**` | — |

## ۷. کنترل نسخه

- `db/` (جانشین `data/`) و `.venv/` و همه‌ی `__pycache__/` نادیده گرفته می‌شوند.
- خط `staticfiles/` از `.gitignore` حذف می‌شود (پوشه هم پاک می‌شود).
- `git status` بعد از گام ۵ باید فقط تغییرات کد/مستندات را نشان بدهد و **هیچ** فایل داده‌ای نباید قابل commit باشد (FR-012).
