# -*- coding: utf-8 -*-
"""Image adapters: upload and serve image files."""

import mimetypes
import os

from django.conf import settings
from django.http import FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from inventory.api import services

from .common import _ok, _fail, _guard


@csrf_exempt
def api_upload(request):
    """POST /api/upload — image upload (JSON base64 or multipart) → ``{path}``."""
    return _guard(lambda: _ok(path=services.save_upload(request)))


@csrf_exempt
@require_POST
def api_images_cleanup(request):
    """POST /api/images/cleanup — remove unreferenced old images → ``{removed}``."""
    def run():
        removed = services.cleanup_orphan_images()
        return _ok(removed=removed)
    return _guard(run)



def serve_image(request, fname):
    """GET /data/images/<name> — serve an uploaded image with caching.

    Existing SVG files already stored keep being served (nothing is deleted),
    but every response carries sniffing/sandbox hardening headers so a
    user-uploaded file can never be executed as active content in the browser.
    """
    safe = os.path.basename(fname)
    path = os.path.join(str(settings.IMG_DIR), safe)
    if not os.path.isfile(path):
        return _fail("یافت نشد", 404)
    ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
    resp = FileResponse(open(path, "rb"), content_type=ctype)
    resp["Cache-Control"] = "public, max-age=604800"
    resp["X-Content-Type-Options"] = "nosniff"
    resp["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; sandbox")
    return resp

