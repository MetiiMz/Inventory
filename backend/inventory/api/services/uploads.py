# -*- coding: utf-8 -*-
"""Image upload: validate and persist, return the stored filename."""

import base64
import datetime
import json
import os
import secrets
import stat
import time

from django.conf import settings

from inventory.dbhelpers import IMG_DIR, get_setting
from inventory.models import Product, Repair, Tracking
from inventory.utils import clean

from .common import ApiError


ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg"}


ICON_EXT = {".png", ".svg", ".ico", ".jpg", ".jpeg", ".webp"}


def _save_uploaded(kind, ext, content):
    """Write uploaded bytes under a unique name; returns (fname, error)."""
    allowed = ICON_EXT if kind == "icon" else ALLOWED_EXT
    if ext not in allowed:
        return None, "فرمت فایل پشتیبانی نمی‌شود"
    fname = ("icon_" if kind == "icon" else "img_") + \
        datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + \
        secrets.token_hex(4) + ext
    os.makedirs(settings.IMG_DIR, exist_ok=True)
    with open(os.path.join(str(settings.IMG_DIR), fname), "wb") as out:
        out.write(content)
    return fname, None


def save_upload(request) -> str:
    """Handle an image/icon upload from either transport and return the filename.

    Preferred path: JSON body ``{kind, name, data}`` with a base64 (or
    data-URI) payload.  Fallback: classic multipart form with a ``file``
    field.  Files are capped at 2 MB.
    """
    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads(request.body or b"{}")
        except Exception:
            raise ApiError(400, "بدنه‌ی درخواست نامعتبر است")
        kind = clean(payload.get("kind")) or "image"
        name = clean(payload.get("name")) or "file"
        data = payload.get("data") or ""
        if isinstance(data, str) and data.startswith("data:"):
            _, _, data = data.partition(",")
        try:
            content = base64.b64decode(data)
        except Exception:
            raise ApiError(400, "محتوای فایل قابل خواندن نیست")
        if not content:
            raise ApiError(400, "فایلی انتخاب نشده است")
        if len(content) > 2 * 1024 * 1024:
            raise ApiError(400, "حجم فایل باید کمتر از ۲ مگابایت باشد")
        fname, err = _save_uploaded(kind, os.path.splitext(name)[1].lower(), content)
        if err:
            raise ApiError(400, err)
        return fname

    f = request.FILES.get("file")
    kind = clean(request.POST.get("kind")) or "image"
    if not f or not f.name:
        raise ApiError(400, "فایلی انتخاب نشده است")
    fname, err = _save_uploaded(
        kind, os.path.splitext(f.name)[1].lower(), b"".join(f.chunks()))
    if err:
        raise ApiError(400, err)
    return fname


def cleanup_orphan_images(min_age_seconds=3600):
    """حذف تصاویر بلااستفاده و قدیمی‌تر از min_age_seconds از IMG_DIR.

    فقط فایل‌های عادی (نه پوشه، نه نماد/ symlink) داخل IMG_DIR در نظر گرفته
    می‌شوند و هرگز چیزی خارج از IMG_DIR لمس نمی‌شود. فایلی که توسط
    Product.image / Repair.image / Tracking.image ارجاع داده شده است یا برابر
    با تنظیمه‌ی site_icon است، حفظ می‌شود. فایلی جدیدتر از آستانه سِن (چون
    شاید در حال پر کردن فرم باز باشد) حذف نمی‌شود.

    Returns:
        int: تعداد فایل‌های حذف‌شده.
    """
    referenced = set()
    for model in (Product, Repair, Tracking):
        referenced.update(
            v
            for v in model.objects.exclude(image="").values_list(
                "image", flat=True
            )
            if v
        )
    site_icon = get_setting("site_icon", "")
    if site_icon:
        referenced.add(site_icon)

    removed = 0
    now = time.time()
    try:
        names = os.listdir(IMG_DIR)
    except OSError:
        return removed
    for name in names:
        path = os.path.join(IMG_DIR, name)
        try:
            st = os.lstat(path)
        except OSError:
            continue
        # فقط فایل‌های عادی — نه پوشه و نه نماد (symlink هرگز دنبال نمی‌شود)
        if not stat.S_ISREG(st.st_mode):
            continue
        if name in referenced:
            continue
        # اگر هنوز در حال پر کردن فرم است، لمس نمی‌شود
        if now - st.st_mtime < min_age_seconds:
            continue
        try:
            os.remove(path)
            removed += 1
        except OSError:
            pass
    return removed
