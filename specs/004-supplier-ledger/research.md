# Research: Supplier Purchase Ledger (Spec-004)

All "unknowns" from the Technical Context were resolved by direct inspection of the
codebase (single local project, no external system to research). Each entry records
the decision, why, and what was rejected.

## 1. API endpoint layout

- **Decision**: A new `/api/ledger/*` route family under a `ledger` compat domain, mirroring the existing per-domain layout (`products`, `payments`, …):
  - `GET/POST /api/ledger/suppliers`
  - `PUT/DELETE /api/ledger/suppliers/<supplier_id>`
  - `GET/POST /api/ledger/invoices` (GET takes `?supplier_id=N`)
  - `GET/PUT/DELETE /api/ledger/invoices/<invoice_id>`
- **Rationale**: The spec delegates the exact layout to the Plan phase "following the app's existing conventions"; every other domain uses exactly this shape (plural collection + `/<id>` detail + verbs mapped onto methods, as in `tikotime/urls.py`).
- **Alternatives considered**: Nested URLs (`/api/ledger/suppliers/<id>/invoices`) — rejected: no existing domain nests routes; flat mixed routes — rejected: inconsistent with the per-domain split.

## 2. Invoice editing mechanism (spec Assumption #5)

- **Decision**: **Full-replace semantics** — `POST /api/ledger/invoices` and `PUT /api/ledger/invoices/<id>` accept the *entire* line-item list; the service replaces all lines in one `transaction.atomic()` block (update invoice fields → delete lines → bulk-create new lines).
- **Rationale**: Matches the app's established PUT contract ("PUT handlers always receive the full form, so legacy behaviour is *replace*" — `services/common._merge_partial` docstring). One round-trip, one transaction, no per-line id bookkeeping in the UI; FR-009 (single editing flow) holds directly.
- **Alternatives considered**: Per-line add/edit/delete endpoints (`POST .../lines`, `PUT .../lines/<id>`, …) — rejected: more routes, more partial-state races, more frontend state to reconcile, and no existing precedent in the codebase.

## 3. Data model

- **Decision**: Three new models in `inventory/models.py` with a fresh migration `0009_ledger`:
  - `LedgerSupplier(name)` — table `ledger_suppliers`
  - `LedgerInvoice(supplier FK CASCADE, purchase_date ISO CharField(10))` — table `ledger_invoices`; zero or more `LedgerInvoiceImage` rows (filename + order, CASCADE) — table `ledger_invoice_images`
  - `LedgerLineItem(invoice FK CASCADE, watch_name, reference, quantity int, unit_price float)` — table `ledger_lines`
  - No stored totals anywhere; no FK to `Product`/`Sale`/`Payment`/`Repair`/`Tracking`/`Setting`.
- **Rationale**: FR-002/FR-007/FR-015. Plain `db_table` names + `BigAutoField` ids match all existing models; FK `on_delete=CASCADE` gives FR-004/FR-012 for free (SQLite `foreign_keys=ON` is set in `settings.py`).
- **Alternatives considered**: One table with JSON lines — rejected: JSON blobs can't be indexed/queried, cascade delete is lost, and the app is relational end-to-end; a 4th "totals" table — rejected by FR-007 (totals must never be stored).

## 4. Date handling

- **Decision**: Store `purchase_date` as ISO `YYYY-MM-DD` in a `CharField(max_length=10)` (same as `Product.purchase_date`, `Sale.sale_date`, `Payment.pay_date`); accept Jalali or ISO input via `_parse_iso_or_raise` (`services/common.py`), display via `fa_date()` (`inventory/utils.py`).
- **Rationale**: FR-005 "per the app's existing date conventions"; every other domain works this way and `jalali.py` is the single conversion source.
- **Alternatives considered**: `DateField` — rejected: breaks the app-wide string-date convention (sorting, export, jalali interplay all assume ISO strings in CharFields).

## 5. Quantity normalization

- **Decision**: `quantity = to_int(raw) or 1` — blank, missing, `0`, or non-numeric all become **1** (spec: "blank means 1"). `unit_price = max(0.0, to_float(raw))`; `watch_name` is required (Persian `ApiError` when missing).
- **Rationale**: FR-006/edge case "Blank quantity". A purchased watch with 0 units is meaningless in this paper-invoice workflow, so 0 maps to the same normalization as blank; the rule is total and easy to test.
- **Alternatives considered**: reject `0` with an error — rejected: the UI is forgiving (blank is explicitly legal) and rejecting a stray 0 would block saving a whole invoice; storing the raw blank and normalizing at display time — rejected: FR-007 says the line total is *computed*; a stored normalized integer keeps the DB authoritative and the computed value trivial.

