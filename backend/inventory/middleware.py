# -*- coding: utf-8 -*-
"""Project middleware — same-origin guard for the token-less legacy API."""

from urllib.parse import urlsplit

from django.http import JsonResponse


class SameOriginMiddleware:
    """Reject state-changing requests whose ``Origin`` is a different site.

    The legacy ``/api/*`` contract carries no CSRF tokens (the views are
    ``csrf_exempt``), so this check is the defence against another web page
    open in the browser driving the app at ``localhost``. Behaviour:

    * only POST/PUT/PATCH/DELETE are guarded (GET/HEAD/OPTIONS are safe);
    * no ``Origin`` header (curl, older browsers) → passes through;
    * an ``Origin`` whose host:port matches the request host → same-origin,
      the app's own ``fetch`` calls keep working.
    """

    UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in self.UNSAFE_METHODS:
            origin = request.headers.get("Origin")
            if origin:
                origin_host = urlsplit(origin).netloc.lower()
                if origin_host != request.get_host().lower():
                    return JsonResponse(
                        {"ok": False, "error": "درخواست بین‌دامنه‌ای مجاز نیست"},
                        status=403,
                    )
        return self.get_response(request)
