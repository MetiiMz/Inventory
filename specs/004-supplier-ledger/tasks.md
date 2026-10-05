# Tasks: Supplier Purchase Ledger — "حساب معین" (Spec-004)

**Input**: Design documents from `/specs/004-supplier-ledger/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/ledger-api.md, quickstart.md

**Tests**: Requested — FR-016 mandates new automated tests (supplier/invoice/line-item CRUD, cascade deletion, computed totals, Clear Database). Tests live in two NEW files only: `backend/tests/test_service_ledger.py` and `backend/tests/test_compat_ledger.py`. No existing test file may be modified (constitution rule 3); the 167-test baseline must stay 100% green after every commit.

**Branch**: development continues on the current `test` branch (per spec; no dedicated branch is created). Run `makemigrations` / `migrate` / `runserver` from the repository root with `.venv/bin/python backend/manage.py ...` — the exception is test runs: Django test discovery starts from the CWD and finds 0 tests when invoked from the repo root, so always run the suite from the `backend/` directory: `cd backend && ../.venv/bin/python manage.py test` (see T001 / T026).

**Persian error-message canon** (used verbatim in service/compat tasks, from contracts/ledger-api.md):
`نام تأمین‌کننده خالی است` · `این تأمین‌کننده قبلاً ثبت شده است` · `تأمین‌کننده یافت نشد` · `تاریخ معتبر نیست` · `نام ساعت را وارد کنید` · `عکس معتبر نیست` · `یافت نشد`

**Amendment, 2026-10-05** (reflected throughout): invoices now carry **zero or more photos** (one `LedgerInvoiceImage` row per physical page, `images` array in payloads, `order` = display sequence), and **line items per invoice are unbounded** (SC-007's "5" is a walkthrough example only, not a cap).

---

## Phase 1: Setup

**Purpose**: Baseline gate before touching anything (constitution rule 3 — tests are the source of truth).

- [x] T001 Verify the 167-test baseline is green before any ledger work begins: run `cd backend && ../.venv/bin/python manage.py test` and confirm 0 failures (covers all of backend/tests/; record the result as the green baseline for this feature)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Ledger persistence layer + shared serializers — every user story depends on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T002 Add the four ledger models to backend/inventory/models.py — ""`LedgerSupplier(name: CharField(200), not blank after strip; created_at: DateTimeField auto_now_add; updated_at: DateTimeField auto_now; Meta.db_table="ledger_suppliers"; index on ["name"])`; `LedgerInvoice(supplier: ForeignKey LedgerSupplier on_delete=models.CASCADE related_name="invoices"; purchase_date: CharField(10, default="", blank=True, db_index=True) stored ISO `YYYY-MM-DD`; created_at: DateTimeField auto_now_add; Meta.db_table="ledger_invoices"; index on ["supplier_id", "-id"])`; `LedgerLineItem(invoice: ForeignKey LedgerInvoice on_delete=models.CASCADE related_name="lines"; watch_name: CharField(200) required free text — NOT a reference into inventory stock; reference: CharField(100, default="", blank=True); quantity: IntegerField default=1; unit_price: FloatField default=0; Meta.db_table="ledger_lines"; index on ["invoice_id", "id"])`; `LedgerInvoiceImage(invoice: ForeignKey LedgerInvoice on_delete=models.CASCADE related_name="images"; filename: CharField(255, default="", blank=True) — the stored name of an uploaded image in shared db/images/; order: IntegerField default=0 — display sequence, page 1, 2, 3…; created_at: DateTimeField auto_now_add; Meta.db_table="ledger_invoice_images"; index on ["invoice_id", "order"])` — exactly per data-model.md: no stored totals anywhere, **no cap on line items per invoice**, no foreign key to Product/Sale/Payment/Repair/Tracking/Setting (FR-002, SC-004)
- [x] T003 Generate migration backend/inventory/migrations/0009_ledger.py (`.venv/bin/python backend/manage.py makemigrations inventory` — must produce ONLY the four new ledger tables), then apply it (`.venv/bin/python backend/manage.py migrate`) and verify `ledger_suppliers`, `ledger_invoices`, `ledger_lines`, and `ledger_invoice_images` exist in db/db.sqlite3
- [x] T004 [P] Add the ledger serializers to backend/inventory/utils.py alongside the existing `*_dict` functions — `ledger_supplier_dict` (id, name, invoice_count), `ledger_line_dict` (id, watch_name, reference, quantity, quantity_display via fa_num, unit_price, unit_price_display via fa_money, `line_total = quantity * unit_price` and `line_total_display` — always computed, never read from a stored column), and `ledger_invoice_dict` (id, supplier_id, purchase_date, purchase_date_fa via fa_date, `images` = the ordered photo-filename array `[img.filename for img in invoice.images.all() ordered by (order, id)]` — empty list when the invoice has no photos; the UI derives the thumbnail from the first entry and the \"+N\" badge from `len - 1`, created_at, `total_quantity`/`total_amount` computed from the invoice's lines + `total_quantity_display`/`total_amount_display` in fa_money — always computed from the current lines, never read from storage; and a `lines` list populated only in detail mode) — mirrors the payment_dict computed-field pattern (FR-007, SC-003)

**Checkpoint**: Foundation ready — ledger tables exist in the DB and the serializer layer is testable; user story implementation can now begin.

---

## Phase 3: User Story 1 - Record a paper purchase invoice (Priority: P1) 🎯 MVP

**Goal**: From "حساب معین" the user adds a supplier and records one of its paper invoices: Jalali purchase date, zero or more photos (one per physical page), and line items (watch name / reference / quantity / unit price — unbounded in number); blank quantity = 1; every total computed, never entered.

**Independent Test**: With an empty ledger, create a supplier, add an invoice with three line items (one left with blank quantity) and two page photos; verify via `GET /api/ledger/invoices?supplier_id=<id>` and `GET /api/ledger/invoices/<id>` that it is stored exactly as entered (both photo rows, in page order), that the blank-quantity line's total equals its unit price, and that the displayed invoice total equals the hand-computed sum of its lines.

### Tests for User Story 1 (write FIRST, ensure they FAIL) ⚠️

- [x] T005 [P] [US1] Create backend/tests/test_service_ledger.py using the `call(fn, *args)` + ApiError pattern from backend/tests/test_service_infra.py — supplier create (name stored; blank name → `نام تأمین‌کننده خالی است`; duplicate stripped name → `این تأمین‌کننده قبلاً ثبت شده است`), invoice create (unknown supplier → 404 `تأمین‌کننده یافت نشد`; invalid date → 400 `تاریخ معتبر نیست`; missing watch_name → 400 `نام ساعت را وارد کنید`; blank and 0 quantity stored as 1; zero-line invoice allowed with totals 0; **zero-photo** invoice allowed (`images` omitted ⇒ no `LedgerInvoiceImage` rows — the explicit no-photo case); a 3-entry `images` array ⇒ 3 image rows with `order` 0/1/2 in submitted order, and a blank/non-string entry ⇒ 400 `عکس معتبر نیست` with no partial rows; `line_total = quantity * unit_price` and invoice `total_amount` equal hand-computed sums on a mixed-quantity fixture including a blank-quantity line)
- [x] T006 [P] [US1] Create backend/tests/test_compat_ledger.py using Django's test client, pattern of backend/tests/test_compat_contract.py — `POST /api/ledger/suppliers` returns the `{ok, supplier}` envelope and `POST /api/ledger/invoices` returns `{ok, invoice}` with the full detail object (lines + computed totals + the `images` array — a POST with `images` omitted or `[]` ⇒ `[]`, a 2-photo POST ⇒ the two filenames in submitted order); validation failures return `{ok: false, error: <Persian message>}` with the matching HTTP status; assert none of these payloads leak a `detail` key

### Implementation for User Story 1

- [x] T007 [US1] Implement backend/inventory/api/services/ledger.py — `create_supplier(payload)` (strip name, exact-stripped-name duplicate check → Persian ApiError), `rename_supplier(supplier, payload)` (same validations excluding the supplier itself), `create_invoice(payload)` (supplier must exist → 404 `تأمین‌کننده یافت نشد`; `purchase_date` via `_parse_iso_or_raise` from .common; `images` an optional ordered array of uploaded filenames (one per physical page) — one `LedgerInvoiceImage` row per entry with `order` = array position; blank/non-string entry ⇒ 400 `عکس معتبر نیست`; omitted/`[]` ⇒ zero photos; normalize every line: `watch_name` required, `quantity = to_int(raw) or 1`, `unit_price = max(0.0, to_float(raw))`; create invoice + lines in one `transaction.atomic()`), plus `update_invoice(invoice, payload)` (full-replace in one `transaction.atomic()`: `purchase_date` revalidated; `lines` present ⇒ replace all line rows in submitted order; `images` present ⇒ drop all image rows, recreate one row per entry in order, and `remove_image` every file no longer referenced; omitted keys ⇒ keep current values — the PUT endpoint registered in T008 and the US3 inline editor both build on this) and `delete_supplier(supplier)` (cascade invoices + lines + image rows, `remove_image` on every photo file) / `delete_invoice(invoice)` (same for one invoice) so US3 has its editing/deletion primitives; import ONLY the ledger models, inventory.jalali, inventory.utils (`clean, to_int, to_float, remove_image`), and .common (SC-004); re-export the new public names from backend/inventory/api/services/__init__.py
- [x] T008 [US1] Implement backend/inventory/api/compat/ledger.py — `api_ledger_suppliers` (GET → `{ok, items}` ordered by name asc with invoice_count; POST → `{ok, supplier}`), `api_ledger_supplier_detail` (PUT rename → `{ok, supplier}`; DELETE → `{ok}`), `api_ledger_invoices` (GET `?supplier_id=N` → summary items ordered purchase_date desc then -id with computed totals only, 404 `یافت نشد` for unknown supplier; POST → `{ok, invoice}` full detail), `api_ledger_invoice_detail` (GET → `{ok, invoice}` with lines + the `images` array; PUT → full-replace via `update_invoice`, `{ok, invoice}`; DELETE), all through `_ok`/`_fail`/`_guard`/`_body` per contracts/ledger-api.md §1–§9; re-export from backend/inventory/api/compat/__init__.py and register all four ledger routes plus the `/ledger` page route in backend/tikotime/urls.py (depends on T007, T009)
- [x] T009 [P] [US1] Add `ledger_page(request)` to backend/inventory/views/pages.py (render "ledger.html" with `page_ctx(request, "ledger")`, exactly like the other page shells) and the "حساب معین" nav item in frontend/templates/base.html immediately after the "پرداخت‌ها" link and before "تنظیمات و پشتیبان" (FR-001, SC-001), with a receipt/document-style SVG icon consistent with the sidebar
- [x] T010 [P] [US1] Create frontend/templates/ledger.html following the payments.html conventions — topbar (title "حساب معین" + "تأمین‌کننده‌ی جدید" primary button), accordion list container, empty-state block (with add-supplier control), and the modals: supplier add/rename (single name input), invoice add (date input with `data-jalali-today`, a multi-photo block — one `.img-upload` per page plus an add-photo control, per-photo remove, and up/down reorder buttons, line-items table with add-row control, save foot button), a full-size image-view modal, and invoice/supplier delete-confirmation modals — every modal with `data-close-modal` close buttons
- [x] T011 [US1] Implement the core of frontend/static/js/ledger.js — load suppliers from `/api/ledger/suppliers` and render the accordion list; add-supplier modal flow (POST, refresh list, toast); add-invoice flow: auto-expand the target supplier, Jalali date through the existing datepicker, each photo through the existing `setupImageUpload` (`POST /api/upload` per page, store each returned `path`, in page order), line-items table (watch name / reference / quantity / unit price with live per-line + invoice total display via `faMoney`), and save via `POST /api/ledger/invoices` with the full line list + the ordered `images` array (blank quantity submitted as-is — the service normalizes it); refresh the supplier's invoice list after save (depends on T008, T010)
- [x] T012 [P] [US1] Add ledger styles to frontend/static/css/app.css — accordion supplier header rows, indented invoice sub-rows (first-photo thumbnail + "+N" count badge + date + computed total + edit/delete controls layout), expand/collapse affordance, and empty-state styling — consistent with the existing `.glass`/`entity-card` conventions; long supplier/watch names must wrap or truncate without breaking the row (edge case "Long names")

**Checkpoint**: US1 MVP works end-to-end — the "حساب معین" page is reachable from the nav in one click, and a supplier + invoice (date, optional photo, line items, computed totals) can be recorded and read back; full suite green.

---

## Phase 4: User Story 2 - Browse the ledger as an accordion (Priority: P1)

**Goal**: Suppliers listed; clicking one expands it in place (others collapse) showing its invoices — first-photo thumbnail (+N count badge for the remaining pages) or empty placeholder, Jalali purchase date, computed grand total, edit/delete controls; clicking an invoice row opens the detail modal (all of the invoice's photos, date, line table, total quantity + total amount); thumbnail click opens the first photo full-size, and each gallery photo opens individually.

**Independent Test**: Seed one supplier with two invoices (one with two photos, one without; one with multiple lines); open /ledger, expand the supplier, verify each invoice row's fields (first-photo thumbnail + "+1" badge on the two-page invoice), open the detail modal, and verify the line-item table and both totals match hand-computed values; verify clicking the thumbnail opens the first photo full-size and each gallery photo opens individually.

### Tests for User Story 2

- [x] T013 [P] [US2] Append read-side contract tests to backend/tests/test_compat_ledger.py — `GET /api/ledger/suppliers` ordered by name with `invoice_count`; `GET /api/ledger/invoices?supplier_id=N` returns summary items (no `lines` key) ordered purchase_date desc then -id with `total_amount`/`total_quantity` equal to hand-computed values and each item carrying its ordered `images` array (`[]` when the invoice has no photos), a 404 `یافت نشد` envelope for an unknown supplier, and an empty `items` list for a supplier with no invoices; `GET /api/ledger/invoices/<id>` returns the full detail with its ordered `images` array, per-line `line_total` and invoice `total_quantity`/`total_amount` matching hand-computed values on a mixed-quantity fixture including blank quantities (SC-003), and 404 `یافت نشد` for an unknown invoice

### Implementation for User Story 2

- [x] T014 [US2] Implement accordion browsing in frontend/static/js/ledger.js — exactly one expanded supplier at a time: clicking a supplier row expands it in place to its invoice list (lazy `GET /api/ledger/invoices?supplier_id=N`; the add-invoice control in the expanded block is created by T011), collapses any previously expanded supplier, and clicking a different supplier shows that supplier's invoices instead; each invoice row shows the first-photo thumbnail (with a "+N" badge for the remaining pages) or an empty placeholder, `purchase_date_fa`, and `total_amount_display` (FR-011, FR-008)
- [x] T015 [US2] Implement the invoice detail modal + image viewing in frontend/static/js/ledger.js and frontend/templates/ledger.html — clicking an invoice row anywhere except its edit/delete buttons loads `GET /api/ledger/invoices/<id>` into the detail modal: a photo gallery (all of the invoice's photos as thumbnails in page order — empty when `images` is `[]`), the purchase date, the line-items table (watch name, reference, quantity, unit price, line total), and under the table the total quantity and the total invoice amount — both computed; clicking the list thumbnail opens the first photo, and clicking any gallery photo in the modal opens that photo, each at full size in the image-view modal over `/data/images/<fname>` (FR-010, FR-008)
- [x] T016 [P] [US2] Style the detail modal (incl. its photo gallery row), the "+N" count badge, line-items table, totals row, and full-size image-view modal in frontend/static/css/app.css (reuse the existing modal/table conventions; table fits inside the modal, totals row visually distinct from the lines)

**Checkpoint**: US1 + US2 both work — records can be recorded AND browsed via the accordion + detail view; full suite green.

---

## Phase 5: User Story 3 - Edit and delete ledger records (Priority: P2)

**Goal**: Rename a supplier; fully edit any invoice from within the detail view (date, photos — add/reorder/remove — add/edit/remove lines) in a single flow; delete any invoice; delete a supplier and its entire history.

**Independent Test**: Rename a supplier and verify the change everywhere; in the detail modal, add, edit, and delete a line item on an existing invoice and verify the totals recompute; delete an invoice and verify its lines are gone; delete a supplier and verify all its invoices are gone.

### Tests for User Story 3

- [x] T017 [P] [US3] Append service tests to backend/tests/test_service_ledger.py — `update_invoice` full-replace: change the date, add/remove/reorder/clear the photo set (orphaned files removed via `remove_image`; `images: []` clears all photos and removes their files), add a line, edit a line's quantity or price, remove a line → all changes stored and `total_quantity`/`total_amount` recomputed from the new lines; `delete_invoice` removes the invoice, all its lines, and all its image rows (+ their files); `rename_supplier` changes the name visible on all of its invoices; `delete_supplier` leaves 0 invoices, 0 line items, 0 image rows, and 0 photo files behind (SC-002)
- [x] T018 [P] [US3] Append compat tests to backend/tests/test_compat_ledger.py — `PUT /api/ledger/suppliers/<id>` renames (blank / duplicate-of-another → 400 envelopes) and returns `{ok, supplier}`; `PUT /api/ledger/invoices/<id>` replaces the line set, the date, and the photo set (ordered `images` array, full-replace — add/reorder/remove/clear) with recomputed totals in the response (`{ok, invoice}`); `DELETE /api/ledger/invoices/<id>` and `DELETE /api/ledger/suppliers/<id>` return `{ok: true}` and cascade (0 orphans); unknown ids return 404 `یافت نشد`

### Implementation for User Story 3

- [x] T019 [US3] Implement the inline invoice editor in frontend/static/js/ledger.js (inside the US2 detail modal) — the date field (existing Jalali input), photo editing via the multi-photo block (add a page photo through the same `/api/upload` flow, remove one, up/down reorder), add/edit/remove of line-item rows, live re-computation of the totals row, and a single save that `PUT /api/ledger/invoices/<id>` with the full current line list + the ordered `images` array (full-replace semantics per contracts/ledger-api.md §8); after save, refresh the accordion's invoice row (new total + first-photo thumbnail/badge) and the modal contents (FR-009)
- [x] T020 [US3] Implement rename + destructive deletes in frontend/static/js/ledger.js and frontend/templates/ledger.html — supplier rename through the supplier modal (reused in edit mode, `PUT /api/ledger/suppliers/<id>`); delete-invoice and delete-supplier confirmation modals following the payments page's Persian confirm pattern (warning that deleting a supplier removes all its invoices); wire both to the DELETE endpoints; after any delete, refresh the open lists/modals so no deleted row remains visible (edge case "Deleting while viewing")

**Checkpoint**: All P1/P2 stories work independently — record, browse, and edit/delete the ledger; full suite green.

---

## Phase 6: User Story 4 - The ledger is wiped by Clear Database (Priority: P3)

**Goal**: The existing Clear Database action (explicit, temporary user decision — FR-014) also removes every ledger supplier, invoice, line item, and invoice photo, while the site logo is kept and the automatic pre-clear backup is still taken first.

**Independent Test**: Seed ledger suppliers, invoices with photos, and line items; run Clear Database; verify 0 ledger records and 0 invoice photos remain, the site logo is intact, and a `pre_clear_*.db` backup was created first.

### Tests for User Story 4

- [x] T021 [P] [US4] Append a clear-database test to backend/tests/test_compat_ledger.py — with ledger suppliers/invoices/line items/invoice images + invoice photos (including a multi-page invoice) in IMG_DIR and a site-icon file in place: `clear_database()` (inventory/dbhelpers.py) returns counts that include the four new tables, leaves 0 ledger suppliers/invoices/line items/invoice images, removes every invoice photo while keeping the site-logo file, and a `pre_clear_*.db` now exists in the backup dir (SC-005); products/sales/payments/repairs/tracking still wipe exactly as before

### Implementation for User Story 4

- [x] T022 [US4] Add `"ledger_suppliers", "ledger_invoices", "ledger_lines", "ledger_invoice_images"` to `_CLEAR_TABLES` in backend/inventory/dbhelpers.py and make the `sqlite_sequence` reset inside `clear_database()` build its `IN (…)` placeholders from the tuple length instead of the hardcoded 5 (research.md §8 pitfall) — no other change: `count_records()`, the transactional wipe, `VACUUM`, and `_remove_orphaned_images(site_icon)` already cover the rest (FR-014)

**Checkpoint**: US4 works — one Clear Database run wipes ledger records + photos, keeps the logo, and still takes its pre-clear backup; full suite green.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Edge cases, independence verification, docs, and the final green gate.

- [x] T023 [P] Update the "امکانات" feature list in README.md with a "حساب معین" (supplier purchase ledger) entry in the existing bullet style, noting it is a fully independent archival subsystem
- [x] T024 [P] Run the independence audit (SC-004): inspect backend/inventory/api/services/ledger.py, backend/inventory/api/compat/ledger.py, and the ledger functions in backend/inventory/utils.py, confirming 0 imports or references to product/sale/payment/repair/tracking/settings/report modules or the product form's supplier text field, and that dashboard/report code is untouched
- [x] T025 Verify the spec's edge cases end-to-end in the app (frontend/static/js/ledger.js + frontend/templates/ledger.html): a zero-line invoice shows totals of 0 and remains fully editable; a zero-photo invoice shows the empty placeholder and still accepts photos later; a multi-page invoice shows its first photo + "+N" badge on the row and the full gallery (each photo full-size on click) in the detail view; multiple invoices sharing a purchase date render as separate rows; long supplier/watch names wrap/truncate without breaking the layout; an invoice with a large line set (e.g. 20 lines) is entered and saved without any cap (line items are unbounded); an empty ledger shows the empty-state list with the add-supplier control; deleting while a list/view is open refreshes so nothing deleted remains visible
- [x] T026 Run the complete automated suite (`cd backend && ../.venv/bin/python manage.py test`): the 167 pre-existing tests plus all new ledger tests pass with 0 failures (FR-016, SC-006)
- [x] T027 Walk through quickstart.md end-to-end — migrate on a fresh DB, runserver, and manual walkthrough steps 1–9 (incl. Clear Database and restart persistence) — confirming every documented expectation holds

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — run first as the baseline gate.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational only — no dependency on other stories.
- **User Story 2 (Phase 4)**: Depends on US1 (page shell, `ledger.js` core, and the read endpoints all exist).
- **User Story 3 (Phase 5)**: Depends on US2 (the detail modal must exist to host the inline editor).
- **User Story 4 (Phase 6)**: Depends on Foundational only (the tables must exist) — can run in parallel with US1–US3; re-run T021 after US1–US3 land to confirm the wipe still covers everything.
- **Polish (Phase 7)**: Depends on all desired user stories being complete; T026/T027 are the final gate.

### User Story Dependencies

- **US1 (P1) 🎯 MVP**: start after Foundational — independently testable on its own.
- **US2 (P1)**: start after US1 — the accordion and detail view build on US1's page + API.
- **US3 (P2)**: start after US2 — editing happens inside US2's detail modal.
- **US4 (P3)**: start after Foundational — the one story with no UI dependency.

### Within Each User Story

- Tests (T005/T006, T013, T017/T018, T021) MUST be written and FAIL before the story's implementation. (T017/T018 guard the US3 edit/delete surface; the `update_invoice` service + PUT primitive already ship with US1's T007/T008, so these tests may be green on their first run — they still must exist before T019/T020.)
- Services before compat adapters; compat adapters before the UI that calls them.
- Markup (`ledger.html`) before the JS that binds to its ids; CSS is independent ([P]).

### Cross-file conflict note

`backend/tikotime/urls.py` is edited by T008 only (it registers all four ledger API routes AND the `/ledger` page route); `views/pages.py` + `base.html` belong to T009 — keep that split to preserve the [P] markings. `frontend/static/js/ledger.js` is shared across US1/US2/US3 — run its tasks sequentially (never two `ledger.js` tasks in parallel).

### Parallel Opportunities

- **Phase 2**: T004 ∥ (T002 → T003) — different files.
- **Phase 3 (US1)**: T005 ∥ T006 (tests, two new files) → then T007 ∥ T009 ∥ T010 ∥ T012 (all different files) → T008 (after T007 + T009) → T011 (after T008 + T010).
- **Phase 4 (US2)**: T013 ∥ T014/T015 (test file vs frontend files); T016 ∥ everything.
- **Phase 5 (US3)**: T017 ∥ T018 (tests) → T019 → T020 (shared `ledger.js`/`ledger.html`).
- **Phase 6 (US4)**: T021 ∥ T022.
- **Phase 7**: T023 ∥ T024; then T025 → T026 → T027 in order.

---

## Parallel Example: User Story 1

```bash
# 1) All tests for US1 together (must FAIL before implementation):
Task: "Service tests for supplier/invoice create in backend/tests/test_service_ledger.py"   # T005
Task: "Compat contract tests for the POST endpoints in backend/tests/test_compat_ledger.py" # T006

