# -*- coding: utf-8 -*-
"""Order-tracking domain: query, CRUD and bulk-delete."""

from django.db import transaction
from django.db.models import Q, QuerySet

from inventory.models import Tracking
from inventory.utils import (
    TRACKING_STATUS_FA, clean, remove_image, to_float,
)

from .common import ApiError, _clean_ids, _merge_partial


_TRACKING_WRITE_FIELDS = (
    "item_name", "item_code", "customer_name", "customer_phone",
    "price", "status", "notes", "image",
)


def tracking_queryset(params) -> QuerySet:
    """Filtered tracking list. Parameters: ``status``, ``q``."""
    status = clean(params.get("status", ""))
    q = clean(params.get("q", ""))
    qs = Tracking.objects.all()
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(item_name__icontains=q) | Q(item_code__icontains=q)
            | Q(customer_name__icontains=q) | Q(customer_phone__icontains=q)
        )
    return qs.order_by("-id")


def _tracking_values(payload):
    """Validate tracking fields (item name is mandatory)."""
    item_name = clean(payload.get("item_name"))
    if not item_name:
        raise ApiError(400, "نام ساعت یا قطعه الزامی است")
    status = clean(payload.get("status")) or "new"
    if status not in TRACKING_STATUS_FA:
        status = "new"
    return {
        "item_name": item_name,
        "item_code": clean(payload.get("item_code")),
        "customer_name": clean(payload.get("customer_name")),
        "customer_phone": clean(payload.get("customer_phone")),
        "price": max(0.0, to_float(payload.get("price"))),
        "status": status,
        "notes": clean(payload.get("notes")),
        "image": clean(payload.get("image")),
    }


def create_tracking(payload) -> Tracking:
    """Create an order-tracking record."""
    with transaction.atomic():
        return Tracking.objects.create(**_tracking_values(payload))


def update_tracking(tracking: Tracking, payload, partial=False) -> Tracking:
    """Update an order-tracking record (image housekeeping included)."""
    if partial:
        payload = _merge_partial(payload, tracking, _TRACKING_WRITE_FIELDS)
    values = _tracking_values(payload)
    old_image = tracking.image
    for key, value in values.items():
        setattr(tracking, key, value)
    tracking.save()
    if old_image and old_image != values["image"]:
        remove_image(old_image)
    return tracking


def delete_tracking(tracking: Tracking) -> None:
    """Delete an order-tracking record and its image file."""
    with transaction.atomic():
        tracking.delete()
    if tracking.image:
        remove_image(tracking.image)


def bulk_delete_tracking(raw_ids) -> int:
    """Bulk-delete tracking records; returns the number deleted."""
    ids = _clean_ids(raw_ids)
    if not ids:
        raise ApiError(400, "موردی انتخاب نشده است")
    images = list(
        Tracking.objects.filter(id__in=ids)
        .exclude(image="").values_list("image", flat=True)
    )
    with transaction.atomic():
        Tracking.objects.filter(id__in=ids).delete()
    for img in images:
        remove_image(img)
    return len(ids)
