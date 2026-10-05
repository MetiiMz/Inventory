# Data Model: Supplier Purchase Ledger (Spec-004)

Four new entities in `backend/inventory/models.py`, introduced by migration
`inventory/migrations/0009_ledger.py`. The ledger is a **fully independent
subsystem**: no foreign keys to, or lookups of, `Product`, `Sale`, `Payment`,
`Repair`, `Tracking`, or `Setting` (FR-002, SC-004).

> **Amendment, 2026-10-05**: an invoice now carries **zero or more photos**
> (one per physical page) via the new child model `LedgerInvoiceImage`,
> replacing the single `image` CharField on `LedgerInvoice`. Also confirmed:
> **no cap on line items per invoice** (real paper invoices can carry ~100
> lines).

## Entities

### LedgerSupplier

A person or company the user purchases from.

| Field | Type | Constraints / defaults | Notes |
|-------|------|------------------------|-------|
| `id` | BigAutoField | PK, auto | — |
| `name` | CharField(200) | not blank (stripped) | display name; uniqueness enforced in the service layer (exact, stripped match → Persian `ApiError`), mirroring the brand-list behaviour |
| `created_at` | DateTimeField | `auto_now_add=True` | convention of the existing models |
| `updated_at` | DateTimeField | `auto_now=True` | updated on rename |

- **db_table**: `ledger_suppliers`; index on `name`.
- **Relationships**: 1 — N `LedgerInvoice` (CASCADE); deleting a supplier removes all of its invoices and all of their line items (FR-004, SC-002), plus their photo files on disk (`remove_image` per invoice).

### LedgerInvoice

One paper purchase invoice from a supplier on a given purchase date.

| Field | Type | Constraints / defaults | Notes |
|-------|------|------------------------|-------|
| `id` | BigAutoField | PK, auto | — |
| `supplier` | FK → `LedgerSupplier` | `on_delete=CASCADE`, `related_name="invoices"`, not null | deleting the supplier cascades (FR-004) |
| `purchase_date` | CharField(10) | ISO `YYYY-MM-DD`; validated via `_parse_iso_or_raise` (Jalali or ISO input accepted) | stored ISO, displayed Jalali via `fa_date` — same convention as `Product.purchase_date`; **the date is the invoice's display name** (no separate name field) |
| `created_at` | DateTimeField | `auto_now_add=True` | — |

- **db_table**: `ledger_invoices`; index on `[supplier_id, -id]`.
- **Relationships**: 1 — N `LedgerInvoiceImage` (CASCADE, `related_name="images"`) — the invoice's page photos; zero rows = no photos (still optional, FR-005). The old single `image` CharField is **removed** by this amendment.
- **Multiple invoices may share the same purchase date** (FR-013, edge case) — no uniqueness constraint on `purchase_date`.
- **Computed (never stored, FR-007)**:
  - `total_quantity` = `SUM(lines.quantity)`
  - `total_amount` = `SUM(lines.quantity * lines.unit_price)`
  - exposed as `total_quantity`, `total_amount`, `total_quantity_display`, `total_amount_display` in the serializer.

### LedgerLineItem

One purchased watch on an invoice.

| Field | Type | Constraints / defaults | Notes |
|-------|------|------------------------|-------|
| `id` | BigAutoField | PK, auto | — |
| `invoice` | FK → `LedgerInvoice` | `on_delete=CASCADE`, `related_name="lines"`, not null | deleting the invoice removes all lines (FR-012) |
| `watch_name` | CharField(200) | required (not blank after strip; Persian `ApiError` otherwise) | **free text — not a reference into inventory stock** (FR-006) |
| `reference` | CharField(100) | default `""`, blank allowed | optional free text |
| `quantity` | IntegerField | default 1; service normalizes blank/missing/0/non-numeric → **1** | "blank means 1" (FR-006, edge case) |
| `unit_price` | Float | default 0; service clamps to `≥ 0` via `to_float` + `max(0.0, …)` | purchase price per unit |

- **db_table**: `ledger_lines`; index on `[invoice_id, id]` (stable line order = insertion order; the full-replace editor preserves the submitted order).
- **Zero-line invoices are legal** (edge case): an invoice with no line items shows totals of 0 and remains fully editable.
- **No cap on line items per invoice** (amendment, 2026-10-05): a real paper invoice can carry ~100 lines; nothing in the model, service, or UI limits the count.
- **Computed (never stored, FR-007)**: `line_total = quantity * unit_price`.

### LedgerInvoiceImage

One page photo of the paper invoice (multi-page invoices have several rows).

| Field | Type | Constraints / defaults | Notes |
|-------|------|------------------------|-------|
| `id` | BigAutoField | PK, auto | — |
| `invoice` | FK → `LedgerInvoice` | `on_delete=CASCADE`, `related_name="images"`, not null | deleting the invoice (or its supplier) removes all its photos |
| `filename` | CharField(255) | not blank (service-enforced; must be the stored name returned by the existing upload endpoint) | filename in shared `db/images/`, same upload mechanism as watch product photos (FR-005) |
| `order` | IntegerField | default 0; non-negative; service sets it from the submitted array position | display sequence = page 1, 2, 3… |
| `created_at` | DateTimeField | `auto_now_add=True` | — |

- **db_table**: `ledger_invoice_images`; index on `[invoice_id, order]`.
- **Zero rows is legal** — photos remain optional (FR-005).
- **Ordering**: the API accepts the photos as an ordered array; array position
  becomes `order` (page order). The UI may reorder entries before saving.

## Relationships (summary)

```
LedgerSupplier 1 ──── * LedgerInvoice 1 ──── * LedgerLineItem
        (CASCADE)                        (CASCADE)
                                  LedgerInvoice 1 ──── * LedgerInvoiceImage
                                                          (CASCADE)
```

- Deleting a supplier ⇒ all its invoices + their line items + their image rows are removed, and `remove_image` is called for every orphaned photo file.
- Deleting an invoice ⇒ all its line items and its `LedgerInvoiceImage` rows are removed (and its photo files, via the service).
- No other relationships; no shared values with the product form's `supplier` text field.

## Validation rules (enforced in `services/ledger.py`, Persian messages)

| Rule | Message (direction) |
|------|---------------------|
| supplier name blank | "نام تأمین‌کننده خالی است" (400) |
| supplier name already exists (create / rename onto another) | "این تأمین‌کننده قبلاً ثبت شده است" (400) |
| unknown supplier on invoice create | "تأمین‌کننده یافت نشد" (404) |
| invalid purchase date | "تاریخ معتبر نیست" (400) |
| line missing watch name | "نام ساعت را وارد کنید" (400) |
| image entry blank/not a string | "عکس معتبر نیست" (400) |
| invoice not found on detail/PUT/DELETE | "یافت نشد" (404) — standard app pattern |

## State & transitions

No lifecycle states — ledger records are archival. The only state-like
behaviour is the accordion UI state (client-side, not persisted) and the
Clear Database policy: `ledger_suppliers`, `ledger_invoices`, `ledger_lines`,
`ledger_invoice_images` are members of `dbhelpers._CLEAR_TABLES`, so Clear
Database wipes them (and their photos via the existing image sweep, site logo
kept) per FR-014.

## Persistence (FR-015)

Records live in the app's existing SQLite storage (`db/db.sqlite3`,
`TIKOTIME_DB` override) and survive restarts — same mechanism as every other
domain. No new storage, no new folders, no new dependencies.