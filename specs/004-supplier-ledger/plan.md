# Implementation Plan: Supplier Purchase Ledger — "حساب معین"

**Branch**: `004-supplier-ledger` (per the spec, no dedicated branch is created — development continues on the current `test` branch) | **Date**: 2026-10-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-supplier-ledger/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Add a brand-new, fully independent "حساب معین" (supplier purchase ledger) page for manually recording paper purchase invoices from suppliers: ledger suppliers, their invoices (Jalali purchase date + zero or more photos, one per physical page + line items with watch name / reference / quantity / unit purchase price, where **every total is computed, never entered** and **line items are unbounded**), rendered as an accordion (supplier list → expand to invoice list → detail modal with full inline editing). Implemented as a new `ledger` domain following the app's existing conventions: four new ORM models with cascade deletes, a `services/ledger.py` business-logic module, a `compat/ledger.py` adapter module under `/api/ledger/*`, a new `/ledger` page shell + `ledger.html` + `ledger.js`, and the four new tables added to the Clear Database wipe list (an explicit, temporary user decision, FR-014). The ledger has zero coupling to products/sales/payments/repairs/tracking/reports. All 167 existing tests must stay 100% green; new tests cover the full ledger surface.

## Technical Context

**Language/Version**: Python 3.14 (venv at project root; README supports 3.10–3.14)

**Primary Dependencies**: Django 5.2, Jinja2, openpyxl — all existing; **no new dependencies** (constitution rule 5)

**Storage**: SQLite at `db/db.sqlite3` (`TIKOTIME_DB` override); ledger images stored in the shared `db/images/` folder, served by the existing `/data/images/<name>` route

**Testing**: Django test runner — run from the `backend/` directory (test discovery starts from the CWD; invoked from the repo root it finds 0 tests): `cd backend && ../.venv/bin/python manage.py test`; baseline verified 2026-10-05: **167 tests, 0 failures**. New tests go in new files only; no existing test file is modified.

**Target Platform**: local desktop, single user, fully offline (Linux dev box; Windows per README); never deployed to a server

**Project Type**: web application — server-rendered Jinja2 page shells + JSON API (`/api/*` is the sole HTTP contract) + vanilla-JS frontend

**Performance Goals**: none beyond the existing app — single local user, trivial data volumes; no latency targets. SC-007's "under 3 minutes" is a manual usability criterion, verified by the quickstart walkthrough (not an automated/perf gate).

**Constraints**: no new dependencies/Docker/auth/CSRF; existing endpoint JSON shapes must remain byte-for-byte identical; offline operation; Jalali date conventions and Persian UI labels throughout; small reversible commits (constitution rule 7)

**Scale/Scope**: one user on one laptop; ledger sizes are small (dozens of suppliers, tens of invoices each; line items per invoice unbounded — real paper invoices can carry ~100 lines)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution was written for the Spec-001 structural restructure ("refactor, no behaviour change"). This feature is **new additive functionality**, and the spec's "Scope Note vs. Constitution" explicitly re-scopes rule 1 for it. Gate evaluation:

| # | Gate | Result |
|---|------|--------|
| 1 | No behaviour change of existing features | **PASS (with documented intent)** — every existing endpoint, service, template, and JS file stays byte-identical, *except*: (a) four new table names added to `dbhelpers._CLEAR_TABLES` (FR-014, explicit temporary user decision), which makes Clear Database also wipe ledger tables and their photos via the existing `_remove_orphaned_images` (logo kept); (b) the `sqlite_sequence` reset placeholder count in `clear_database()` must follow the tuple length; (c) `count_records()`/`/api/database/info` will now also report ledger table counts (additive preview change, same code path). No existing service logic or JSON shape changes. |
| 2 | No unapproved feature removal | **PASS** — nothing is removed. |
| 3 | Tests are the source of truth | **MUST** — after every commit the full suite (167 existing + new ledger tests) must be 100% green; new tests only in `tests/test_service_ledger.py` / `tests/test_compat_ledger.py`; existing test files untouched. |
| 4 | Domain-based file split | **PASS** — new `ledger` domain module in `api/services/` and `api/compat/`, re-exported from each package's `__init__.py`; serializers added to `inventory/utils.py` alongside the existing `*_dict` functions; existing domains untouched. |
| 5 | No new dependencies/complexity | **PASS** — Django ORM, SQLite, Jinja2, vanilla JS only. |
| 6 | Relocations via settings only | **N/A** — no files are relocated. |
| 7 | Small reversible commits | **MUST** — commit sequence: (1) models + migration; (2) utils serializers; (3) services/ledger; (4) compat/ledger + urls; (5) dbhelpers clear-list; (6) page shell + nav; (7) ledger.html + ledger.js + CSS; (8) tests. Each commit keeps the suite green. |

**Re-evaluation after Phase 1 design**: PASS — the design in `data-model.md` / `contracts/` adds no new dependencies, no coupling to existing domains (SC-004), keeps all totals computed (FR-007), reuses the existing upload/image/clear-database machinery, and introduces no new transport or tooling.

## Project Structure

### Documentation (this feature)

```text
specs/004-supplier-ledger/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── ledger-api.md    # /api/ledger/* endpoint contract + page/nav contract
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── inventory/
│   ├── models.py                    # + LedgerSupplier, LedgerInvoice, LedgerLineItem, LedgerInvoiceImage
│   ├── migrations/0009_ledger.py    # NEW — 4 tables + indexes
│   ├── utils.py                     # + ledger_supplier_dict / ledger_invoice_dict (exposes ordered `images` filename array + computed totals) / ledger_line_dict
│   ├── dbhelpers.py                 # _CLEAR_TABLES += 4 ledger tables (FR-014)
│   ├── views/pages.py               # + ledger_page(request)
│   └── api/
│       ├── services/ledger.py       # NEW — ledger business logic (single source of truth)
│       ├── services/__init__.py     # + re-export ledger surface
│       ├── compat/ledger.py         # NEW — /api/ledger/* adapters (thin, no logic)
│       └── compat/__init__.py       # + re-export ledger adapters
├── tikotime/
│   └── urls.py                      # + /ledger page route + 4 /api/ledger/* routes
└── tests/
    ├── test_service_ledger.py       # NEW — service-level tests (CRUD, cascade, totals, image cleanup)
    └── test_compat_ledger.py        # NEW — API contract tests (envelopes, errors, filtering, clear-db)

frontend/
├── templates/
│   ├── base.html                    # + "حساب معین" nav item immediately after "پرداخت‌ها"
│   └── ledger.html                  # NEW — page shell: topbar, accordion (first-photo thumbnail + "+N" badge), empty state, modals (invoice form w/ multi-photo, detail gallery w/ inline line editing)
└── static/
    ├── js/ledger.js                 # NEW — accordion, multi-photo add/remove/reorder, full-size image-view modal, invoice modal w/ inline line editing, deletes
    └── css/app.css                  # + ledger accordion/row styles (follows existing conventions)
```

**Structure Decision**: Web application layout (backend + frontend), matching the repository's three-part division documented in `README.md`. The ledger is a new `ledger` domain inside the existing `inventory` Django app (no new Django app) — consistent with how every other domain (products, sales, payments, …) lives in one app, split into per-domain `services/` and `compat/` modules.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — all gates pass as documented above. The only intentional behaviour change (Clear Database wiping ledger tables + photos) is the user's explicit, temporary decision recorded in FR-014 and the spec's Scope Note, not a complexity addition.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — (none) | — | — |
