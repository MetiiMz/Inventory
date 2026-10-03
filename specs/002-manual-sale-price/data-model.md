# Data Model: Manual Sale Price (Spec-002)

**Date**: 2026-10-03 · Post-feature entities, invariants and computed aggregates. Delta vs. current schema marked.

## Entity changes

### Product — sale price removed
Fields (after): `name`, `reference`, `office_code`, `website_code`, `brand`, `purchase_price` (cost, FloatField), `available`, `supplier`, `purchase_date` (ISO string), `purchase_type`, `notes`, `image`, `created_at`, `updated_at`.
- **Removed**: `sale_price` (migration `0008_remove_product_sale_price`).
- Validation: unchanged (cost price stays 0-tolerant as today).

### Sale — one price, required at the service layer
Fields (after): `product` (FK, cascade), `sale_price` (the entered price — required > 0 at service level on create; the column keeps `default=0` for schema simplicity, enforcement lives in the sales service), `purchase_price` (denormalized cost snapshot taken from the product at creation; editable on update), `profit` (denormalized; recomputed on every create/update as `sale_price − purchase_price`), `sale_date`, `customer`, `customer_phone`, `sale_type` ("person" | "online"), `payment_type` ("cash" | "deposit"), `paid_cash` / `paid_pos` / `paid_card2card`, `is_settled`, `settled_at`, `invoice_code`, `notes`, `created_at`.
- **Removed**: `final_price` (migration `0007_remove_sale_final_price`).

Invariants:
- `paid_cash + paid_pos + paid_card2card ≤ sale_price + 0.001`, else 400 (existing message style, reworded to name the entered price).
- Cash sale with no typed amounts → fully paid at `sale_price` (existing default, now against the entered price).
- `discount_price` payload key: no longer meaningful — ignored like any unknown key (FR-004).
- The old "final price must not exceed sale price" guard disappears (there is only one price).
- Receipts created at sale time use `total_amount = sale_price` (was `final_price`).

### Payment (receipt) — unchanged
`total_amount`, `paid_amount`, `pay_date`, `settled_at`, `notes`, sale/product FKs. Historical receipts are not rewritten (spec assumption "Receipt history is untouched").

## Computed aggregates (not stored)

| Aggregate | Window | Source after the feature |
|---|---|---|
| Dashboard `total_sale_value` | all-time | Σ `Sale.sale_price` (was Σ `Product.sale_price` over all products) |
| Dashboard `total_profit_value` | current Jalali year | Σ (`Sale.sale_price` − `Sale.purchase_price`) where `sale_date` falls in the current Jalali year (was inventory projection, all-time) |
| Dashboard `sold_revenue` | all-time | Σ `Sale.sale_price` (was Σ `final_price`) |
| Dashboard `sold_profit` | all-time | Σ stored `Sale.profit` (unchanged) |
| Brand row `sale_value` | per brand | Σ `Sale.sale_price` of sales whose product belongs to the brand (was Σ unsold `Product.sale_price`) |
| Brand row `profit` | per brand | Σ (`sale_price` − `purchase_price`) over the same sale rows (was unsold projected margin) |
| Brand row `count` / `value` | per brand | unchanged (unsold stock count / purchase cost) |
| Monthly `person_count` / `online_count` | per Jalali month | COUNT of sales by `sale_type` (new; 0 for future months) |
| Monthly `revenue` | per Jalali month | Σ `Sale.sale_price` (was `final_price`) |

Aggregation basis per research D3: computed from price/cost fields, not the stored `profit` column, so historical discounted rows stay on one consistent basis.

## State / lifecycle
No new states. `is_settled` / payment flows unchanged. Product `available` toggling on sale create/delete unchanged.

## Historical data semantics
- Old discounted sales: display/aggregate at the stored `sale_price`; stored `profit` kept for per-sale display (no recomputation).
- Product rows: the `sale_price` value is discarded by the migration (it becomes unused); every other product field survives intact.

## Migrations
- `0007_remove_sale_final_price` — `RemoveField(Sale.final_price)`
- `0008_remove_product_sale_price` — `RemoveField(Product.sale_price)`
- Generated via `makemigrations`; applied to the local database last, after all code and tests stop referencing the fields (research D8), with a backup taken beforehand.
