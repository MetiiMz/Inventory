# -*- coding: utf-8 -*-
"""Shared legacy-shape helpers: body parsing, ok/fail envelopes, ApiError guard, attachment."""

import json

from django.http import FileResponse, JsonResponse

from inventory.api.services import ApiError


def _body(request):
    """Parse the JSON request body (empty dict on any parse failure)."""
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return {}



def _ok(**data):
    """Legacy success envelope: ``{ok: true, ...data}``."""
    data.setdefault("ok", True)
    return JsonResponse(data)



def _fail(error, status=400):
    """Legacy error envelope: ``{ok: false, error: <persian message>}``."""
    return JsonResponse({"ok": False, "error": error}, status=status)



def _guard(fn):
    """Run ``fn(request, ...)`` and render :class:`ApiError` in legacy shape."""
    try:
        return fn()
    except ApiError as exc:
        return _fail(exc.message, exc.status_code)



def _attachment(path, name, mimetype):
    """File download response with UTF-8 safe Content-Disposition."""
    from urllib.parse import quote
    resp = FileResponse(open(path, "rb"), content_type=mimetype)
    quoted = quote(name)
    resp["Content-Disposition"] = (
        f"attachment; filename=\"{quoted}\"; filename*=UTF-8''{quoted}")
    return resp

