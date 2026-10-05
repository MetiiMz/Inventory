# -*- coding: utf-8 -*-
"""Ledger API adapters: /api/ledger/* (legacy-shape envelopes, no logic)."""

from django.views.decorators.csrf import csrf_exempt

from inventory.api import services
from inventory.utils import ledger_invoice_dict, ledger_supplier_dict

from .common import _body, _fail, _guard, _ok


def _bad_method():
    return _fail("متد پشتیبانی نمی‌شود", 405)


@csrf_exempt
def api_ledger_suppliers(request):
    """GET lists suppliers; POST creates one (``{name}``)."""
    if request.method == "POST":
        return _guard(lambda: _ok(supplier=ledger_supplier_dict(
            services.create_supplier(_body(request)))))
    if request.method == "GET":
        return _guard(lambda: _ok(items=[
            ledger_supplier_dict(s)
            for s in services.ledger_suppliers_list()]))
    return _bad_method()


@csrf_exempt
def api_ledger_supplier_detail(request, supplier_id):
    """PUT renames the supplier; DELETE removes it with full cascade."""
    if request.method == "PUT":
        return _guard(lambda: _ok(supplier=ledger_supplier_dict(
            services.rename_supplier(
                services.ledger_supplier_or_404(supplier_id),
                _body(request)))))
    if request.method == "DELETE":
        return _guard(lambda: (services.delete_supplier(
            services.ledger_supplier_or_404(supplier_id)), _ok())[1])
    return _bad_method()


@csrf_exempt
def api_ledger_invoices(request):
    """GET ?supplier_id=N lists one supplier's invoices; POST creates one."""
    if request.method == "POST":
        return _guard(lambda: _ok(invoice=ledger_invoice_dict(
            services.create_invoice(_body(request)), with_lines=True)))
    if request.method == "GET":
        supplier_id = str(request.GET.get("supplier_id") or "").strip()
        if not supplier_id:
            return _fail("یافت نشد", 404)
        date_from = str(request.GET.get("date_from") or "").strip()
        date_to = str(request.GET.get("date_to") or "").strip()
        return _guard(lambda: _ok(items=[
            ledger_invoice_dict(i)
            for i in services.ledger_invoices_list(
                supplier_id, date_from, date_to)]))
    return _bad_method()


@csrf_exempt
def api_ledger_invoice_detail(request, invoice_id):
    """GET full detail; PUT full-replace edit; DELETE removes the invoice."""
    if request.method == "GET":
        return _guard(lambda: _ok(invoice=ledger_invoice_dict(
            services.ledger_invoice_or_404(invoice_id), with_lines=True)))
    if request.method == "PUT":
        return _guard(lambda: _ok(invoice=ledger_invoice_dict(
            services.update_invoice(
                services.ledger_invoice_or_404(invoice_id), _body(request)),
            with_lines=True)))
    if request.method == "DELETE":
        return _guard(lambda: (services.delete_invoice(
            services.ledger_invoice_or_404(invoice_id)), _ok())[1])
    return _bad_method()