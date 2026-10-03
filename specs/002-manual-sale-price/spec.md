# Feature Specification: Manual Sale Price at Sale Time (Spec-002)

**Feature Branch**: `002-manual-sale-price` (development continues on the current `test` branch; no dedicated branch hook is configured for this project)

**Created**: 2026-10-03

**Status**: Draft

**Input**: User description: "Remove the pre-set product sale price; make sale price a required manual entry at sale time. Update all dependent reports. Context: this is Spec 002, independent from the Spec-001 restructure already completed. Constitution's 'no behaviour change' rule applies only to Spec 001 and does not restrict this feature — schema, logic, and template changes are expected and required here." (Full verified change list provided by the user; the numbered "Required changes" and acceptance criteria in the originating request are the authoritative source of scope.)

## Scope Note vs. Constitution

The project constitution's strict "no behaviour change / tests are frozen" rules were written for the Spec-001 structural restructure. This feature is **explicitly exempt**: changing the data schema (removing fields), changing sale-flow logic, changing report calculations, changing templates, and updating existing tests are all **required** here. All other constitution constraints (local single-user app, no new dependencies, no auth/Docker, small reversible commits, domain-based file split untouched) still apply.

## Clarifications

### Session 2026-10-03

- Q: Does the quick "record sale" modal on the Products page (currently a read-only pre-set price plus a required "final price" discount field) get the same treatment as the Sold page form — a single editable required sale price with the discount field removed? (FR-003/FR-004) → A: Yes — identical treatment to the Sold page form: one manually entered required price; the read-only pre-set price field and the discount field are removed; the same validation, profit, and payment rules apply.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Record a sale with a price I actually type (Priority: P1)

As a shop clerk, I open the "Record Sale" form, pick a product, and type the real sale price for this customer. The form has no discount field — the price I type is the price the customer pays. If I forget to type a price, the system refuses to save and tells me why.

**Why this priority**: This is the heart of the feature. Everything else (reports, dashboard, list views) is only meaningful once every sale carries a real, manually-entered price instead of a stale pre-set one.

**Independent Test**: Create a sale with a typed price and verify it saves with that exact price and profit = price − product cost; create a sale without a price and verify it is rejected with a clear error. No product data needs a sale price for either test.

**Acceptance Scenarios**:

1. **Given** a product in stock, **When** the clerk opens the Record Sale form and submits without entering a sale price, **Then** the sale is rejected with a clear Persian error message and nothing is saved.
2. **Given** a product in stock, **When** the clerk submits a sale with a manually entered sale price, **Then** the sale is stored with exactly that price, its profit equals price minus the product's purchase (cost) price, and no separate "final/discounted" price exists on the record.
3. **Given** an existing sale, **When** the clerk edits it and changes the sale price, **Then** profit is recomputed from the new price and all payment-amount checks run against the new price (the old "final price" fallback no longer exists).
4. **Given** a sale form, **When** the clerk looks at the payment fields, **Then** the amount already paid can never exceed the entered sale price; for a cash ("نقدی") sale with no amounts typed, the sale is recorded as fully paid at the entered price (existing default behavior, now against the entered price).
5. **Given** the quick "record sale" modal on the Products page, **When** the clerk records a sale from the inventory screen, **Then** a single editable required price field is shown (the read-only pre-set price and the discount field are gone) and the same validation/profit/payment rules as the Sold page form apply.

---

### User Story 2 - Add a product with only a cost price (Priority: P1)

As a shop clerk, when I register a new watch, I only type what I paid for it (purchase/cost price). There is no "sale price" field anywhere in the product form — I decide the selling price later, at the moment of sale.

**Why this priority**: Pair with User Story 1 — the stale pre-set price must disappear from both ends of the flow (product side and sale side) or the old default would still be editable somewhere.

**Independent Test**: Open the Add Product form, confirm no sale-price field exists, submit a product with only a cost price, and verify it saves and the product page still renders everywhere.