## 6. Computed totals

- **Decision**: Totals exist only in the serializers — `ledger_line_dict` computes `line_total = quantity * unit_price`; `ledger_invoice_dict` computes `total_quantity` and `total_amount` over the invoice's lines, plus `*_display` values via `fa_money`. The list endpoint (`GET /api/ledger/invoices`) returns totals without line detail; the detail endpoint (`GET /api/ledger/invoices/<id>`) returns the full `lines` array.
- **Rationale**: FR-007/FR-008/FR-010/SC-003; mirrors `payment_dict` (computed `remaining`, `paid_percent`, `*_display`) in `inventory/utils.py`.
- **Alternatives considered**: computing totals client-side only — rejected: the backend must stay the single source of truth (constitution + "Tests are the source of truth"); a `?detail` flag on one endpoint — rejected: two explicit routes match the collection/detail convention.

## 7. Image storage & cleanup

- **Decision**: Invoice photos reuse the **existing** upload/serving machinery: `POST /api/upload` (JSON-base64 or multipart, 2 MB cap, `img_*` filenames — called **once per photo page**) + `GET /data/images/<fname>`; each photo's filename is stored in a `LedgerInvoiceImage` row (`filename`, `order` = page sequence) on the invoice. On invoice delete, invoice update-with-new-photo-set, and supplier cascade delete, the service calls `remove_image()` for every file no longer referenced (same as `delete_product`/`delete_repair`/`delete_tracking`).
- **Rationale**: FR-005 ("uploaded through the app's existing image upload"); the shared `db/images/` folder is exactly what FR-014/`_remove_orphaned_images` already sweeps (all files except the site icon). Orphan-file cleanup on delete is the established pattern in every image-bearing domain.
- **Alternatives considered**: A separate invoice-image folder — explicitly deferred to a future spec (FR-014 note / Out of Scope); storing image bytes in the DB — rejected: contradicts the app's file-based image storage.

## 8. Clear Database integration (FR-014)

- **Decision**: Add `"ledger_suppliers", "ledger_invoices", "ledger_lines", "ledger_invoice_images"` to `dbhelpers._CLEAR_TABLES`. No other change: `clear_database()` already takes the automatic pre-clear backup, deletes all listed tables in one transaction, resets their `sqlite_sequence` rows, and then `_remove_orphaned_images(site_icon)` removes every image except the logo — which covers the invoice photos.
- **Rationale**: FR-014 + edge case "Clear Database with ledger data present"; keeps the wipe mechanism single-sourced in `dbhelpers.py`.
- **Implementation pitfall (flagged for tasks)**: `clear_database()` builds `DELETE FROM sqlite_sequence WHERE name IN (?, ?, ?, ?, ?)` with a **hardcoded 5 placeholders** matching the current 5-table tuple; the placeholder count must track the tuple length when the 4 ledger tables are added (5 → 9 placeholders). `count_records()` (used by `/api/database/info` on the settings page) iterates `_CLEAR_TABLES` and will therefore also report the 4 new tables — an additive preview change, acceptable and noted in the Constitution Check.
- **Alternatives considered**: a separate ledger-only wipe path — rejected: the user's decision is that the *one* Clear Database action wipes everything; a second mechanism would fragment the backup/wipe flow.

## 9. Independence guarantee (SC-004)

- **Decision**: The ledger domain's modules import only `inventory.models` (ledger classes), `inventory.jalali`, `inventory.utils` (`clean`, `to_int`, `to_float`, `fa_date`, `fa_money`, `remove_image`), and the shared `services/common` primitives — never products/sales/payments/repairs/tracking/settings/reports modules, and never the product form's `supplier` CharField. The dashboard/report code is untouched.
- **Rationale**: FR-002/SC-004 ("0 references … verifiable by code inspection"); keeping imports domain-local makes the check trivially grep-able.
- **Alternatives considered**: reusing `Setting` rows for suppliers (as brands do) — rejected: brands are a settings convenience, but ledger suppliers need real relational cascade delete to invoices; reusing `Product.supplier` text — explicitly out of scope (no shared values/suggestions).

## 10. Page, navigation, and frontend behaviour

