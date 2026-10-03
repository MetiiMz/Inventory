# Implementation Plan: Manual Sale Price at Sale Time (Spec-002)

**Branch**: `002-manual-sale-price` (script-resolved; actual git development happens on the `test` branch — no branch hook in this project) | **Date**: 2026-10-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-manual-sale-price/spec.md` (clarified in session 2026-10-03)

## Summary

Remove the pre-set product sale price and the discount/"final price" concept: the sale price becomes a required manual entry at sale time (both the Sold page form and the Products page quick-sale modal), the redundant `Sale.final_price` column and `Product.sale_price` column are dropped via two migrations, and every report (dashboard boxes, per-brand table, 12-month chart, sold list, calendar, exports) is re-pointed from inventory projections / discounted prices to actual `Sale` records — including two new chart series for in-person vs. online sale counts.

Approach, in landing order: (1) re-point all price readers and change the sale-flow logic (required price, no discount, profit = price − cost, payment cap vs. the entered price) with tests; (2) rework report math (actual sales, current Jalali year, per-brand sold sums, chart counts) with tests; (3) update templates + JS (one price everywhere, new labels, two chart series); (4) product side (service, dicts, forms, list/sort, import/export) with tests; (5) the two column-dropping migrations, applied to the real local DB last. Small revertible commits per the constitution.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.14.4 (project `.venv`)

**Primary Dependencies**: Django 5.2.6 (Jinja2 3.1.6 as template backend for the untouched UI), openpyxl 3.1.5 (Excel I/O) — no additions (constitution rule 5)

**Storage**: SQLite — `db/db.sqlite3` (WAL); images in `db/images/`; backups in `db/backups/`

**Testing**: Django built-in test runner — `backend/manage.py test` (153 tests pre-feature; suite updated in place, research D11)

**Target Platform**: Local single-user desktop app (laptop), `manage.py runserver` only — per constitution

**Project Type**: Web application (Django backend in `backend/` + Jinja2 templates and vanilla JS in `frontend/`; data area `db/`)

**Performance Goals**: Single local user; all pages/reports stay responsive (<1 s) on the real data (thousands of rows) — no new targets beyond existing behavior

**Constraints**: No new dependencies; no server deployment; no auth/CSRF; URL routes stay byte-stable (Spec-001 contract); small revertible commits (constitution rule 7)

**Scale/Scope**: Single-user shop: ~10²–10³ products, ~10³ sales, ~5×10³ images. Change surface: 2 dropped columns, ~6 backend modules, 3 frontend templates + 1 inline chart script + 3 JS files, 10 test files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Gates against `.specify/memory/constitution.md` (rule numbers refer to "قوانین سخت‌گیرانه"):

- **Rule 1 — No behaviour change**: ⚠️ **Intentionally violated — documented exemption.** Spec-002 changes behaviour by design (required manual price, discount-concept removal, actual-sales report semantics). The rule exists for the Spec-001 structural restructure; the user's instruction and the spec's "Scope Note vs. Constitution" record this exemption.
- **Rule 2 — No unauthorized feature removal**: ✅ Pass. Every removal (discount concept, pre-set price field, final-price column/UI) is explicitly spec-approved (FR-001…FR-014); no endpoint or capability outside the spec is removed.
- **Rule 3 — Tests are the source of truth**: ⚠️ **Partially relaxed — documented exemption.** Tests asserting the now-obsolete behavior (discount alias, final-price fallback, projected aggregates) are *updated* — explicitly permitted by the user ("unlike Spec 001, this feature is explicitly allowed to edit tests"). The suite must be 100% green after the change (FR-015/FR-016) — still enforced.
- **Rule 4 — Domain-based file split**: ✅ Pass. Only the *content* of existing modules is edited (`services/sales.py`, `services/calendar.py`, `services/products.py`, `reports.py`, `utils.py`, `excel_io.py`, `api/compat/sales.py`, templates, `static/js`); no new packages, `__init__` re-exports untouched.
- **Rule 5 — No new dependencies**: ✅ Pass. No new libraries, no Docker, no auth/CSRF.
- **Rule 6 — Moves only via settings**: ✅ N/A — no file moves in this feature.
- **Rule 7 — Small revertible steps**: ✅ Pass. Landing plan: (1) reader re-pointing + sale-flow logic + tests, (2) report math + tests, (3) templates/JS (forms, lists, dashboard, chart, labels), (4) product side (service, dicts, templates, JS, import/export) + tests, (5) two column-dropping migrations applied to the local DB last. Each step individually revertible.

**Post-design (Phase 1) re-check**: no new violations. The data model, contracts, and quickstart all agree: no new dependencies, domain split respected, migrations are the final step (research D8), and all label/chart decisions (D5–D7) stay within the existing UI layer.

## Project Structure

### Documentation (this feature)

```text
specs/002-manual-sale-price/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
backend/
├── manage.py
├── requirements.txt                # unchanged (no new deps)
├── tikotime/                       # Django project settings/urls — untouched
├── inventory/
│   ├── models.py                   # Product/Sale: two fields removed (migrations)
│   ├── migrations/                 # + 0007_remove_sale_final_price, 0008_remove_product_sale_price
│   ├── reports.py                  # dashboard / brand / monthly reworked
│   ├── utils.py                    # product_dict & sale_dict key cleanup
│   ├── excel_io.py                 # import/export column cleanup
│   ├── views/pages.py              # untouched (key pass-through)
│   ├── api/compat/
│   │   ├── sales.py                # summary total_final → total_sale
│   │   └── …                       # other compat modules untouched
│   └── api/services/               # domain services (Spec-001 split)
│       ├── sales.py                # required price; discount concept removed
│       ├── calendar.py             # price_display → entered sale price
│       ├── products.py             # stop reading sale_price; sort map
│       └── …                       # payments/repairs/tracking/etc. untouched
└── tests/                          # nine modules + helpers.py, updated in place

frontend/
├── templates/
│   ├── products.html               # add-form price removed; quick-sale modal; sort option
│   ├── sold.html                   # discount input + final-price sort removed
│   ├── dashboard.html              # box labels; inline chart JS gains two series; brand labels
│   └── (calendar template untouched — data-driven via calendar.js)
└── static/js/
    ├── products.js                 # form/payload/sort cleanup
    ├── sold.js                     # price cells, detail rows, summary chip
    └── calendar.js                 # price fallback + day totals → entered price

db/
└── db.sqlite3                      # migrations applied last (with backup)
```

**Structure Decision**: Reuse the Spec-001 layout (`db/ backend/ frontend/`). No new directories or packages — this feature is content-level work across the already-split domain files; only `inventory/migrations/` gains two files.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Behaviour change (constitution rule 1) | Spec-002's entire purpose: required manual price, discount-concept removal, actual-sales report semantics | Keeping the Spec-001 freeze rule — rejected: that rule exists for the structural restructure only and is explicitly lifted by the user for this feature |
| Test edits (constitution rule 3) | Existing tests assert the now-obsolete behaviour (discount alias, final-price fallback, projected aggregates); the suite cannot be green against the new intended behaviour without updating them | Adding new tests alongside the old ones — rejected: the old tests would then assert behaviour the spec declares wrong, requiring the removed fields to stay |
