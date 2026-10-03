"""Jinja2 environment for Django — helpers identical to the legacy Flask app."""
import os

from django.conf import settings
from django.middleware.csrf import get_token
from django.urls import reverse

from inventory.jalali import MONTH_NAMES, WEEKDAY_NAMES, today_jalali
from inventory.utils import fa_date, fa_money, fa_num

STATUS_FA = {
    "received": "دریافت شده",
    "in_progress": "در حال تعمیر",
    "waiting_parts": "انتظار قطعه",
    "done": "آماده تحویل",
    "delivered": "تحویل شده",
}
STATUS_COLOR = {
    "received": "blue", "in_progress": "amber", "waiting_parts": "purple",
    "done": "green", "delivered": "gray",
}
TRACKING_STATUS_FA = {
    "new": "جدید", "ordered": "سفارش داده شد", "found": "پیدا شد",
    "delivered": "تحویل شد", "cancelled": "لغو شد",
}
TRACKING_STATUS_COLOR = {
    "new": "blue", "ordered": "amber", "found": "green",
    "delivered": "gray", "cancelled": "red",
}


def static_v(path):
    """آدرس static با نسخه‌ی mtime فایل — کش مرورگر را با هر تغییر می‌شکند.

    پس از هر تغییر در CSS/JS، ?v=mtime آپدیت می‌شود و مرورگر نسخه‌ی
    تازه را می‌گیرد — بدون هیچ گام جمع‌آوری یا وایرالینگ.
    """
    fs = str(settings.STATIC_DIR / path)
    try:
        v = int(os.path.getmtime(fs))
    except OSError:
        return settings.STATIC_URL + path
    return f"{settings.STATIC_URL}{path}?v={v}"


def environment(**options):
    env = options["environment"]() if callable(options.get("environment")) else None
    if env is None:
        from jinja2 import Environment
        env = Environment(**options)
    env.globals.update(
        STATUS_FA=STATUS_FA,
        STATUS_COLOR=STATUS_COLOR,
        TRACKING_STATUS_FA=TRACKING_STATUS_FA,
        TRACKING_STATUS_COLOR=TRACKING_STATUS_COLOR,
        MONTH_NAMES=MONTH_NAMES,
        WEEKDAY_NAMES=WEEKDAY_NAMES,
        fa_date=fa_date,
        fa_money=fa_money,
        fa_num=fa_num,
        today_jalali=today_jalali,
        static=settings.STATIC_URL,
        static_v=static_v,
        media=settings.MEDIA_URL,
        csrf_token=lambda request: get_token(request),
        url=reverse,
    )
    env.filters["fa_money"] = fa_money
    env.filters["fa_num"] = fa_num
    env.filters["fa_date"] = fa_date
    return env