- **Decision**:
  - Route `GET /ledger` → `views.ledger_page` (renders `ledger.html` via `page_ctx(request, "ledger")`, like every other page shell).
  - Nav item "حساب معین" inserted in `base.html` **immediately after** the "پرداخت‌ها" link (FR-001/SC-001), with a document/receipt-style SVG icon consistent with the sidebar.
  - `frontend/templates/ledger.html` + `frontend/static/js/ledger.js` follow `payments.html`/`payments.js` conventions: topbar with primary action button, `.glass` sections, `modal-backdrop` modals with `data-close-modal`, `toast()`, `api()`, `esc()`, `faMoney`/`money`, `jFromIso`, `setupImageUpload` (`.img-upload`), and `data-jalali-today` date inputs with the existing Jalali datepicker.
  - Accordion (FR-011): one expanded supplier at a time; clicking a supplier row expands it in place (its invoice list + "افزودن فاتوره" control) and collapses any previously expanded supplier; clicking another supplier swaps.
  - Invoice detail modal doubles as the inline editor (FR-009): photo gallery (add / remove / reorder the page photos), date, editable line-item table (add row / edit cells / remove row), computed totals row, single save.
  - Destructive actions (delete invoice / delete supplier) go through a confirm modal, matching the app's existing destructive-action pattern (spec Assumption).
  - Empty ledger shows the existing empty-state pattern (`#...-empty` block) with the "add supplier" control.
- **Rationale**: spec FR-001/FR-008/FR-010/FR-011 + Assumptions; every pattern cited above already exists in `frontend/static/js/app.js` and the payments/tracking pages.
- **Alternatives considered**: a separate "new invoice" modal plus a read-only detail modal — rejected: the spec's input explicitly asks for "a detail modal with full inline editing" and FR-009 requires one editing flow; tabs instead of an accordion — rejected: the spec mandates the accordion.

## 11. Full-size photo viewing

- **Decision**: A small image-view modal on the ledger page: clicking the list thumbnail (or any photo in the detail modal's gallery) opens `modal-img-view` showing the same `/data/images/<fname>` source at full size; closed via `data-close-modal` / backdrop / Escape like every other modal.
- **Rationale**: The app's existing image-viewing pattern is "serve via `/data/images/`, display in an `<img>`" — there is no lightbox anywhere in the current frontend (verified by search). A full-size `<img>` inside the standard modal system is the minimal, convention-consistent way to satisfy FR-008's "clicking it opens the full image".
- **Alternatives considered**: `window.open`/new tab — rejected: breaks the in-app UX and isn't used anywhere in the current frontend; a dedicated lightbox component — rejected as new complexity (constitution rule 5 spirit).

## 12. Supplier list ordering & uniqueness

- **Decision**: Suppliers listed by `name` ascending (like the brands list, which orders by value); duplicate-name rejection is exact-match on the stripped name (like `dbhelpers.add_brand`), with Persian error messages: "نام تأمین‌کننده خالی است" / "این تأمین‌کننده قبلاً ثبت شده است". Rename validates the same way, excluding the supplier itself.
- **Rationale**: FR-003 ("same list pattern the app uses elsewhere — as with brand/product lists"); brands are the closest analogue (name-only, add/rename-free list primitive) and set the message style.
- **Alternatives considered**: order by `-id` (newest first, like payments) — rejected: an alphabetical ledger is the natural bookkeeping view and matches brands; case-insensitive dedupe — rejected: the app's dedupe conventions are exact-match; over-engineering for a single-user Persian app.

## 13. Testing strategy

- **Decision**:
  - `backend/tests/test_service_ledger.py` — service-level tests using the `call(fn, *args)` + `ApiError` pattern from `test_service_infra.py`: supplier create/duplicate/rename/delete-cascade; invoice create/update/delete (incl. **zero-photo** invoices and multi-photo invoices with ordered `LedgerInvoiceImage` rows); blank & zero quantity → 1; zero-line invoices; computed line/invoice totals vs hand-computed values (incl. mixed quantities); date validation; `remove_image` called on delete/photo-set-replacement/supplier-cascade.
  - `backend/tests/test_compat_ledger.py` — API contract tests with Django's test client (pattern of `test_compat_contract.py`): ok/fail envelopes, wrapped create payloads, `items` lists (incl. the `images` array), 404s, Persian error strings, `?supplier_id` filtering, and a clear-database test proving the four ledger tables + photos are wiped while the site logo file survives.
  - No existing test file is modified (constitution rule 3).
- **Rationale**: FR-016 + SC-002/SC-003/SC-005/SC-006; mirrors the two-tier split the suite already uses (service vs compat).
- **Alternatives considered**: one single test module — rejected: the suite's convention is per-tier modules; Selenium/browser tests — rejected: not part of the app's testing stack.