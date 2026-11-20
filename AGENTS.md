# AGENTS.md — TikoTime (نرم‌افزار انبار ساعت)

فایل تحویل (handoff) برای هر agent آینده که روی این مخزن کار می‌کند. هر واقعیتی در این فایل از خود مخزن استخراج شده است (git log، README.md، specs/، کد backend/inventory/ و تست‌ها) — چیزی اختراع نشده است.

--------------------------------------------------------------------------------
## ۱. چیست این برنامه؟
TikoTime یک برنامه وب محلی، تک‌کاربره، آفلاین برای مدیریت انبار، فروش، تعمیر و سفارش‌های فروشگاه ساعت است.
- پشته: Django 5.2 + Jinja2 (django-jinja env) + SQLite + vanilla JS
- رابط فارسی، راست‌به‌چپ (RTL)، تقویم شمسی (Jalali) سمت کلاینت و سرور
- تک‌کاربره: احراز هویت ندارد (local only); قبل از انتشار عمومی لاگین اضافه شود
- تنها قرارداد HTTP برنامه مسیرهای /api/* هستند (آداپتورهای نازک backend/inventory/api/compat/ روی لایه خدمات business)

--------------------------------------------------------------------------------
## ۲. اجرا و تست
اجرا (از ریشه پروژه):
    .venv/bin/python backend/manage.py runserver   # سپس http://127.0.0.1:8000
تست (دیتابیس موقت — دیتابیس واقعی در db/ دست نخورده می‌ماند):
    cd backend && TIKOTIME_DB=/tmp/x.sqlite3 .venv/bin/python manage.py test tests
تشخیص استاتیک Django:
    .venv/bin/python backend/manage.py check
    .venv/bin/python backend/manage.py makemigrations --check --dry-run
بررسی سینتکس جاوااسکریپت:
    node --check frontend/static/js/*.js
متغیر محیطی TIKOTIME_DB مسیر دیتابیس را overridden می‌کند (پیش‌فرض db/db.sqlite3).
SafeMediaTestRunner تصاویر و بکاپ‌ها را در دایرکتوری موقت محصور می‌کند؛ هرگز db/images یا db/backups را schreef نمی‌شود.
بررسی‌های مرورگر (E2E) قبلاً با Playwright روی یک دیتابیس موقت انجام شده و اسکریپت‌ها از مخزن حذف شده‌اند؛ هرگز علیه دیتابیس واقعی اجرا نشود.

--------------------------------------------------------------------------------
## ۳. قوانین معماری
- backend/inventory/api/services/ تک منبع حقیقت قوانین کسب‌وکار (source of truth); api/compat/ فقط آداپتورهای /api/* بدون منطق است.
- backend/inventory/views/pages.py رندرر صفحات HTML خفيف (page shells).
- هر مسیر در backend/tikotime/settings.py مشخص می‌شود (DATA_DIR=db، STATIC_DIR=frontend/static، TEMPLATES=frontend/templates).
- db/ (دیتابیس، تصاویر، بکاپ، صادرات) gitignore شده است و هرگز commit نمی‌شود.

--------------------------------------------------------------------------------
## ۴. قوانین دامنه (ضروری در هر فیچر جدید)
- sale_type (person/online) مستقل از payment_type است.
- payment_type: cash «تسویه کامل» / deposit «بیعانه» / credit «اعتباری».
- deposit یک 감사 Payment ایجاد می‌کند و در صفحه پرداخت‌ها نمایش داده می‌شود؛ credit و تسویه کامل هرگز رسید ایجاد نمی‌کنند.
- credit نیاز به provider (snappay|digipay|torob) + کد پیگیری با پیشوند S-/D-/T- و یکتاست.
- جابجایی مستقیم credit↔deposit رد می‌شود (credit↔cash مجاز است).
- کلید API deposit_amount = کل پرداخت شده تا کنون.
- ستون‌های پول FloatField holding whole toman; سود ممکن است منفی باشد.

--------------------------------------------------------------------------------
## ۵. تصاویر و بکاپ
- IMG_DIR + BACKUP_DIR در repo db/ هستند; بکاپ شامل تصاویر (<stem>.images.zip).
- آپلود پسوند + magic bytes را اعتبارسنجی می‌کند؛ SVG مجاز نیست.
- نقطه پایان تصاویر یتیم: /api/images/cleanup.

--------------------------------------------------------------------------------
## ۶.원에서 فرانت‌اند
- کمککارهای shared: detail-cards.js و dashboard-charts.js (initChart(cfg)).
- مودال جزئیات = هدر + کارت‌های تیل (یکسان در sold و calendar).
- نمودارها باید داخل منطقهِ plot بمانند، incl. سود منفی.
- هرگز تگ <script> بسته نشده باقی نماند.

--------------------------------------------------------------------------------
## ۷. تاریخچه فیچرها (جدیدترین اول)
- 2026-11-20 (25e5648) fix some bugs — اصلاحات کوچک شامل نمودار سود منفی (dashboard-charts.js)
- 2026-11-19 (d418794 / 6e6942a) redesigned detail modals (sold + calendar: sale, purchase, repair)
- 2026-11-14 (fcaae18) M2: Finish credit sale, fix payments, relabel cash→تسویه کامل — فروش اعتباری + فیلتر ارائه‌دهنده؛ حذف روش پرداخت (pos/card2card) از ثبت جدید (فقط bucket‌های legacy در payload قدیمی باقی مانده)
- 2026-11-10 (07c0f6d) suppliers — مدیریت فروشندگان در تنظیمات (list/add/delete)
- 2026-11-10 (bfa43d7) safe test runner — isolate IMG_DIR + suite-wide guard (L1)
- 2026-11-04 (41b9ea7) backups with images — بکاپ شامل <stem>.images.zip
- 2026-11-04 (d1d5f87 / 2b45f67) image lightbox / zoom
- 2026-10-03 (fe3ae2e) manual sale price (spec 002) — قیمت فروش دستی اجباری
- 2026-10-03 (3bd16dc) dashboard sales-by-channel chart — counts per month: person / online / credit
- 2026-10-03 (af09572) three-part layout refactor — db/ + backend/ + frontend/ + تک منبع مسیرها

--------------------------------------------------------------------------------
## ۸. تصمیمات ثبت‌شده / موردهای غیر-هدف
- هیچ DRF و نه /api/v1 (حذف شده در 2026-10-03).
- احراز هویت ندارد (local only).
- SameOriginMiddleware به جای csrf middleware.
- DEBUG پیش‌فرض 1 (روشن).
- پول float; مبالغ عدد صحیح تومان.
- تم liquid-glass و بسته‌بندی دسکتاپ لغو شده است.

--------------------------------------------------------------------------------
## ۹. چگونه فیچر اضافه شود (چک‌لیست)
۱. سرویس مربوطه و spec در specs/ را بخوانید.
۲. تست مربوطه اضافه کنید.
۳. کل مجموعه تست را روی دیتابیس موقت اجرا کنید (TIKOTIME_DB=/tmp/…).
۴. در مرورگر واقعی روی دیتابیس موقت تایید کنید (هرگز دیتابیس واقعی db/).
۵. این فایل را در همان تغییر به‌روز کنید (اضافه کردن ردیف تاریخچه در بخش ۷).
