# -*- coding: utf-8 -*-
"""Order-tracking adapters: list/detail/bulk-delete over /api/tracking."""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from inventory.api import services
from inventory.utils import tracking_dict

from .common import _body, _ok, _fail, _guard


def api_tracking(request):
    """GET lists tracking records; POST creates one (wrapped in ``tracking``)."""
    if request.method == "POST":
        def run():
            tracking = services.create_tracking(_body(request))
            return _ok(tracking=tracking_dict(tracking))
        return _guard(run)

    rows = services.tracking_queryset(request.GET)
    return JsonResponse([tracking_dict(r) for r in rows], safe=False)



def api_tracking_detail(request, tid):
    """GET returns / PUT updates / DELETE destroys one tracking record."""
    from inventory.models import Tracking
    tracking = Tracking.objects.filter(id=tid).first()
    if tracking is None:
        return _fail("یافت نشد", 404)
    if request.method == "GET":
        return JsonResponse(tracking_dict(tracking), safe=False)
    if request.method == "PUT":
        def run():
            services.update_tracking(tracking, _body(request))
            tracking.refresh_from_db()
            return _ok(tracking=tracking_dict(tracking))
        return _guard(run)
    return _guard(lambda: (services.delete_tracking(tracking), _ok())[1])



@csrf_exempt
@require_POST
def api_tracking_bulk_delete(request):
    """POST /api/tracking/bulk-delete — ``{ids: [...]}`` → ``{deleted: n}``."""
    def run():
        deleted = services.bulk_delete_tracking(_body(request).get("ids"))
        return _ok(deleted=deleted)
    return _guard(run)