**Acceptance Scenarios**:

1. **Given** the Add Product form, **When** the clerk inspects it, **Then** it contains only the purchase (cost) price input — no sale-price input.
2. **Given** the product stored after migration, **When** any screen or export reads the product, **Then** it exposes cost price and all other product attributes, but no product-level sale price.

---
### User Story 3 - Dashboard numbers reflect what actually sold (Priority: P2)

As the shop owner, the two top dashboard boxes tell me real business numbers: "total sale value" is the sum of prices of sales that actually happened (not a projection over everything sitting in the warehouse), and the profit box is the profit of sales that happened in the current Jalali year (not a forever-accumulating sum and not an inventory projection).

**Why this priority**: The owner's daily glance metric. Wrong numbers here actively mislead inventory and pricing decisions; after removing the pre-set price, the old inventory-projection numbers would be meaningless or broken anyway.

**Independent Test**: Seed a test database with known products (some unsold, some sold) and known sales (some in the current Jalali year, some in earlier years); verify the two boxes equal hand-computed sums over actual Sale records with the correct filters.

**Acceptance Scenarios**:

1. **Given** products in stock with cost prices but no sales, **When** the dashboard loads, **Then** "total sale value" shows 0 (previously it projected from pre-set sale prices of unsold inventory).
2. **Given** sales in the current Jalali year plus sales from earlier years, **When** the dashboard loads, **Then** the profit box equals the sum of profit of only the current-year sales.
3. **Given** any set of sales, **When** the dashboard loads, **Then** "total sale value" equals the sum of the entered sale prices of those sales exactly.

---

### User Story 4 - Brand table shows what each brand actually earned (Priority: P2)

As the shop owner, the per-brand table's "total sale value" and profit columns are computed from sales that actually happened for that brand, not from pre-set prices of unsold stock. The columns showing unsold stock count and stock cost value stay exactly as before.

**Why this priority**: Directly dependent on the same data-shape change; the brand table is the owner's per-supplier performance view and would otherwise keep projecting phantom numbers from removed data.

**Independent Test**: Seed two brands: one with several sold products and unsold remainder, one with zero sales but stock; verify per-brand sale value and profit equal hand-computed sums over that brand's Sale rows only, while stock count/value columns are unchanged.

**Acceptance Scenarios**:

1. **Given** brand A with sold and unsold products, **When** the owner views the brand table, **Then** brand A's "total sale value" = sum of sale prices of its sold products and its profit = sum of (sale price − cost) for those same sales.
2. **Given** brand B with stock but no sales, **When** the owner views the brand table, **Then** brand B's sale value and profit are 0 while its stock count and stock cost value are still correct.

---

### User Story 5 - Activity chart shows in-person vs. online volume (Priority: P3)

As the shop owner, the 12-month activity chart adds two new lines: how many in-person sales and how many online sales happened each month, alongside the existing purchase/sale/profit lines.

**Why this priority**: A reporting enhancement riding on the same data source; valuable for channel comparison but not blocking for the core price change.

**Independent Test**: Seed sales of both types across known months; verify the two new per-month count series equal hand counts and the existing series are unchanged.

**Acceptance Scenarios**:

1. **Given** sales marked in-person and online across several months, **When** the owner views the 12-month chart, **Then** two new series appear with per-month counts matching the actual sale counts of each type, and the existing series (purchase value, sale value, profit, total count) are unchanged.

---

### User Story 6 - Every sale view shows one price: the one I entered (Priority: P3)

As a clerk or owner, everywhere a sale is shown — the Sold list, the calendar, the dashboard's recent-sales table, exports — only the manually entered sale price appears. No "final price" column, no "discount" breakdown, no sort option by final price.

**Why this priority**: Cleanup of all consumer surfaces so the UI can't display a concept that no longer exists; last-mile consistency after the data change.

**Independent Test**: With historical data (including old sales that had a discounted final price), open the Sold list, calendar, dashboard and the sales export; verify only the entered price is shown, payment breakdowns remain, and no discount remnants exist.

