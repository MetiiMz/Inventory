# Feature Specification: Supplier Purchase Ledger — "حساب معین" (Spec-004)

**Feature Branch**: `004-supplier-ledger` (development continues on the current `test` branch; no dedicated branch hook is configured for this project)

**Created**: 2026-10-05

**Status**: Final (amended 2026-10-05 — multi-page invoice photos; unbounded line items confirmed)

**Input**: User description: "Add a brand-new, fully independent page 'حساب معین' (supplier purchase ledger) for manually recording the paper purchase invoices received from suppliers (person or company). It is a purely archival/bookkeeping record with zero relationship to the rest of the project's data — not with the product records, not with the supplier text field on the product form, not with the reports or the dashboard. New ledger records: suppliers, and each supplier's invoices (purchase date + optional photo + line items with watch name / reference / quantity / unit purchase price; every total is computed, never entered). The UI is an accordion: supplier list → click supplier to expand its invoice list → click invoice to open a detail modal with full inline editing. The page links into the nav immediately after 'پرداخت‌ها'. Per an explicit temporary decision, the Clear Database action must also wipe ledger records and invoice images. The user's detailed brief (entity attributes, accordion behavior, computed-total semantics, and acceptance criteria) is the authoritative source of scope; the exact API/endpoint shapes are delegated to the implementer, following the app's existing conventions."

## Scope Note vs. Constitution

The project constitution's strict "no behaviour change / tests are frozen" rules were written for the Spec-001 structural restructure. This feature is **new additive functionality**: new data records, new API endpoints, a new page, and new tests are all **expected and required** here. All other constitution constraints still apply: local single-user app (no auth, no multi-device concerns), no new dependencies, no Docker/CSRF, the domain-based split of the services and API-compat layers is respected (a new "ledger" domain is added; existing domains' behaviour is untouched), small reversible commits, and the full automated test suite stays 100% green after every step.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Record a paper purchase invoice (Priority: P1)

As the shop owner, I receive a paper purchase invoice from a supplier. I open "حساب معین", add the supplier if I don't have one yet, record a new invoice with its purchase date, attach one or more photos of the paper invoice — one per physical page (all optional), and enter each purchased watch as a line: watch name, reference, quantity, and unit purchase price. The invoice is stored as a permanent archival record of the purchase.

**Why this priority**: This is the core purpose of the feature. Without the ability to record, none of the browsing, editing, or clearing has value.

**Independent Test**: With an empty ledger, create a supplier, add an invoice with three line items (one left with blank quantity) and two page photos; verify it is stored exactly as entered (both photo rows, in page order), that the blank-quantity line's total equals its unit price, and that the displayed invoice total equals the hand-computed sum of its lines.

**Acceptance Scenarios**:

1. **Given** an empty ledger, **When** the user adds a supplier with a name, **Then** the supplier appears in the ledger's supplier list.
2. **Given** a supplier, **When** the user adds an invoice with a purchase date and line items (one of them with quantity left blank), **Then** the invoice is saved and the blank-quantity line is treated as quantity 1, so its line total equals its unit price.
3. **Given** an invoice form, **When** the user saves it without attaching any photos, **Then** the invoice is saved normally and its list row shows no photo (an empty placeholder instead); photos can be added or replaced later.
4. **Given** an invoice with line items, **When** the user views its list row, **Then** the shown grand total equals the sum of quantity × unit price over all of its lines — a number the user never typed in.


### User Story 2 - Browse the ledger as an accordion (Priority: P1)

As the shop owner, I open "حساب معین" and see my suppliers as a list. Clicking a supplier expands that row in place and shows that supplier's invoices underneath it — each row with the first photo as a thumbnail (when photos exist), a small count badge for any additional pages (e.g. "+2"), the purchase date in Jalali, and the computed grand total. Clicking an invoice (not its buttons) opens a detail modal showing all of the invoice's photos, the date, a table of the line items (watch name, reference, quantity, unit price, line total), and under the table the total quantity and the total amount.

**Why this priority**: Browsing the records is the daily use of the ledger; without the accordion + detail view, recorded data cannot be consulted.

**Independent Test**: Seed one supplier with two invoices (one with two photos, one without; one with multiple lines); open the page, expand the supplier, verify each invoice row's fields (first-photo thumbnail + "+1" badge on the two-page invoice), open the detail modal, and verify the line-item table and both totals match hand-computed values; verify clicking the thumbnail opens the first photo full-size and each photo in the detail view opens full-size on its own click.

