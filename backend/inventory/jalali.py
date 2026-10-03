# -*- coding: utf-8 -*-
"""تبدیل تاریخ شمسی (جلالی) به میلادی و برعکس — بدون وابستگی خارجی.

الگوریتم استاندارد و آزموده‌ی jdf (تقویم دقیق).
"""

import datetime

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"

MONTH_NAMES = [
    "فروردین", "اردیبهشت", "خرداد",
    "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر",
    "دی", "بهمن", "اسفند",
]

WEEKDAY_NAMES = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یکشنبه"]


def gregorian_to_jalali(gy, gm, gd):
    """میلادی → جلالی. خروجی: (jy, jm, jd)"""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100)
            + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1])
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def jalali_to_gregorian(jy, jm, jd):
    """جلالی → میلادی. خروجی: (gy, gm, gd)"""
    jy += 1595
    days = (-355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd)
    days += (jm - 1) * 31 if jm < 7 else ((jm - 7) * 30) + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)
    sal_a = [0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 13 and gd > sal_a[gm]:
        gd -= sal_a[gm]
        gm += 1
    return gy, gm, gd


def is_jalali_leap(jy):
    """سال کبیسه‌ی شمسی — با رفت‌وبرگشت تبدیل (سازگار با الگوریتم تبدیل)."""
    gy, gm, gd = jalali_to_gregorian(jy, 12, 30)
    jy2, jm2, jd2 = gregorian_to_jalali(gy, gm, gd)
    return (jy2, jm2, jd2) == (jy, 12, 30)


def jalali_month_length(jy, jm):
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    return 30 if is_jalali_leap(jy) else 29


def today_jalali():
    d = datetime.date.today()
    return gregorian_to_jalali(d.year, d.month, d.day)


def today_iso():
    return datetime.date.today().isoformat()


def fa_num(value):
    """تبدیل رقم‌های لاتین به فارسی."""
    return str(value).translate(str.maketrans("0123456789", PERSIAN_DIGITS))


def parse_jalali_date(text):
    """
    رشته‌ی تاریخ را می‌خواند و تاریخ میلادی ISO برمی‌گرداند.
    فرمت‌های پذیرفته‌شده:
      - ۱۴۰۳/۰۵/۱۲ یا 1403-5-12 یا 14030512  (شمسی)
      - 2024-08-12 (میلادی ISO)
    اگر نتوانست بخواند None برمی‌گرداند.
    """
    if text is None:
        return None
    s = str(text).strip()
    # ارقام فارسی (U+06F0) و عربی (U+0660) هر دو به لاتین
    s = s.translate(str.maketrans(PERSIAN_DIGITS + "٠١٢٣٤٥٦٧٨٩", "0123456789" * 2))
    if not s:
        return None
    s = s.replace("٫", "/").replace("-", "/").replace(".", "/").replace(" ", "/")
    s = s.strip("/")
    parts = [p for p in s.split("/") if p != ""]
    try:
        if len(parts) == 3:
            a, b, c = (int(p) for p in parts)
            if a > 1900:  # میلادی
                d = datetime.date(a, b, c)
            elif a > 1000:  # شمسی
                if not (1 <= b <= 12) or not (1 <= c <= 31):
                    return None
                gy, gm, gd = jalali_to_gregorian(a, b, c)
                d = datetime.date(gy, gm, gd)
            else:
                return None
            return d.isoformat()
        if len(parts) == 1 and len(parts[0]) == 8:
            n = int(parts[0])
            if n > 19000000:  # میلادی 20240812
                d = datetime.date(n // 10000, (n // 100) % 100, n % 100)
            else:  # شمسی 14030512
                gy, gm, gd = jalali_to_gregorian(n // 10000, (n // 100) % 100, n % 100)
                d = datetime.date(gy, gm, gd)
            return d.isoformat()
    except (ValueError, TypeError):
        return None
    return None
