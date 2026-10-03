# -*- coding: utf-8 -*-
"""Image adapters: upload and serve image files."""

import mimetypes
import os

from django.conf import settings
from django.http import FileResponse
from django.views.decorators.csrf import csrf_exempt

from inventory.api import services

from .common import _ok, _fail, _guard


@csrf_exempt
def api_upload(request):
    """POST /api/upload — image upload (JSON base64 or multipart) → ``{path}``."""
    return _guard(lambda: _ok(path=services.save_upload(request)))



def serve_image(request, fname):
    """GET /data/images/<name> — serve an uploaded image with caching."""
    safe = os.path.basename(fname)
    path = os.path.join(str(settings.IMG_DIR), safe)
    if not os.path.isfile(path):
        return _fail("یافت نشد", 404)
    ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
    resp = FileResponse(open(path, "rb"), content_type=ctype)
    resp["Cache-Control"] = "public, max-age=604800"
    return resp