**Acceptance Scenarios**:

1. **Given** the Sold list page, **When** the clerk views it, **Then** the "final price" (قیمت نهایی) sort option is gone, no discount/final-price column or detail text appears, and the displayed price is the entered sale price.
2. **Given** the calendar page, **When** the clerk views a sale event, **Then** its price is the entered sale price (no fallback to a removed field) and the paid-cash / POS / card-to-card breakdown is unchanged.
3. **Given** the sales export, **When** the owner exports sales, **Then** the price column contains the entered sale price.

---

### Edge Cases

- **Missing or empty price**: submitting a sale without a price (or with a blank/zero price field) must be rejected with a clear, specific error — no silent fallback to any product value.
- **Overpayment**: entered paid amounts that sum to more than the sale price must be rejected with the existing style of error message, now referencing the entered price.
- **Editing a deposit sale**: when a "بیعانه" (deposit) sale is edited with a new price, validation and profit recompute against the new price; previously recorded receipts keep their stored amounts (no automatic rewrite of past receipts — payment-receipt logic is out of scope).
- **Historical discounted sales**: old sales stored with a discounted final price lower than their listed price keep their stored sale price, profit and payments; after the redundant final-price column is dropped, their displayed/summed price is the stored sale price. Historical profit values are NOT retroactively recomputed — the recorded profit stays as-is.
- **Product without a cost price**: sale profit is computed against a zero cost (existing behavior: profit = full price).
- **Zero-sales brand/product**: all "sold" aggregates must read as zero without errors or empty-table crashes.
- **Migration on the live local database**: both column removals must apply cleanly on the existing `db/db.sqlite3`; every remaining field (product cost price; sale price, profit, payments, dates, customer data) must be preserved exactly; the app must start and all pages render after migration.
- **No remaining readers of the removed price field**: before the column is dropped, every code path that read the "final/discounted" price must be switched to the entered price so nothing references a missing field.


## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The product record MUST NOT store a sale price; it stores only the purchase (cost) price and its existing non-price attributes.
- **FR-002**: The Add/Edit Product form MUST NOT present a sale-price input.
- **FR-003**: Recording a sale — from either the Sold page form or the Products page quick "record sale" modal — MUST require a manually entered sale price; the system MUST reject the sale with a clear error when the price is missing or invalid, and MUST NOT default it to any product value. The Products page modal's current read-only pre-set price field and required discount field are replaced by this single editable required price field.
- **FR-004**: The concept of a separate discounted "final price" MUST be removed from the entire sale flow: no discount input in any form (including the Products page quick modal), no discount alias accepted from client payloads, no "final price" stored on the sale — the entered sale price IS the final price.
- **FR-005**: Sale profit MUST equal entered sale price minus the product's purchase price, on both creation and edit of a sale.
- **FR-006**: Payment-amount validation MUST run against the entered sale price: total paid cannot exceed it; a cash sale with no typed payments is recorded as fully paid at the entered price.
- **FR-007**: The sale record's redundant discounted-final-price field MUST be removed from storage via a data migration; all historical sale data that remains (sale price, profit, payments, dates, customer, sale type) MUST be preserved.
- **FR-008**: The dashboard "total sale value" (ارزش فروش) MUST equal the sum of sale prices of sales that actually happened, not a projection over unsold products.
- **FR-009**: The dashboard profit box MUST equal the sum of profit of sales dated within the current Jalali year.
- **FR-010**: The brand table's "total sale value" (جمع ارزش فروش) MUST equal the sum of sale prices of that brand's actual sales; its profit column MUST equal the sum of (sale price − cost) over the same sales. The existing stock-count and stock-cost-value columns MUST keep their current meaning (unsold inventory).
- **FR-011**: The 12-month activity chart MUST add two series: per-month count of in-person sales and per-month count of online sales; existing series MUST remain unchanged.
- **FR-012**: The Sold list page MUST remove the "final price" (قیمت نهایی) sort option and every discount/final-price column, input or detail text; it MUST display only the entered sale price.
- **FR-013**: The calendar MUST display the entered sale price for sale events (no fallback to a removed field); the payment breakdown section MUST stay unchanged.
- **FR-014**: The dashboard's recent-sales table and the sales export MUST display the entered sale price only.
- **FR-015**: Existing tests that assert the old behavior (discount alias, final-price fallback, default-to-product price, inventory-projection aggregates, brand breakdown over stock) MUST be updated to the new intended behavior; the full suite MUST pass.
- **FR-016**: After the change, the application's system check and full test suite MUST pass; the app MUST run against the migrated real local database with all pages functional.

