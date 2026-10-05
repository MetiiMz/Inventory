# -*- coding: utf-8 -*-
"""View packages.

``inventory.views`` contains only the HTML page shells (``pages``);
every JSON endpoint lives in ``inventory.api``:

* ``inventory.api.compat``  — legacy-shape endpoints the current
  frontend calls, backed by the same service layer;
* ``inventory.api.services``— the shared business rules (single source
  of truth for validation and transactional writes).
"""
from .pages import (  # noqa: F401
    calendar_page, dashboard, handler404, index, ledger_page, payments_page,
    products_page, repairs_page, settings_page, sold_page, tracking_page,
)
