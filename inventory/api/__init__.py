# -*- coding: utf-8 -*-
"""API layer — the sole HTTP contract of the app.

Layout:

* ``services.py`` — all business rules (validation + transactional
  writes); the single source of truth.
* ``compat.py``   — legacy-shape ``/api/*`` endpoints the current
  frontend calls, backed by the same services (thin adapters, no logic).
"""
