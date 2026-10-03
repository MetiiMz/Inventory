# -*- coding: utf-8 -*-
"""Product domain: query, create/update/delete, bulk-delete, validation."""

from django.db import transaction
from django.db.models import Q, QuerySet
from django.db.models.functions import Lower

from inventory.jalali import parse_jalali_date
from inventory.models import Product
from inventory.utils import clean, remove_image, to_float

from .common import (
    ApiError, _clean_ids, _merge_partial, _parse_iso_or_raise,
)


_PRODUCT_SORT = {
    "office_code": "office_code", "website_code": "website_code", "name": "name",
    "brand": "brand", "supplier": "supplier", "purchase_date": "purchase_date",
    "purchase_price": "purchase_price",
    "available": "available", "created_at": "id",
}


_PRODUCT_NOCASE = {"office_code", "website_code", "name", "brand", "supplier"}


_PRODUCT_WRITE_FIELDS = (
    "name", "reference", "office_code", "website_code", "brand",
    "purchase_price", "supplier", "purchase_date",
    "purchase_type", "notes", "image",
)


def product_queryset(params) -> QuerySet:
    """Filtered/ordered product list.

    Supported query parameters (identical in both API layers):
    ``q`` (name/reference/codes/brand/supplier), ``brand``,
    ``status`` = ``available`` | ``unavailable``, ``date_from``/``date_to``
    (Jalali or ISO, bounds for ``purchase_date``), ``sort`` + ``dir``.
    """
    q = clean(params.get("q", ""))
    brand = clean(params.get("brand", ""))
    status = clean(params.get("status", ""))
    date_from = clean(params.get("date_from", ""))
    date_to = clean(params.get("date_to", ""))
    sort = clean(params.get("sort", "")) or "office_code"
    direction = clean(params.get("dir", "")).lower() or "asc"

    qs = Product.objects.all()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(reference__icontains=q)
            | Q(office_code__icontains=q) | Q(website_code__icontains=q)
            | Q(brand__icontains=q) | Q(supplier__icontains=q)
        )
    if brand:
        qs = qs.filter(brand=brand)
    if status == "available":
        qs = qs.filter(available=True)
    elif status == "unavailable":
        qs = qs.filter(available=False)
    if date_from:
        parsed = parse_jalali_date(date_from)
        if parsed:
            qs = qs.filter(purchase_date__gte=parsed)
    if date_to:
        parsed = parse_jalali_date(date_to)
        if parsed:
            qs = qs.filter(purchase_date__lte=parsed)

    col = _PRODUCT_SORT.get(sort, "office_code")
    desc = direction == "desc"
    if col in _PRODUCT_NOCASE:  # legacy COLLATE NOCASE equivalent
        func = Lower(col)
        order = [func.desc() if desc else func.asc()]
    else:
        order = ["-" + col if desc else col]
    return qs.order_by(*order, "-id")


def _product_values(payload):
    """Validate product fields; returns the clean dict (raises ApiError)."""
    name = clean(payload.get("name"))
    office_code = clean(payload.get("office_code"))
    website_code = clean(payload.get("website_code"))
    if not name:
        raise ApiError(400, "نام ساعت الزامی است")
    if not office_code:
        raise ApiError(400, "کد دفتر فروشگاه الزامی است")
    if not website_code:
        raise ApiError(400, "کد انبار سایت الزامی است")

    purchase_date = clean(payload.get("purchase_date"))
    if purchase_date:
        purchase_date = _parse_iso_or_raise(
            purchase_date, "تاریخ خرید معتبر نیست (نمونه: ۱۴۰۳/۰۵/۱۲)")
    else:
        purchase_date = ""

    return {
        "name": name,
        "reference": clean(payload.get("reference")),
        "office_code": office_code,
        "website_code": website_code,
        "brand": clean(payload.get("brand")),
        "purchase_price": max(0.0, to_float(payload.get("purchase_price"))),
        # one row = one watch; it becomes unavailable once sold
        "available": True,
        "supplier": clean(payload.get("supplier")),
        "purchase_date": purchase_date,
        "notes": clean(payload.get("notes")),
        "image": clean(payload.get("image")),
    }


def _check_duplicate_code(office_code, website_code, exclude_id=None):
    """Reject duplicate office/site codes (case-insensitive), legacy message."""
    cond = Q(office_code__iexact=office_code) | Q(website_code__iexact=website_code)
    if exclude_id:
        cond &= ~Q(id=exclude_id)
    dup = Product.objects.filter(cond).first()
    if not dup:
        return None
    if dup.office_code.lower() == office_code.lower():
        return f"کد دفتر فروشگاه «{office_code}» قبلاً برای ساعت «{dup.name}» ثبت شده است"
    return f"کد انبار سایت «{website_code}» قبلاً برای ساعت «{dup.name}» ثبت شده است"


def create_product(payload) -> Product:
    """Create a product (codes must be unique, stock starts as available)."""
    values = _product_values(payload)
    dup = _check_duplicate_code(values["office_code"], values["website_code"])
    if dup:
        raise ApiError(400, dup)
    with transaction.atomic():
        return Product.objects.create(**values)


def update_product(product: Product, payload, partial=False) -> Product:
    """Update a product.

    The stock flag (``available``) is never touched here — editing a sold
    watch must not flip it back to in-stock (a historic bug).
    """
    if partial:
        payload = _merge_partial(payload, product, _PRODUCT_WRITE_FIELDS)
    values = _product_values(payload)
    dup = _check_duplicate_code(values["office_code"], values["website_code"],
                                exclude_id=product.id)
    if dup:
        raise ApiError(400, dup)
    values.pop("available", None)
    old_image = product.image
    for key, value in values.items():
        setattr(product, key, value)
    product.save()
    if old_image and old_image != values["image"]:
        remove_image(old_image)
    return product


def delete_product(product: Product) -> None:
    """Delete a product and its image file."""
    with transaction.atomic():
        product.delete()
    if product.image:
        remove_image(product.image)


def bulk_delete_products(raw_ids) -> int:
    """Delete many products at once; returns the number deleted."""
    ids = _clean_ids(raw_ids)
    if not ids:
        raise ApiError(400, "موردی انتخاب نشده است")
    images = list(
        Product.objects.filter(id__in=ids)
        .exclude(image="").values_list("image", flat=True)
    )
    with transaction.atomic():
        Product.objects.filter(id__in=ids).delete()
    for img in images:
        remove_image(img)
    return len(ids)
