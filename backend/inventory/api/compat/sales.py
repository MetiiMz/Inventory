# -*- coding: utf-8 -*-
"""Sale adapters: list/detail/bulk-delete over the legacy /api/sales contract."""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from inventory.api import services
from inventory.utils import sale_dict

from .common import _body, _ok, _fail, _guard


def api_sales(request):
    """GET lists sales with a summary; POST creates a sale."""
    if request.method == "POST":
        def run():
            sale = services.create_sale(_body(request))
            return _ok(sale=sale_dict(sale, sale.product))
        return _guard(run)

    if request.GET.get("next_code"):
        return JsonResponse(
            {"next_invoice_code": services.next_invoice_code()})

    rows = list(services.sale_queryset(request.GET)[:500])
    items = [sale_dict(s) for s in rows]
    summary = {
        "count": len(items),
        "total_sale": sum(x.get("sale_price") or 0 for x in items),
        "total_profit": sum(x.get("profit") or 0 for x in items),
    }
    return JsonResponse({"items": items, "summary": summary})



def api_sale_detail(request, sid):
    """GET returns / PUT updates / DELETE destroys one sale."""
    from inventory.models import Sale
    sale = Sale.objects.filter(id=sid).select_related("product").first()
    if sale is None:
        return _fail("فروش یافت نشد", 404)
    if request.method == "GET":
        return JsonResponse({"ok": True, "sale": sale_dict(sale)})
    if request.method == "PUT":
        def run():
            services.update_sale(sale, _body(request))
            sale.refresh_from_db()
            return _ok(sale=sale_dict(sale, sale.product))
        return _guard(run)
    return _guard(lambda: (services.delete_sale(sale), _ok())[1])



@csrf_exempt
@require_POST
def api_sales_bulk_delete(request):
    """POST /api/sales/bulk-delete — ``{ids: [...]}`` → ``{deleted: n}``."""
    def run():
        deleted = services.bulk_delete_sales(_body(request).get("ids"))
        return _ok(deleted=deleted)
    return _guard(run)

