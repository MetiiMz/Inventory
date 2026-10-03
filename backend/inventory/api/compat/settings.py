# -*- coding: utf-8 -*-
"""Brand and store-settings adapters: brands CRUD, settings, site icon."""

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from inventory.api import services

from .common import _body, _ok, _guard


@csrf_exempt
def api_brands(request):
    """GET lists brands; POST adds one (``{name}``) — legacy contract."""
    if request.method == "POST":
        return _guard(lambda: (services.brands_add(_body(request)), _ok())[1])
    return _guard(lambda: _ok(brands=services.brands_list()))



@csrf_exempt
@require_POST
def api_brands_delete(request):
    """POST /api/brands/delete — remove a brand."""
    return _guard(lambda: (services.brands_delete(_body(request)), _ok())[1])



@csrf_exempt
def api_settings(request):
    """GET reads store settings; POST persists the whitelisted keys."""
    if request.method == "POST":
        services.save_settings(_body(request))
        return _ok()
    return _ok(**services.site_settings())



@csrf_exempt
@require_POST
def api_settings_site_icon(request):
    """POST /api/settings/site-icon — ``{icon: "<filename>"}``."""
    icon = services.set_site_icon(_body(request).get("icon"))
    return _ok(icon=icon)