# 2) All independent implementation files together:
Task: "Implement backend/inventory/api/services/ledger.py + services/__init__.py re-exports" # T007
Task: "Add ledger_page + the 'حساب معین' nav item (views/pages.py, base.html)"             # T009
Task: "Create frontend/templates/ledger.html (page shell + modals)"                         # T010
Task: "Add ledger accordion styles to frontend/static/css/app.css"                          # T012

# 3) Then the dependent steps:
Task: "Implement backend/inventory/api/compat/ledger.py + register routes in urls.py"       # T008 (after T007, T009)
Task: "Implement the frontend/static/js/ledger.js core (accordion + add flows)"             # T011 (after T008, T010)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup — baseline 167 green (T001).
2. Phase 2: Foundational — models, migration, serializers (T002–T004). **CRITICAL — blocks all stories.**
3. Phase 3: US1 — tests first (T005/T006), then services → adapters → page → UI (T007–T012).
4. **STOP and VALIDATE**: run US1's Independent Test end-to-end (record a paper invoice via the app and the API) and confirm the full suite is green. This is the shippable MVP.

### Incremental Delivery

5. Phase 4: US2 — read-side contract tests (T013), then accordion + detail modal + full-size photo (T014–T016). Validate with US2's Independent Test; suite green.
6. Phase 5: US3 — edit/delete tests (T017/T018), then inline editor + rename/deletes (T019/T020). Validate; suite green.
7. Phase 6: US4 — clear-database test (T021) + the `_CLEAR_TABLES` change (T022). Validate; suite green.
8. Phase 7: Polish — README, SC-004 audit, edge cases, the full-suite gate (T026), and the quickstart E2E (T027).

### Commit Discipline (constitution rule 7)

One small, reversible commit per logical slice, matching the plan.md commit sequence exactly: (1) models + migration `0009_ledger` (all four tables), (2) utils serializers, (3) services/ledger, (4) compat/ledger + urls registration, (5) dbhelpers clear-list, (6) page shell + nav, (7) ledger.html + ledger.js + CSS, (8) tests — test files may land together with the story slice they verify. Every commit leaves `manage.py test` 100% green so any step can be reverted independently.