**Acceptance Scenarios**:

1. **Given** a ledger with several suppliers, **When** the user clicks a supplier row, **Then** that row expands in place to show its invoice list and an "add invoice" button, while other suppliers stay collapsed.
2. **Given** an expanded supplier's invoice list, **When** the user views each invoice row, **Then** it shows the first-photo thumbnail (or an empty placeholder when there are no photos), a count badge for the remaining pages when there is more than one, the purchase date in Jalali, and the computed grand total.
3. **Given** an invoice row with photos, **When** the user clicks the thumbnail, **Then** the first photo opens at full size using the app's existing image-viewing pattern; in the detail view, each photo individually opens at full size on its own click.
4. **Given** an expanded invoice list, **When** the user clicks an invoice row (anywhere except its edit/delete buttons), **Then** the invoice detail modal opens showing all of the invoice's photos (if any), the date, the line-items table (watch name, reference, quantity, unit price, line total), and under the table the total quantity and the total invoice amount.

---

### User Story 3 - Edit and delete ledger records (Priority: P2)

As the shop owner, I can rename a supplier, and fully edit any invoice: its date, its photos (add, reorder, remove), and any of its line items (add a line, change a line, remove a line) — all from inside the invoice detail view. I can delete any invoice, and deleting a supplier removes that supplier's entire history with it.

**Why this priority**: Records made with a mistake must be correctable; deletion (with cascade) keeps the archive clean.

**Independent Test**: Rename a supplier and verify the change everywhere; in the detail modal, add, edit, and delete a line item on an existing invoice and verify the totals recompute; delete an invoice and verify its lines are gone; delete a supplier and verify all its invoices are gone.

**Acceptance Scenarios**:

