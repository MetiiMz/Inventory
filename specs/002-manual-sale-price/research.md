# Research & Decisions: Manual Sale Price (Spec-002)

**Date**: 2026-10-03 · **Status**: complete — no open NEEDS CLARIFICATION items.

The codebase was verified line-by-line during specify/clarify, so this document records the concrete plan-level decisions the spec delegated ("agent's call", label choices, chart mechanics), each with rationale and rejected alternatives. File/function names below are current as of the `test` branch.

## D1 — Sale-price validation rule (FR-003)
- **Decision**: On create, `sale_price` is required: must parse to a number > 0 or the create fails with 400 `ApiError("قیمت فروش را وارد کنید")`, reusing the existing `to_float` helper. On update, the same check applies only when a new value is provided; omitted means keep the stored price. Both forms mark the input `required` as the first line of defense.
- **Rationale**: Spec edge cases demand rejection of blank/zero prices; the shop is paid retail — free sales are out of domain.
- **Alternatives**: allow 0 (free/gift sale) — rejected by the spec's own edge-case list.

## D2 — Historical discounted sales
- **Decision**: After `Sale.final_price` is dropped, old discounted sales display and aggregate at their stored `sale_price`; the stored per-sale `profit` stays as recorded (no retroactive recomputation).
- **Rationale**: Explicit user instruction ("only the now-redundant final_price column is dropped"); spec assumption "Historical data semantics".
- **Alternatives**: back-fill `sale_price := final_price` — rejected: destroys the entered list price; spec says stored data is preserved as-is.

## D3 — Report aggregation sources (FR-008/009/010)
- **Decision**: All "sold" aggregates compute from Sale rows: sale value = `Sum("sale_price")`; profit = `Sum(F("sale_price") − F("purchase_price"))` (Sale carries a denormalized cost snapshot). `total_profit_value` additionally filters `sale_date` to the current Jalali year using the existing `jalali_to_gregorian` month-bound math (same pattern as `get_monthly_activity`). Brand rows join Sales → `product.brand`.
- **Rationale**: FR-010 mandates (price − cost) per sale; one consistent basis across dashboard box and brand table; historical discounted rows would mix bases under `Sum("profit")`.
- **Alternatives**: `Sum("profit")` — rejected: differs from price−cost exactly for the historical discounted rows.

## D4 — Sale payload keys (FR-004/012)
- **Decision**: `sale_dict` drops `final_price` and `final_price_display` outright; the sales-list summary renames `total_final` → `total_sale` (Σ entered sale prices). The single consumer (`sold.js`) updates in the same change set.
- **Rationale**: Spec-002 is exempt from Spec-001's frozen-shape rule; constitution guarantees no second client; SC-006 demands zero code references to the removed concept.
- **Alternatives**: keep `final_price` aliased to `sale_price` for compatibility — rejected: dead twin key, invites confusion.

## D5 — Dashboard stat keys vs. label text (FR-008/009)
- **Decision**: JSON keys `total_sale_value` / `total_profit_value` keep their names (sources change to Sale rows) → views pass-through untouched; `sold_revenue` now = Σ `sale_price` (was `final_price`). Template label/sub-text changes:
  - Box 2: label `ارزش فروش کل انبار` → `ارزش فروش کل`; sub `ارزش فروش ساعت‌های موجود` → `مجموع قیمت فروش‌های ثبت‌شده`
  - Box 3: label `سود انبار (بالقوه)` → `سود فروش امسال`; sub `اگر همه‌ی موجودی به قیمت فروش فروخته شود` → `مجموع سود فروش‌های سال جلالی جاری`
- **Rationale**: Keys are plumbing, labels are user-facing; renaming labels was delegated by the user (spec Assumptions).
- **Alternatives**: rename the JSON keys — more churn, zero user-visible gain; keep old labels — now factually wrong (inventory no longer holds a sale price).

## D6 — Brand-table labels (FR-010)
- **Decision**: column `سود بالقوه` → `سود فروش`; section title `انبار بر اساس برند` → `انبار و فروش بر اساس برند`; `جمع ارزش فروش` text unchanged (now more accurate); stock columns `تعداد در انبار` / `جمع ارزش خرید` unchanged.
- **Rationale**: Parallel with D5; the user's suggested example (`سود فروش‌رفته`) signals a sold-based label; `سود فروش` is shorter and parallel.
- **Alternatives**: `سود فروش‌رفته` (user's example) — equivalent, slightly clunkier; keep old labels — rejected.

## D7 — Chart: two count series on a money chart (FR-011)
- **Decision**: Backend adds `person_count` + `online_count` to every month object (0 for future months, consistent with existing series). Frontend: two new thin **dashed** lines with no area fill, on an independent count scale mapped into the bottom ~35% band of the plot (own rounded max); distinct colors from the three money series; two extra tooltip rows (`فروش حضوری`, `فروش آنلاین`); a small legend chip row for all five series.
- **Rationale**: The current chart has one y-scale derived from money maxima (millions of toman); integer counts would render flat at zero on it. A bottom band + dashed style keeps counts legible without a full dual-axis.
- **Alternatives**: right dual axis — cluttered with 5 series; separate mini-chart — violates "in the existing chart"; normalizing counts to the money scale — misleading.

## D8 — Migrations (FR-001/007)
- **Decision**: Two migrations: `0007_remove_sale_final_price` and `0008_remove_product_sale_price` (one `RemoveField` each, generated via `makemigrations`), applied **last** — after code and tests no longer reference the fields — with a `cp db/db.sqlite3` backup taken first.
- **Rationale**: Constitution rule 7 (small revertible commits); SQLite `DROP COLUMN` preserves the remaining columns' data (SC-005); spec edge case "no remaining readers of the removed field".
- **Alternatives**: single combined migration — worse bisectability; hand SQL — loses Django migration state.

## D9 — Excel import/export (FR-014)
- **Decision**: Product export/import drop the `قیمت فروش` column/key; the sales export drops the `قیمت نهایی` column (rows become purchase, sale, profit); the importer silently ignores a legacy `قیمت فروش` column if present in an old file.
- **Rationale**: SC-006 zero remnants; previously exported files remain importable.

## D10 — Product payload & list cleanup (FR-001/002)
- **Decision**: `product_dict` drops `sale_price`, `sale_price_display`, `profit_per_unit(_display)`, `total_sale_value(_display)` (keeps `total_value` = purchase cost); the product sort map drops `sale_price`; create/update stop reading `sale_price`; the Products page loses the `قیمت فروش` sort option, list column, and the add/edit form input.
- **Rationale**: All derive from the removed field; "per-unit profit" ceases to exist at product level.

## D11 — Test strategy (FR-015)
- **Decision**: Update the existing nine test files + `helpers.py` in place (the suite is the single test seam since Spec-001). Fixture `final_price=` kwargs removed; `test_discount_sets_final_price` becomes an assertion that discount payloads are ignored (unknown key; price = sale_price; no `final_price` key in responses). New tests: missing/zero price rejected on create; overpayment vs. entered price; profit = price − cost on create and edit; dashboard Σ-sale / current-year-profit values; brand sold sums; monthly `person_count`/`online_count`; payload key absence; baseline key updates (`total_sale`, dropped `final_price_display`).
- **Rationale**: Modules are already organized per seam (service/compat/reports/utils/calendar); the user explicitly permitted test edits for this feature.
- **Alternatives**: a new parallel module — fragmentation with no benefit.
