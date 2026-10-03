# Project Memory Index — TikoTime (Watch Inventory)

> Quick-reference context for any AI/human session working on this project.
> Detailed activity log lives in `JOURNAL.md`.

## Project Overview
- **Name:** TikoTime — سیستم مدیریت انبار فروشگاه ساعت (Watch Shop Inventory Management)
- **Type:** Fully local, offline-first, Persian (Farsi) web app with Jalali (Shamsi) calendar
- **Stack:** Django 5.2 + Jinja2 (django-jinja env) + SQLite + vanilla JS. Legacy Flask code **fully removed** (2026-09-08 — port verified before deletion).
- **Entry point (target):** `manage.py runserver` / gunicorn inside `.venv` — user explicitly wants `requirements.txt`, NO shell script.
- **UI/UX:** frozen by user decision — existing templates/static/js must render unchanged.
- Requirements (pinned): Django==5.2.6, Jinja2==3.1.6, gunicorn==23.0.0, whitenoise==6.11.0, openpyxl==3.1.5

## Key Files (Django rewrite — in progress)
| File | Purpose | Status |
|---|---|---|
| `tikotime/settings.py` | Django settings (SQLite in `data/`, whitenoise) | done |
| `tikotime/urls.py` | page routes + the legacy-shape `/api/*` routes (the app's sole API contract) | done |
| `tikotime/jinja.py` | Jinja2 env with fa_* helpers + template globals | done |
| `inventory/models.py` | ORM: Setting/Product/Sale/Payment/Repair/Tracking, true PK/FK + indexes | done |
| `inventory/utils.py` | fa_* helpers, parsers, dict serializers (legacy JSON shape) | done |
| `inventory/reports.py` | dashboard stats via ORM aggregates | done |
| `inventory/jalali.py` | Jalali conversion (unchanged port) | done |
| `inventory/views/` | products, sales, payments, repairs, tracking, calendar, pages, shared (brands/upload/images), backups, exportimport, settings_api, common | done |
| `inventory/migrations/` | Django migrations (0001_initial; 0002 +0003 = quantity add/remove history; 0004 = Sale/Payment `settled_at`; 0005 = seed store_name «Tick O Time») | done |
| `inventory/excel_io.py` | Excel/CSV import-export via openpyxl (Persian headers) | done |
| `README.md` | Persian run/usage guide (rewritten 2026-09-06) | done |
| ~~`legacy_flask/`~~ | removed 2026-09-08 — port complete, no references remain | deleted |

## Core Domain Concepts
- Inventory rows are **one watch per row** (تعداد field removed again 2026-09-06 at user request — was briefly restored then reverted; sale → ناموجود, sale delete → موجود again). Total value chips = unit prices (legacy semantics).
- Unique keys per row: `کد دفتر فروشگاه` (shop office code) + `کد انبار سایت` (site warehouse code)
- Sales record buyer name/phone, sale type (in-person/online), payment (cash/deposit with cash/POS/card-transfer breakdown)
- Modules: inventory, sales, repairs, order tracking, payments, Jalali calendar, dashboard, backup, CSV/Excel I/O, theming (light/dark, RTL, Apple-blue accent)
- Single-user, no auth by design (add login before public deployment)

## Data Locations
- `data/watch_inventory.db` — SQLite DB
- `data/images/`, `data/backups/`, `data/exports/`

## Conventions for This Memory System
- Journal entries are written in `JOURNAL.md` in GitHub-commit style:
  ```
  ## <short-hash> — YYYY-MM-DD HH:MM
  **type:** feat|fix|docs|chore|explore
  **scope:** <area>
  **subject:** <one-line summary>

  <body: what was done and why>
  ```
- Every meaningful action on this project gets a new entry appended (newest at top).

## Known schema facts (2026-09-03; updated session IV 2026-09-07)

- `sales.sale_date`, `payments.pay_date`, `products.purchase_date` are stored as **ISO Gregorian** (`YYYY-MM-DD`); the UI sends raw Jalali (`۱۴۰۵/۰۶/۱۲`) and the backend converts via `parse_jalali_date`. Never store raw Jalali strings.
- **Session IV additions:** `sales.settled_at` + `payments.settled_at` (datetime, migration 0004) — set when a deposit payment is added/settled/edited, shown in the sale detail modal; `sales.invoice_code` format TT-YYYYMM-NNNN (`utils.invoice_code`); buyer name + phone are required on sale create/update (API-validated); `settings` row `store_name` defaults to «Tick O Time» (migration 0005; `page_ctx` fallback for every page's title/sidebar brand); site icon lives in `settings.site_icon` and is rendered in favicon + sidebar.
- **Shared JS:** `static/js/jalali-datepicker.js` (popup Jalali calendar, attach via `data-datepicker`) and `bindMoneyInput`/`moneyIn` in `static/js/app.js` (live thousands-separator) are the shared helpers — reuse them for any new date/price input.
- `products`/`sales` were rebuilt (2026-09-03) with true `INTEGER PRIMARY KEY` + FK `ON DELETE CASCADE`; `database.py::_migrate_inner` auto-repairs legacy `id INT` tables on every `init_db()` — keep that repair idempotent when adding migrations.
- Deleting a **product** cascades its **sales** (which then vanish from the Calendar); deleting a **sale** restores the product to available and cascade-removes its deposit receipt.
- The Calendar (`/api/calendar`, `/api/calendar/day`) live-queries `sales` — no separate event store. `static/js/calendar.js` re-fetches on bfcache `pageshow` and tab `visibilitychange`.
- Integration tests live in `tests/` and run against a temp DB: `.venv/bin/python tests/test_calendar_sale_deletion.py`.

## Known issues / decisions (updated 2026-09-06)
- ⚠️ **OPEN (2026-10-01, found during the layout-refactor preflight) — test isolation leak (out of scope of the refactor):** `tests/test_services_misc.py:90` (`test_multipart_upload`) and `:100` (`test_json_base64_upload`) call `services.save_upload()` **without** `override_settings(IMG_DIR=…)`, so every full-suite run writes **2 × 58-byte orphan PNGs** into the REAL `data/images/` (write path: `inventory/api/services.py:955-956` → `settings.IMG_DIR`). Observed orphans: 2026-09-17, 09-27, 09-28, 09-29, 10-01 (`img_<date>_*.png`, 58 bytes each). **Fix later as a standalone change** — add `override_settings(IMG_DIR=<tmpdir>)` to those two tests — and NOT during this refactor, because FR-010 forbids editing existing test files. Until then: data-area gates compare image **sets** before/after (never a fixed count) — see SC-004, T047/T048 and quickstart V4.

- ✅ **FIXED (2026-09-06):** Sales-page deposit bug — Django `api_sales` lists ALL sales regardless of `is_settled` (verified in E2E suite).
- ✅ **FIXED (2026-09-06):** `templates/dashboard.html` still referenced removed `qty` key → `no such element` shown on dashboard + Add-Watch modal area; replaced with available-based display.
- ✅ **FIXED (2026-09-06):** `inventory/utils.py::product_dict` lacked `is_available` while `products.js`/`calendar.js` use `p.is_available` — added `"is_available": bool(r.available)` (keep BOTH keys when touching serializers).
- ✅ **FIXED (2026-09-06):** serializer keys dropped in the port restored — `product_dict`: `total_value(_display)`, `total_sale_value(_display)`, `profit_per_unit(_display)`, `availability_fa`, `purchase_date_weekday`; `repair_dict`: `status_color`, `is_warranty_fa`, `delivery_date_weekday`; `tracking_dict`: `status_color` (+`TRACKING_STATUS_COLOR`); `payment_dict`: `paid_percent`. Rule: when porting a serializer, diff against `legacy_flask/app.py` `*_dict` and grep the JS for consumed keys.
- ✅ **FIXED (2026-09-06):** Quantity (تعداد) restored end-to-end — `products.quantity` (migration 0002), sale decrement / sale-delete restore, sold-out API guard, form + table + JS, Excel I/O «تعداد» column, `dbhelpers._REQUIRED_COLS`. Editing a product no longer flips `available` unless quantity changes (`_product_values(payload, min_quantity=0)` on update, min 1 on create).
- ✅ **FIXED (2026-09-06):** `.claude/launch.json` still launched legacy Flask `app.py` on :5000 → now `manage.py runserver 8000`.
- **User decisions:** rewrite on Django; UI/UX unchanged; run via venv + `requirements.txt` (no shell script); optimize speed; tests only when the user asks (2026-09-06: user asked → full suite written & passed; NOT checked into repo, lives at `/tmp/tikotime_fulltest.py`); **Git adopted 2026-09-06 — every completed task must be committed (repo on `main`, initial commit `776891f`, runtime `data/` ignored).**
- Every command executed must be logged in `.memory/COMMANDS.md` (user request).

## Facts verified by E2E suite (2026-09-06, 75/75 PASS)
- Isolated test DB via env var: `TIKOTIME_DB=/tmp/xxx.db` is honored by `tikotime/settings.py` — use it for any DB-touching test; real `data/watch_inventory.db` stays untouched.
- Repairs statuses: `received | in_progress | waiting_parts | done | delivered` (delivered sets `return_date` to today automatically via `/api/repairs/<id>/status`).
- Tracking statuses: `new | ordered | found | delivered | cancelled`.
- Image upload `/api/upload` returns key `path` (JS uses `res.path`); served at `/data/images/<name>`.
- Bulk-delete endpoints return `deleted = len(ids)` (selected count, not matched count).
- `settle-full` on a deposit receipt: sets receipt paid=total, marks linked sale `is_settled=1` and adds remaining to `sale.paid_cash`.
- Deposit sale creates a linked `Payment` row automatically; deleting the sale restores product `available=1` (cascade removes receipt).
- Persian-digit phones/dates accepted everywhere; stored latin/ISO (`parse_jalali_date`, `to_en_phone`).
- Excel import: upsert keyed on codes with `update_existing=1`; headers = `PRODUCT_HEADERS` (وضعیت column: موجود/ناموجود).

## Work in progress (session IV — 2026-09-06)
- **22-item multi-page feature request received; context gathering only — NO code edits yet.** Full breakdown + findings live in `.memory/JOURNAL.md` (entry b7d2f90) and `.claude/PROGRESS.md` (top section).
- Short form: dashboard chart=profit-only/green + brand sales value + out-of-stock images; Jalali popup date-picker (new shared component) for purchase & sale dates; sale modal rework (final discounted price required, thousands-sep typing, name/phone required, invoice code, payment breakdown optional); calendar event images + full details; sales-page visibility bug to reproduce; payments page product details/images/purchase+settlement dates (settlement date needs new `Sale.settled_date`-style field or derive from Payment.updated_at); repairs/tracking thousands-sep; settings site-icon upload + site name «Tick O Time».
- Key decisions pending: invoice code source (likely `Sale.id`), settlement-date storage (migration vs derived), datepicker placement (`static/js/jalali_datepicker.js` + CSS, shared by products/sales forms).

## Command Log
- All executed shell commands are appended to `.memory/COMMANDS.md` (commit-style).