1. **Given** a ledger supplier, **When** the user renames it, **Then** the new name is shown everywhere that supplier appears.
2. **Given** an invoice with line items, **When** the user edits it in the detail view (changes the date, adds/reorders/removes photos, adds a new line, edits a line's quantity or price, removes a line) and saves, **Then** all changes are stored and the list-row and detail totals are recomputed from the new lines.
3. **Given** an invoice with line items, **When** the user deletes the invoice, **Then** the invoice and all of its line items are removed.
4. **Given** a supplier that has invoices, **When** the user deletes the supplier, **Then** the supplier, all of its invoices, and all of their line items are removed.

---

### User Story 4 - The ledger is wiped by Clear Database (Priority: P3)

As the shop owner, I use the Clear Database action to start a new year fresh. Per my explicit temporary decision, that action now also removes every ledger supplier, invoice, line item, and invoice photo, while the site logo is kept.

**Why this priority**: It is maintenance behavior with a known, user-decided (and explicitly temporary) policy; it only matters once other data exists.

**Independent Test**: Seed ledger suppliers, invoices with photos, and line items; run Clear Database; verify 0 ledger records and 0 invoice photos remain, the site logo is intact, and the regular pre-clear backup was still taken first.

**Acceptance Scenarios**:

1. **Given** a ledger with suppliers, invoices, and invoice photos, **When** the user runs Clear Database, **Then** all ledger records and all invoice photos are removed, the site logo remains, and the action still takes its automatic pre-clear backup.

---

### Edge Cases

- **No photos**: an invoice may exist and be edited without any photos; photos can be added, reordered, or replaced at any later time (the list shows an empty placeholder until then).
- **Multi-page invoice**: an invoice with several photos shows its first photo as the list thumbnail plus a count badge for the remaining pages; every photo is viewable full-size from the detail view.
- **Blank quantity**: a line with no quantity is treated as 1; its line total equals its unit price — no special UI treatment is needed.
- **Zero-line invoice**: an invoice saved without any line item is allowed; it displays totals of 0 and remains fully editable.
- **Same date, same supplier**: multiple invoices may share a purchase date; each stays a separate record shown as its own list row (the date is the display "name"; there is no separate invoice-name field).
- **Long names**: a long supplier or watch name must not break the list layout (it wraps/truncates consistently with the app's other lists).
- **Empty ledger**: with no suppliers, the page shows an empty-state list and the "add supplier" control.
- **Deleting while viewing**: after deleting an invoice or a supplier, any open lists or views refresh so no deleted row remains visible.
- **Clear Database with ledger data present**: ledger rows and their photos are swept together with all other data; the existing site-logo exception still applies.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a "حساب معین" page, linked from the app's side navigation immediately after the "پرداخت‌ها" (Payments) item.
- **FR-002**: The ledger MUST be a fully independent subsystem: no data relationships, lookups, or references to the app's existing product, sale, repair, tracking, or payment records; no coupling to the supplier text field on the product form (no shared values or shared suggestions); and the ledger data MUST NOT be used by the dashboard or by any report.
- **FR-003**: The user MUST be able to create a ledger supplier by name, edit its name, and delete it; suppliers are listed using the same list pattern the app uses elsewhere (as with brand/product lists).
- **FR-004**: Deleting a supplier MUST automatically delete all of its invoices and all of their line items.
- **FR-005**: The user MUST be able to add an invoice under a supplier with a purchase date (entered and displayed per the app's existing date conventions) and one or more optional photos of the paper invoice — one per physical page, uploaded through the app's existing image upload; photos MUST NOT be required to save an invoice (an invoice may have zero photos).
- **FR-006**: Each invoice MUST be composed of zero or more line items, each having: a watch name (free text, required — not a reference into inventory stock), a reference (optional free text), a quantity (optional; blank means 1), and a unit purchase price.
- **FR-007**: Line totals and the invoice grand total MUST always be computed from the line items (line total = quantity × unit price; invoice total = the sum of its line totals); no total may be entered or stored as a separate field.
- **FR-008**: Each supplier's invoice list MUST show, per invoice: the first photo as a thumbnail (when photos exist — clicking it opens that photo at full size using the app's existing image-viewing pattern), a small count badge for the remaining pages when there is more than one photo (e.g. "+2"), the purchase date in Jalali (acting as the invoice's display name), the computed grand total in the app's money formatting, and edit and delete controls.
- **FR-009**: The user MUST be able to fully edit an invoice — its date, its photos (add, reorder, remove), and its line items (add, edit, delete) — from within the invoice detail view, in a single editing flow.
- **FR-010**: Clicking an invoice row (anywhere except its edit/delete controls) MUST open an invoice detail modal (in the app's existing modal pattern) showing all of the invoice's photos (if any — a thumbnail gallery, each photo individually clickable to open at full size), the purchase date, a table of the line items (watch name, reference, quantity, unit price, line total), and under the table the total quantity and the total invoice amount — both computed.
- **FR-011**: Supplier rows MUST expand accordion-style: clicking a supplier expands that row in place to reveal its invoice list and an "add invoice" control; a previously expanded supplier collapses; clicking a different supplier shows that supplier's invoices instead.
- **FR-012**: Deleting an invoice MUST automatically delete all of its line items.
- **FR-013**: Multiple invoices from the same supplier sharing the same purchase date MUST be allowed; each remains a separate record shown as its own list row.
- **FR-014**: The Clear Database action MUST also wipe all ledger suppliers, invoices, and line items, and remove the invoice photos from the shared image storage (the existing "remove all stored images except the site logo" cleanup already covers the photos). **This is a temporary, explicitly user-decided policy** — a precise Clear Database policy (including separating watch, invoice, and logo images into different folders) will be decided later, in a separate spec.
- **FR-015**: Ledger data MUST persist in the app's existing local storage (the new ledger records are added through the app's normal data-store mechanism) and survive app restarts.
- **FR-016**: New automated tests MUST cover ledger supplier CRUD, invoice CRUD (with and without a photo), line-item CRUD, cascade deletion, and the computed-total logic; the complete automated test suite — the 167 existing tests plus the new ones — MUST pass with 0 failures.

### Key Entities

- **Ledger supplier**: a person or company the user purchases from; has a display name; 1—N ledger invoices; deleting it cascades to its invoices and their line items.
- **Ledger invoice**: one paper purchase invoice from a supplier on a given purchase date; zero or more photos (one per physical page, each with a display order); 1—N line items (unbounded — a real paper invoice can carry ~100 lines); its grand total is always computed from its lines; multiple invoices may share the same date; the date doubles as its display name (no separate name field).
- **Ledger invoice line item**: one purchased watch on an invoice; a free-text watch name (not a reference into inventory stock), an optional reference, a quantity (blank = 1), and a unit purchase price; its line total is always computed.
- **Ledger invoice image**: one page photo attached to an invoice; a stored image filename plus a display order (page 1, 2, 3…); an invoice may have zero images; deleting the invoice (or its supplier) removes all of its images.
- **Relationships**: supplier → invoices (cascade delete); invoice → line items (cascade delete); invoice → invoice images (cascade delete). No relationship to any of the app's existing entities (product, sale, repair, tracking, payment, settings).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The "حساب معین" link is present in the side navigation immediately after "پرداخت‌ها"; the user reaches the ledger page in exactly one click.
- **SC-002**: 0 orphans: after deleting a supplier that has invoices and after deleting an invoice that has line items, zero affected invoices or line items remain (verified by automated tests and a manual check).
- **SC-003**: 0 divergence between the displayed invoice grand total, the detail view's total quantity, and the detail view's total amount versus hand-computed values from the underlying line items, on a fixture with mixed quantities (including blank quantities).
- **SC-004**: 0 references from the new ledger functionality to the app's existing product/sale/repair/tracking/payment records, to the supplier text field on the product form, or to the dashboard/report logic (verifiable by code inspection).
- **SC-005**: After one Clear Database run: 0 ledger suppliers/invoices/line items remain, 0 invoice photos remain, and the site logo is still present.
- **SC-006**: The complete automated test suite (existing tests + new ledger tests) is 100% green, and the new ledger records are added to the app's local storage with 0 errors.
- **SC-007**: A user can complete the entire "record a paper invoice" flow — add supplier, add invoice, enter a representative set of line items (e.g. 5, for the manual walkthrough only — there is no functional cap), attach a page photo, save — entirely inside the app in under 3 minutes.

## Assumptions

- **Spec numbering**: the user's brief labels this feature "Spec 004". The next auto-generated number under `specs/` would have been 003 (only 001 and 002 exist); the user's explicit "Spec 004" label is honored, so the feature directory is `specs/004-supplier-ledger`.
- **Clear Database is temporary**: wiping ledger data and invoice photos on Clear Database is an explicit, temporary user decision for the current development stage; the final policy (including separating watch/invoice/logo image folders) is deferred to a future, separate spec.
- **Invoice display name**: there is no separate "invoice name" field; the purchase date is the display name. Date entry/display follow the app's existing Jalali date conventions.
- **API shape**: the ledger's service and API-compat endpoints follow the app's existing domain-split conventions (a new "ledger" domain); the exact endpoint layout and response shapes are Plan-phase decisions, explicitly delegated to the implementer by the user.
- **Invoice editing mechanism**: whether editing an invoice submits the full line-item list at once or uses per-line add/edit/delete operations is a Plan-phase decision; both are acceptable as long as FR-009 holds.
- **Destructive-action confirmation**: deleting a supplier or an invoice asks for confirmation, consistent with the app's existing destructive-action patterns.
- **UI language and style**: all labels are in Persian, consistent with the app; "add supplier"/"add invoice" controls follow the existing button style; an empty ledger shows an empty-state list.
- **No shared supplier suggestions**: the supplier text field on the product form and the ledger's suppliers are unrelated; no autocomplete/suggestion is shared between the two.
- **Test baseline**: 167 automated tests exist as of 2026-10-05; this feature adds tests on top and does not alter existing test behaviour.
- **Multi-page photos (amendment, 2026-10-05)**: an invoice can carry multiple photos — one per physical page of the paper invoice. The first photo is the list thumbnail; a count badge shows the remaining pages. An invoice may have zero photos; photos can be added, reordered, or removed while editing the invoice (display order = page order).
- **Unbounded line items (amendment, 2026-10-05)**: there is NO cap on line items per invoice (real paper invoices can carry ~100 lines). SC-007's "5 line items" is a representative example for the manual timing walkthrough, not a functional limit.
- **Environment**: local single-user app — no authentication, no multi-device concerns, no new dependencies (per the constitution).

## Out of Scope

- Any dashboard or report use of ledger data (the reporting module stays untouched).
- Any coupling with the supplier text field on the product form, including shared suggestions/autocomplete.
- Financial reconciliation between these purchase invoices and the app's sale/payment records — the ledger is purely a supplier-purchase archive.
- A more precise image-folder separation (watch / invoice / logo) for Clear Database purposes — deferred to a future, separate spec (see FR-014 note).
- Ledger export/import (Excel or any other format) and any external client or mobile access.
- Multi-user access, roles, or permissions.