# -*- coding: utf-8 -*-
"""Repair adapters: list/detail/bulk-delete/status over /api/repairs."""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from inventory.api import services
from inventory.api.services import ApiError
from inventory.utils import repair_dict

from .common import _body, _ok, _fail, _guard


def api_repairs(request):
    """GET lists repairs; POST creates one (wrapped in ``repair``)."""
    if request.method == "POST":
        def run():
            repair = services.create_repair(_body(request))
            return _ok(repair=repair_dict(repair))
        return _guard(run)

    rows = services.repair_queryset(request.GET)
    return JsonResponse([repair_dict(r) for r in rows], safe=False)



def api_repair_detail(request, rid):
    """GET returns / PUT updates / DELETE destroys one repair ticket."""
    from inventory.models import Repair
    repair = Repair.objects.filter(id=rid).first()
    if repair is None:
        return _fail("یافت نشد", 404)
    if request.method == "GET":
        return JsonResponse(repair_dict(repair), safe=False)
    if request.method == "PUT":
        def run():
            services.update_repair(repair, _body(request))
            repair.refresh_from_db()
            return _ok(repair=repair_dict(repair))
        return _guard(run)
    return _guard(lambda: (services.delete_repair(repair), _ok())[1])



@csrf_exempt
@require_POST
def api_repairs_bulk_delete(request):
    """POST /api/repairs/bulk-delete — ``{ids: [...]}`` → ``{deleted: n}``."""
    def run():
        deleted = services.bulk_delete_repairs(_body(request).get("ids"))
        return _ok(deleted=deleted)
    return _guard(run)



@csrf_exempt
@require_POST
def api_repair_status(request, rid):
    """POST /api/repairs/<id>/status — change status (+ return date)."""
    def run():
        from inventory.models import Repair
        repair = Repair.objects.filter(id=rid).first()
        if repair is None:
            raise ApiError(404, "یافت نشد")
        repair = services.set_repair_status(repair, _body(request))
        return _ok(repair=repair_dict(repair))
    return _guard(run)

