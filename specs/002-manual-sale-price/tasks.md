# Tasks: Manual Sale Price at Sale Time (Spec-002)

**Input**: Design documents from `/specs/002-manual-sale-price/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/api-shape.md, quickstart.md

**Tests**: explicitly requested (FR-015/FR-016) — the existing suite in `backend/tests/` is updated **in place**; new/updated tests must FAIL before the implementation task they verify.

**Constitution note**: rules 1 & 3 are documented exemptions for this feature (see plan.md → Constitution Check); every phase lands as a small commit (rule 7). Migrations are the **last** step (research D8).

## Phase 1: Setup

**Purpose**: Confirm the pre-change baseline is green before any test edits.

- [X] T001 Baseline gate: run `cd backend && python manage.py check` (expect 0 issues) and `cd backend && python manage.py test` (expect 153 tests green); record the counts in the commit message of the first implementation commit. No file changes.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared test fixtures — every story's test task builds on these.

**⚠️ CRITICAL**: All story test tasks assume the fixtures below.

- [X] T002 [P] Update `backend/tests/helpers.py`: remove the `final_price` kwarg from the sale fixture (keep `sale_price`, `profit`); stop setting `sale_price` on the product fixture (cost price only). No app-code changes; run the suite — if removing a fixture default breaks an unrelated assertion, keep that default until its owning story task removes it.

**Checkpoint**: Foundation ready — user story implementation can begin.

---

## Phase 3: User Story 1 - Record a sale with a price I actually type (Priority: P1) 🎯 MVP

**Goal**: Both sale forms (Sold page + Products page quick modal) require one manually entered price; no discount concept anywhere in the sale flow; profit = price − cost; payment checks run against the entered price (FR-003…FR-006).

**Independent Test**: Service-level: `create_sale` with a typed price stores exactly that price with `profit = price − purchase_price`; `create_sale` without a price raises the Persian error "قیمت فروش را وارد کنید" and saves nothing. UI: both forms have exactly one price input.

### Tests for User Story 1 (write FIRST — they must fail)

- [X] T003 [P] [US1] Rewrite the discount tests in `backend/tests/test_service_sales.py`: `create_sale` ignores `discount_price` in the payload (unknown key; stored price = entered `sale_price`); missing/blank/zero price raises an error containing `قیمت فروش را وارد کنید`; paid total > entered price raises the overpayment error naming the entered price (`fa_money`); cash ("نقدی") sale with no amounts → fully paid at the entered price and settled; `update_sale` with a new price recomputes `profit = new price − cost` and validates payment sums against the new price; editing a "بیعانه" (deposit) sale keeps already-stored receipt amounts unchanged.
- [X] T004 [P] [US1] Update `backend/tests/test_service_infra.py` and `backend/tests/test_services_misc.py`: remove/adjust every assertion referencing `final_price`/`discount_price` to the entered-price behavior.
- [X] T005 [P] [US1] Update `backend/tests/test_utils.py` (sale section): `sale_dict` output has no `final_price` / `final_price_display` keys; `sale_price_display` = `fa_money(sale.sale_price)`.
- [X] T006 [P] [US1] Update the sale parts of `backend/tests/test_legacy_api_baseline.py` and `backend/tests/test_compat_contract.py`: sale items carry no `final_price` key; the sales-list summary key is `total_sale` (= Σ entered `sale_price`), not `total_final`.

### Implementation for User Story 1

- [X] T007 [US1] `backend/inventory/api/services/sales.py` — `create_sale` (line ~94): delete the discount/final-price logic (lines ~111–113); require `to_float(payload["sale_price"]) > 0` else raise the Persian error `قیمت فروش را وارد کنید`; run all paid-total caps against `sale_price` (~143–153); cash default pays out at `sale_price` (~153); `profit = sale_price − (product.purchase_price or 0)` (~157); stop saving `final_price` (~165) and set the receipt `total_amount=sale_price` (~174). In `update_sale` (~185): delete the discount-alias block (~197–210); enforce new price > 0; caps/profit against the new price (~218–239).
- [X] T008 [US1] `backend/inventory/utils.py` — `sale_dict` (~149): drop the `final_price` and `final_price_display` keys (~162, ~180).
- [X] T009 [US1] `backend/inventory/api/compat/sales.py` — `api_sales` (~14): rename summary key `"total_final"` → `"total_sale"` and sum the entered `sale_price` (~30).
- [X] T010 [US1] `backend/inventory/api/services/calendar.py`: every item's price / `price_display` uses the entered `sale_price` (remove the `final_price` fallback).
- [X] T011 [US1] `frontend/templates/sold.html`: make the sale-price input editable + `required`; remove the `discount_price` input and its hint.
- [X] T012 [US1] `frontend/static/js/sold.js`: submit the typed `sale_price` (drop all `discount_price` reads); summary chip `summary.total_final` → `summary.total_sale` (~line 49); remove every `final_price` display — list price cells and the detail panel's `قیمت نهایی (با تخفیف)` / `میزان تخفیف` rows (keep the `قیمت فروش` and `قیمت پرداخت‌شده` rows).
- [X] T013 [US1] `frontend/templates/products.html` — quick "record sale" modal: replace the read-only pre-set price field and the required discount input with a single editable, required `sale_price` input (same pattern as T011) — spec scenario 5.
- [X] T014 [US1] `frontend/static/js/products.js`: quick-sale submit sends the entered `sale_price`; remove `discount_price` handling and any pre-set-price defaulting.
- [X] T015 [US1] Gate: `cd backend && python manage.py test` fully green; commit `feat(sale): manual required sale price, discount concept removed (US1)`.

**Checkpoint**: MVP — a sale can only be recorded with a manually typed price from either form.

---

## Phase 4: User Story 2 - Add a product with only a cost price (Priority: P1)

**Goal**: The product side of the same change — no sale-price field in forms, payloads, dicts, sort, list, or import/export (FR-001, FR-002).

**Independent Test**: The Add Product form has no sale-price input; a product created with only a cost price saves, and every product read (API item, list, export) exposes cost price and no product-level sale price.

### Tests for User Story 2 (write FIRST — they must fail)

- [X] T016 [P] [US2] Update `backend/tests/test_service_products.py`: `create_product`/`update_product` ignore a `sale_price` payload key (stored attributes unaffected); `product_queryset` with `sort=sale_price` falls back to the default sort (key no longer in the map); duplicate-code checks unchanged.
- [X] T017 [P] [US2] Update `backend/tests/test_utils.py` (product section): `product_dict` emits no `sale_price`, `sale_price_display`, `profit_per_unit(_display)`, `total_sale_value(_display)` keys; `total_value` = purchase cost.
- [X] T018 [P] [US2] Update `backend/tests/test_legacy_api_baseline.py` (product parts): product items carry no sale-price keys.

### Implementation for User Story 2

- [X] T019 [US2] `backend/inventory/api/services/products.py`: remove `"sale_price"` from `_PRODUCT_SORT` (~line 20) and the payload-values list (~line 30); `_product_values` (~line 83) stops reading `sale_price` (~line 109); create/update (~132/142) ignore the key.
- [X] T020 [US2] `backend/inventory/utils.py` — `product_dict` (~98): remove the sale-price, per-unit profit, and total-sale-value keys (~107, ~120, ~122, ~126); keep `total_value` = purchase cost.
- [X] T021 [US2] `frontend/templates/products.html`: remove the sale-price input from the add/edit product form; remove the sale-price column from the product list; remove the `قیمت فروش` sort option.
- [X] T022 [US2] `frontend/static/js/products.js`: drop sale-price reads/writes in the add/edit form payloads, list row rendering, and sort control.
- [X] T023 [US2] `backend/inventory/excel_io.py`: remove `قیمت فروش` from the product export/import headers and rows (~lines 17, 22, 205, 213); `import_products` (~281) silently drops a legacy `قیمت فروش` column when present in an old file (~316/341 — stop forwarding the key to product values).
- [X] T024 [US2] Gate: `cd backend && python manage.py test` fully green; commit `feat(product): products store cost price only (US2)`.

**Checkpoint**: Both P1 stories done — the pre-set price is gone from both ends of the flow.

---

## Phase 5: User Story 3 - Dashboard numbers reflect what actually sold (Priority: P2)

**Goal**: The two top dashboard boxes come from actual `Sale` rows — total sale value all-time, profit current Jalali year only (FR-008, FR-009, research D3).

**Independent Test**: Seed known products (some unsold, some sold) and sales spanning two Jalali years; the two boxes equal hand-computed sums over actual Sale records with the correct filters.

### Tests for User Story 3 (write FIRST — they must fail)

- [X] T025 [US3] Update `backend/tests/test_dbhelpers_reports.py` (dashboard section): unsold stock with no sales → `total_sale_value` = 0 (no projection); mixed current-year/earlier-year sales → `total_profit_value` = Σ(price − cost) of **current Jalali-year** sales only; `sold_revenue` = Σ entered `sale_price`.

### Implementation for User Story 3

- [X] T026 [US3] `backend/inventory/reports.py` — `get_dashboard_stats` (~14): `total_sale_value` → `Sum(Sale.sale_price)` (all-time, replacing the product aggregate at ~17); `total_profit_value` → `Sum(F("sale_price") − F("purchase_price"))` over sales in the current Jalali year (reuse the existing Jalali year-bound math used by `get_monthly_activity`, replacing the product aggregate at ~19); `sold_revenue` → `Sum(Sale.sale_price)` (~26).
- [X] T027 [US3] `frontend/templates/dashboard.html`: stat-box labels — `ارزش انبار (بالقوه)` → `ارزش فروش` and `سود بالقوه` → `سود فروش امسال` (subtext `از فروش‌های جاری سال`); wire boxes to the unchanged keys `total_sale_value` / `total_profit_value`.
- [X] T028 [US3] Gate: suite green; commit `feat(reports): dashboard boxes from actual sales (US3)`.

**Checkpoint**: Dashboard shows real business numbers.

---

## Phase 6: User Story 4 - Brand table shows what each brand actually earned (Priority: P2)

**Goal**: The per-brand table's sale-value/profit columns come from that brand's actual `Sale` rows; stock columns unchanged (FR-010, research D3/D4).

**Independent Test**: Brand A with sold + unsold products → sale value/profit equal hand-computed sums over A's Sale rows; brand B with stock but zero sales → 0/0 with correct stock count/value.

### Tests for User Story 4 (write FIRST — they must fail)

- [X] T029 [US4] Update `backend/tests/test_dbhelpers_reports.py` (brand section): brand with sold + unsold → `sale_value` = Σ sale prices of its sales and `profit` = Σ(price − cost) over the same sales; zero-sales brand → `sale_value`/`profit` = 0 with stock count/value unchanged.

### Implementation for User Story 4

- [X] T030 [US4] `backend/inventory/reports.py` — `get_brand_breakdown` (~115): replace the product aggregates (~128/130) — `sale_value` = Σ `Sale.sale_price` and `profit` = Σ(`Sale.sale_price` − `Sale.purchase_price`) over sales whose product belongs to that brand; the `count`/`value` (unsold stock) columns keep their current queries.
- [X] T031 [US4] `frontend/templates/dashboard.html` (brand section): section title `انبار بر اساس برند` → `انبار و فروش بر اساس برند`; column `سود بالقوه` → `سود فروش`; `جمع ارزش فروش` text stays (now accurate).
- [X] T032 [US4] Gate: suite green; commit `feat(reports): brand table from actual sales (US4)`.

**Checkpoint**: Per-supplier performance view is truthful.

---

## Phase 7: User Story 5 - Activity chart shows in-person vs. online volume (Priority: P3)

**Goal**: Two new per-month count series (in-person / online) in the 12-month chart; existing series unchanged (FR-011, research D7).

**Independent Test**: Seed in-person and online sales across known months; the two new series equal hand counts per month and the pre-existing keys render identically.

### Tests for User Story 5 (write FIRST — they must fail)

- [X] T033 [US5] Update `backend/tests/test_dbhelpers_reports.py` (monthly section): every month object includes `person_count` and `online_count` matching the actual per-type sale counts for that month; `revenue` = Σ entered `sale_price`; future months are 0; all pre-existing keys unchanged.

### Implementation for User Story 5

- [X] T034 [US5] `backend/inventory/reports.py` — `get_monthly_activity` (~50): read `sale_price` instead of `final_price` from the sales aggregation (~76/90) and add per-month `person_count` / `online_count` (count of sales by `sale_type` in each month).
- [X] T035 [US5] `frontend/templates/dashboard.html` (inline chart script): two new thin **dashed** lines with no area fill, on an independent count scale mapped into the bottom ~35% band with its own rounded max; distinct colors from the money series; two tooltip rows `فروش حضوری` / `فروش آنلاین`; a small legend chip row covering all five series; existing series untouched (research D7).
- [X] T036 [US5] Gate: suite green; commit `feat(reports): chart in-person/online count series (US5)`.

**Checkpoint**: Channel volume visible in the activity chart.

---

## Phase 8: User Story 6 - Every sale view shows one price: the one I entered (Priority: P3)

**Goal**: Final consumer-surface cleanup — Sold list sort/columns, calendar, dashboard recent sales, sales export — no discount/final-price remnant anywhere (FR-012…FR-014, SC-006).

**Independent Test**: With historical data (including old discounted sales) open the Sold list, calendar, dashboard, and the sales export: only the entered price shows, payment breakdowns remain, zero discount remnants.

### Tests for User Story 6 (write FIRST — they must fail)

- [X] T037 [P] [US6] Update `backend/tests/test_calendar_sales.py`: calendar sale items expose the entered price (no `final_price` key/fallback); paid-cash / POS / card-to-card breakdown unchanged.

### Implementation for User Story 6

- [X] T038 [P] [US6] `backend/inventory/excel_io.py` — `export_sales` (~133): drop the `قیمت نهایی` header (~line 42) and the fallback row value (~138/146) → columns are purchase price, entered sale price, profit.
- [X] T039 [P] [US6] `frontend/static/js/calendar.js`: replace the `final_price` fallback with the entered `sale_price` (event price and per-day totals).
- [X] T040 [P] [US6] `frontend/templates/sold.html` + `frontend/static/js/sold.js`: remove the `قیمت نهایی` sort option and any remaining discount/final-price column or detail text; the list shows only the entered sale price.
- [X] T041 [P] [US6] `frontend/templates/dashboard.html` (recent-sales table): render the entered `sale_price` only; drop any `final_price` key usage.
- [X] T042 [US6] Gate: suite green; remnant check `grep -rn 'final_price\|discount_price' backend/inventory frontend` must hit only `backend/inventory/migrations/0001_initial.py` and `__pycache__` files; commit `feat(ui): single entered price on every sale surface (US6)`.

**Checkpoint**: All six stories independently functional — no code path still reads the removed price.

---

## Phase 9: Polish & Cross-Cutting Concerns (schema removal — LAST)

**Purpose**: Drop the two now-dead columns and prove the real database migrates losslessly (FR-001, FR-007, SC-005, SC-007).

- [X] T043 [P] `backend/inventory/models.py`: remove `Sale.final_price` (line ~51) and `Product.sale_price` (line ~43); run `cd backend && python manage.py makemigrations inventory` generating `0007_remove_sale_final_price` and `0008_remove_product_sale_price` (one `RemoveField` each); run the full test suite — test DBs rebuild through migrations, so this proves no code still reads the removed columns (spec edge case "no remaining readers").
- [X] T044 Migrate the real local DB: `cp db/db.sqlite3 db/backups/db.sqlite3.pre-spec002.bak` then `cd backend && python manage.py migrate` (expect exactly 0007/0008 to apply); verify before/after: product rows keep `purchase_price`, sale rows keep `sale_price`/`profit`/payments/dates/customer; app starts and every page renders.
- [X] T045 Final gate (FR-016/SC-007): `cd backend && python manage.py check` → 0 issues; `python manage.py test` → 100% green; walk `specs/002-manual-sale-price/quickstart.md` manual steps 1–8 end-to-end on the real app; commit `chore(schema): drop Sale.final_price and Product.sale_price (migrations 0007/0008)`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; T002 blocks every test task below.
- **User stories (Phases 3–8)**: sequential in priority order — US2, US3/4/5, and US6 all share files with their predecessors (`utils.py`, `products.html`, `products.js`, `test_utils.py`, `test_legacy_api_baseline.py`, `reports.py`, `dashboard.html`, `test_dbhelpers_reports.py`), so phases do NOT run in parallel.
- **Polish (Phase 9)**: depends on ALL story phases — no code may still read the removed fields before T043 (spec edge case).

### User Story Dependencies

- **US1 (P1)**: after Foundational — no dependency on other stories.
- **US2 (P1)**: after US1 (shares `utils.py`, `products.html`, `products.js`, two test files) — otherwise independent.
- **US3 (P2)**: after US2; reads only `Sale` rows, so independent of US2's product side, but shares the test/runner flow.
- **US4 (P2)**: after US3 (same `reports.py` + `test_dbhelpers_reports.py`).
- **US5 (P3)**: after US4 (same `reports.py` + `dashboard.html` chart block).
- **US6 (P3)**: after US5 (final `dashboard.html` edit; also the last UI cleanup before the remnant-grep gate).

### Within Each Story

- Tests written and confirmed failing → implementation → gate task (suite green + commit).
- Service/payload changes before template/JS changes (contract flow: backend shape first, then the UI that consumes it).

### Parallel Opportunities

- **US1**: T003–T006 (four test files, disjoint) — write in parallel before touching app code.
- **US2**: T016–T018 (three test files, disjoint).
- **US6**: T037–T041 (five tasks, all disjoint files: `test_calendar_sales.py`, `excel_io.py`, `calendar.js`, `sold.html`+`sold.js`, `dashboard.html`).
- No [P] between phases — shared files force the order above.

---

## Parallel Example: User Story 1

```text
Write first (4 parallel test tasks, disjoint files):
Task T003: "Update backend/tests/test_service_sales.py …"
Task T004: "Update backend/tests/test_service_infra.py + test_services_misc.py …"
Task T005: "Update backend/tests/test_utils.py (sale section) …"
Task T006: "Update backend/tests/test_legacy_api_baseline.py + test_compat_contract.py (sale parts) …"

