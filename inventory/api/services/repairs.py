# -*- coding: utf-8 -*-
"""Repair domain: query, CRUD, status flow and bulk-delete."""

from django.db import transaction
from django.db.models import Q, QuerySet

from inventory.jalali import today_iso
from inventory.models import Repair
from inventory.utils import STATUS_FA, clean, remove_image, to_float

from .common import (
    ApiError, _clean_ids, _merge_partial, _parse_iso_or_raise,
)


_REPAIR_WRITE_FIELDS = (
    "watch_name", "watch_code", "issue", "delivery_date", "return_date",
    "customer_name", "customer_phone", "is_warranty", "status",
    "repair_price", "image", "notes",
)


def repair_queryset(params) -> QuerySet:
    """Filtered repair list. Parameters: ``status``, ``q``."""
    status = clean(params.get("status", ""))
    q = clean(params.get("q", ""))
    qs = Repair.objects.all()
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(watch_name__icontains=q) | Q(watch_code__icontains=q)
            | Q(customer_name__icontains=q) | Q(customer_phone__icontains=q)
        )
    return qs.order_by("-id")


def _repair_values(payload):
    """Validate repair fields (delivery date defaults to today)."""
    watch_name = clean(payload.get("watch_name"))
    if not watch_name:
        raise ApiError(400, "نام ساعت الزامی است")
    customer_phone = clean(payload.get("customer_phone"))
    if customer_phone and not customer_phone.replace("+", "").replace(" ", "").isdigit():
        raise ApiError(400, "شماره تماس معتبر نیست")
    delivery_date = clean(payload.get("delivery_date"))
    if delivery_date:
        delivery_date = _parse_iso_or_raise(delivery_date, "تاریخ تحویل معتبر نیست")
    else:
        delivery_date = today_iso()
    return_date = clean(payload.get("return_date"))
    if return_date:
        return_date = _parse_iso_or_raise(return_date, "تاریخ بازگشت معتبر نیست")
    else:
        return_date = ""
    status = clean(payload.get("status")) or "received"
    if status not in STATUS_FA:
        status = "received"
    return {
        "watch_name": watch_name,
        "watch_code": clean(payload.get("watch_code")),
        "issue": clean(payload.get("issue")),
        "delivery_date": delivery_date,
        "return_date": return_date,
        "customer_name": clean(payload.get("customer_name")),
        "customer_phone": customer_phone,
        "is_warranty": 1 if payload.get("is_warranty") else 0,
        "status": status,
        "repair_price": max(0.0, to_float(payload.get("repair_price"))),
        "image": clean(payload.get("image")),
        "notes": clean(payload.get("notes")),
    }


def create_repair(payload) -> Repair:
    """Create a repair ticket."""
    with transaction.atomic():
        return Repair.objects.create(**_repair_values(payload))


def update_repair(repair: Repair, payload, partial=False) -> Repair:
    """Update a repair ticket (image housekeeping included)."""
    if partial:
        payload = _merge_partial(payload, repair, _REPAIR_WRITE_FIELDS)
    values = _repair_values(payload)
    old_image = repair.image
    for key, value in values.items():
        setattr(repair, key, value)
    repair.save()
    if old_image and old_image != values["image"]:
        remove_image(old_image)
    return repair


def delete_repair(repair: Repair) -> None:
    """Delete a repair ticket and its image file."""
    with transaction.atomic():
        repair.delete()
    if repair.image:
        remove_image(repair.image)


def bulk_delete_repairs(raw_ids) -> int:
    """Bulk-delete repair tickets; returns the number deleted."""
    ids = _clean_ids(raw_ids)
    if not ids:
        raise ApiError(400, "موردی انتخاب نشده است")
    images = list(
        Repair.objects.filter(id__in=ids)
        .exclude(image="").values_list("image", flat=True)
    )
    with transaction.atomic():
        Repair.objects.filter(id__in=ids).delete()
    for img in images:
        remove_image(img)
    return len(ids)


def set_repair_status(repair: Repair, payload) -> Repair:
    """Change a repair's status; ``delivered`` stamps ``return_date``."""
    status = clean(payload.get("status"))
    if status not in STATUS_FA:
        raise ApiError(400, "وضعیت نامعتبر است")
    return_date = clean(payload.get("return_date"))
    if return_date:
        parsed = _parse_iso_or_raise(return_date, "تاریخ بازگشت معتبر نیست")
    elif status == "delivered":
        parsed = today_iso()
    else:
        parsed = ""
    repair.status = status
    if parsed:
        repair.return_date = parsed
    repair.save()
    return repair
