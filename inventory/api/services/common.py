# -*- coding: utf-8 -*-
"""Shared business-logic primitives: ApiError and small helpers."""

from inventory.jalali import parse_jalali_date
from inventory.utils import to_int


class ApiError(Exception):
    """A business-rule violation.

    Raised by every service function.  ``status_code`` is the HTTP status
    the API layers should return and ``message`` is a human-readable
    Persian error message (or a list of messages for the Excel importer).
    """

    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _clean_ids(raw_ids):
    """Coerce a raw ``ids`` payload into a list of positive ints."""
    return [to_int(i) for i in (raw_ids or []) if to_int(i)]


def _merge_partial(payload, obj, fields):
    """Fill keys missing from a PATCH payload with the object's current values.

    PUT handlers always receive the full form, so legacy behaviour is
    "replace".  For PATCH (partial update) we pre-merge the instance's
    current values so that omitted fields are preserved instead of wiped.
    """
    payload = dict(payload or {})
    for field in fields:
        if field not in payload:
            payload[field] = getattr(obj, field)
    return payload


def _parse_iso_or_raise(text, message):
    """Parse a Jalali/ISO date string; raise ``ApiError`` when invalid."""
    parsed = parse_jalali_date(text)
    if not parsed:
        raise ApiError(400, message)
    return parsed
