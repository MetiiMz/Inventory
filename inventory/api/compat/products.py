# -*- coding: utf-8 -*-
"""Product adapters: list/detail/bulk-delete over the legacy /api/products contract."""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from inventory.api import services
from inventory.utils import product_dict

from .common import _body, _ok, _fail, _guard


def api_products(request):
    """GET lists products; POST creates one (wrapped in ``product``)."""
    if request.method == "POST":
        def run():
            product = services.create_product(_body(request))
            return _ok(product=product_dict(product))
        return _guard(run)

    rows = services.product_queryset(request.GET)
    return JsonResponse([product_dict(r) for r in rows], safe=False)



def api_product_detail(request, pid):
    """GET returns / PUT updates / DELETE destroys one product."""
    from inventory.models import Product
    product = Product.objects.filter(id=pid).first()
    if product is None:
        return _fail("محصول یافت نشد", 404)
    if request.method == "GET":
        return JsonResponse(product_dict(product), safe=False)
    if request.method == "PUT":
        def run():
            services.update_product(product, _body(request))
            product.refresh_from_db()
            return _ok(product=product_dict(product))
        return _guard(run)
    return _guard(lambda: (services.delete_product(product), _ok())[1])



@csrf_exempt
@require_POST
def api_products_bulk_delete(request):
    """POST /api/products/bulk-delete — ``{ids: [...]}`` → ``{deleted: n}``."""
    def run():
        deleted = services.bulk_delete_products(_body(request).get("ids"))
        return _ok(deleted=deleted)
    return _guard(run)

