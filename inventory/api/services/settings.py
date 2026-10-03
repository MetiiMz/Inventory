# -*- coding: utf-8 -*-
"""Brands and store settings: brand CRUD, site settings, site icon."""

from inventory.dbhelpers import (
    add_brand, delete_brand, get_setting, set_setting,
)
from inventory.utils import clean

from .common import ApiError


def brands_list():
    """All brand names, alphabetically."""
    from inventory.dbhelpers import get_brands
    return get_brands()


def brands_add(payload):
    """Add a brand; raises with the legacy message on duplicates."""
    good, err = add_brand((payload or {}).get("name"))
    if not good:
        raise ApiError(400, err)


def brands_delete(payload):
    """Delete a brand by name."""
    delete_brand((payload or {}).get("name"))


def site_settings() -> dict:
    """Store settings as a dict (the settings page's GET payload)."""
    return {
        "store_name": get_setting("store_name", "") or "Tick O Time",
        "store_phone": get_setting("store_phone", ""),
        "store_address": get_setting("store_address", ""),
        "currency": get_setting("currency", "تومان"),
        "site_icon": get_setting("site_icon", ""),
    }


def save_settings(payload):
    """Persist the whitelisted store-setting keys present in the payload."""
    for key in ("store_name", "store_phone", "store_address", "currency"):
        if key in (payload or {}):
            set_setting(key, clean(payload.get(key)))


def set_site_icon(icon) -> str:
    """Store the site icon filename; removes the previous icon file."""
    from inventory.utils import remove_image
    old = get_setting("site_icon", "")
    icon = clean(icon)
    if icon and icon != old:
        remove_image(old)
    set_setting("site_icon", icon)
    return icon
