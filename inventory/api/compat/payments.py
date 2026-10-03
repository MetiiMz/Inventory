# -*- coding: utf-8 -*-
"""Payment adapters: list/detail/add/settle/bulk-delete over /api/payments."""

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from inventory.api import services
from inventory.api.services import ApiError

from .common import _body, _ok, _fail, _guard


def api_payments(request):
    """GET lists payments with a summary; POST creates a record."""
    if request.method == "POST":
        def run():
            payment = services.create_payment(_body(request))
            from inventory.utils import payment_dict
            return _ok(payment=payment_dict(payment))
        return _guard(run)

    from inventory.utils import payment_dict
    rows = services.payment_queryset(request.GET)
    items = [payment_dict(p) for p in rows]
    summary = {
        "count": len(items),
        "total": sum(i["total_amount"] for i in items),
        "paid": sum(i["paid_amount"] for i in items),
        "remaining": sum(i["remaining"] for i in items),
    }
    return _ok(items=items, summary=summary)



def api_payment_detail(request, payid):
    """PUT updates / DELETE destroys one payment record."""
    from inventory.models import Payment
    from inventory.utils import payment_dict
    payment = Payment.objects.filter(id=payid).first()
    if not payment:
        return _fail("یافت نشد", 404)
    if request.method == "PUT":
        def run():
            services.update_payment(payment, _body(request))
            payment.refresh_from_db()
            return _ok(payment=payment_dict(payment))
        return _guard(run)
    if request.method == "DELETE":
        return _guard(lambda: (services.delete_payment(payment), _ok())[1])
    return _fail("متد پشتیبانی نمی‌شود", 405)



@csrf_exempt
@require_POST
def api_payment_add(request, payid):
    """POST /api/payments/<id>/add — pay an installment amount."""
    def run():
        from inventory.models import Payment
        from inventory.utils import payment_dict
        payment = Payment.objects.filter(id=payid).first()
        if not payment:
            raise ApiError(404, "یافت نشد")
        payment = services.add_payment(payment, _body(request))
        return _ok(payment=payment_dict(payment))
    return _guard(run)



@csrf_exempt
@require_POST
def api_payment_settle_full(request, payid):
    """POST /api/payments/<id>/settle-full — settle the whole balance."""
    def run():
        from inventory.models import Payment
        payment = Payment.objects.filter(id=payid).first()
        if not payment:
            raise ApiError(404, "یافت نشد")
        services.settle_payment_full(payment)
        return _ok()
    return _guard(run)



@csrf_exempt
@require_POST
def api_payments_bulk_delete(request):
    """POST /api/payments/bulk-delete — ``{ids: [...]}`` → ``{deleted: n}``."""
    def run():
        deleted = services.bulk_delete_payments(_body(request).get("ids"))
        return _ok(deleted=deleted)
    return _guard(run)