### Key Entities

- **Product**: a watch in stock — cost (purchase) price, purchase date, stock availability, brand, codes, image. After this feature: no sale-price attribute.
- **Sale**: one sold product — entered sale price (required, manual), profit, sale date, sale type (in-person / online), payment type (cash / deposit), paid amounts (cash, POS, card-to-card), customer. After this feature: no separate discounted final-price attribute.
- **Payment (receipt)**: an amount paid against a sale — total amount, paid amount, date. Unchanged by this feature.
- **Brand**: a grouping label on products, with aggregates: unsold stock count, unsold stock cost value, sold sale-value, sold profit (new meaning after this feature).
- **Jalali calendar month**: the time bucket for the activity chart and for "current year" aggregation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of newly recorded sales carry a manually entered price; 0 sales can be created without one (verified by an automated attempt that is rejected).
- **SC-002**: The two top dashboard boxes match hand-computed sums over actual Sale records exactly (0 divergence) on a fixture containing unsold stock and multi-year sales.
- **SC-003**: Every brand-table row's sale-value and profit match hand-computed per-brand sums over that brand's Sale rows exactly; stock columns match pre-feature values on the same fixture.
- **SC-004**: The two new chart series match hand-counted in-person/online sales per month exactly, with all pre-existing series unchanged.
- **SC-005**: The migration applies to the real local database with 0 data loss on all retained fields (product cost prices; sale prices, profits, payments, dates, customers), verified by before/after row inspection.
- **SC-006**: 0 discount/final-price remnants remain in the sale-flow UI (forms, sort options, detail panels, list columns) and 0 code references to the removed price field remain in the application.
- **SC-007**: The full automated test suite passes with 100% green and the application system check reports 0 issues.

## Assumptions

- **Historical data semantics**: old sales that had a discounted final price will display and aggregate at their stored sale price after the redundant column is dropped; their stored profit values are preserved as recorded (no retroactive recomputation). This matches the explicit instruction to drop the column rather than back-fill.
- **Receipt history is untouched**: payment receipts created under the old final-price are not rewritten; only the validation target for new/edited amounts changes to the entered sale price.
- **Labels**: the dashboard/brand-table labels ("ارزش فروش", "سود بالقوه") may be kept or cosmetically renamed (e.g., "سود فروش‌رفته") to reflect the new meaning; either way the displayed values come from actual Sale records.
- **Current-year window**: "current Jalali year" uses the same Jalali calendar math the app already uses for the activity chart — the year in which today falls.
- **Local single-user app**: per the constitution, everything stays local; no authentication, no multi-device concerns; the migration runs once on the local database.
- **Small reversible commits**: per the constitution, the schema change (migrations), the sale-flow logic change, the reporting changes, and the template changes land as small, individually revertible commits.

## Out of Scope

- Changes to the payment-receipt model or `payment_type` logic beyond staying consistent with the removed discount concept.
- Changes to Repair, Tracking, or other domain models.
- Changes to Spec-001's completed restructure (file locations, `services`/`compat` package split) — this feature edits the content of the already-split files only.
- Retroactive recomputation or reconstruction of historical discounted prices/profits.
- Adding discount capability in any new form (promotions, per-customer pricing, price history).