Then sequentially (backend shape → UI):
T007 → T008 → T009 → T010 → T011 → T012 → T013 → T014 → T015 (gate)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (baseline) + Phase 2 (fixtures)
2. Phase 3: US1 — the sale flow is now price-mandatory end to end (both forms, validation, profit, payments, payload shape)
3. **STOP and VALIDATE**: quickstart steps 3–4 (required price, discount gone, Persian errors, profit)
4. The app still works on the old schema (the two columns are simply unused) — fully demoable

### Incremental Delivery

1. US1 → demo (MVP)
2. + US2 → products side complete; no pre-set price anywhere
3. + US3 → real dashboard boxes
4. + US4 → real per-brand numbers
5. + US5 → channel-volume chart series
6. + US6 → zero discount remnants (grep gate)
7. Phase 9 → schema drop + final green suite; each phase is its own revertible commit (constitution rule 7)

---

## Notes

- [P] = different files, no dependency on an incomplete task; story labels map to `spec.md` user stories 1–6.
- Line numbers in tasks are anchors from the current code state (post-Spec-001) — locate by symbol name if off by a few lines.
- Historical discounted sales: their stored `sale_price`/`profit`/payments survive the column drop untouched (spec assumption — no back-fill).
- `backend/inventory/migrations/0001_initial.py` keeps its historical field definitions — the remnant-grep gate in T042/SC-006 explicitly excludes it (and `__pycache__`).
- Commit after each gate task; stop at any checkpoint to validate the story independently.
- Avoid: touching payment-receipt storage, Repair/Tracking domains, or Spec-001 file layout (out of scope per spec).
