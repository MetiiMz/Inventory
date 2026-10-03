# API & UI Shape Changes: Manual Sale Price (Spec-002)

Routes and URL paths are **unchanged** (the Spec-001 route contract stands). Payload shapes and form fields **do** change — Spec-002 is explicitly exempt from Spec-001's frozen-response rule. Enforcement points: `backend/tests/test_legacy_api_baseline.py` plus the service/report tests, all updated in the same change set (research D11).

## Removed / renamed JSON keys

### Sale item (`sale_dict` — sold list, sale detail, calendar items, dashboard recent sales)
- Removed: `final_price`, `final_price_display`
- Kept (meaning unchanged): `sale_price`, `sale_price_display`, `purchase_price`, `profit`, `profit_display`, `paid_total`, `paid_cash/pos/card2card`, `is_settled`, `sale_type(_fa)`, `payment_type_fa`, customer/date fields, `product_name`, `product_image`, …

### Sales-list summary
- `total_final` → **`total_sale`** (= Σ entered sale prices; the single UI chip "جمع فروش" switches to it)
- `total_profit` unchanged; `count` unchanged

### Product item (`product_dict`)
- Removed: `sale_price`, `sale_price_display`, `profit_per_unit`, `profit_per_unit_display`, `total_sale_value`, `total_sale_value_display`
- Kept: `total_value` (= purchase cost) and every non-price field

### Sort keys
- Products: `sale_price` removed from the sort map (and the UI option)
- Sales: `final_price` removed from the sort map (and the "قیمت نهایی" UI option)

### Dashboard stats (`get_dashboard_stats`)
- `total_sale_value`: same key, new source — Σ `Sale.sale_price`, all-time (was Σ `Product.sale_price`)
- `total_profit_value`: same key, new source — Σ (`sale_price` − `purchase_price`), **current Jalali year only** (was all-products inventory projection)
- `sold_revenue`: now Σ `Sale.sale_price` (was `final_price`); `sold_profit`, `sold_count`, all stock/payment/repair keys unchanged

### Monthly activity (`get_monthly_activity`, each month object)
- Added: `person_count`, `online_count` (integers; 0 for future months, same convention as existing keys)
- `revenue` now Σ `sale_price` (was `final_price`); `profit`, `count`, `purchase_value`, `jy/jm/label/future` unchanged

### Brand breakdown row (`get_brand_breakdown`)
- `sale_value`, `profit`: now computed from that brand's actual sales (research D3)
- `count`, `value` unchanged (unsold stock)

## Request payloads
- **Create sale**: `sale_price` required (> 0) or 400; `discount_price` no longer accepted as meaningful — ignored like any unknown key (FR-004).
- **Update sale**: `sale_price` optional; when provided it must be > 0; all payment validation runs against it.
- **Create/update product**: `sale_price` no longer read; products save with a cost price only.

## Error contract
- New 400 on create: `قیمت فروش را وارد کنید` (missing/blank/zero/unparseable price)
- Removed 400: `قیمت نهایی نمی‌تواند از قیمت فروش بیشتر باشد` (the concept is gone)
- Reworded 400: the overpayment message now names the entered sale price (same structure/style, `fa_money` amount)

## Forms (UI contract)
- **Sold page sale form**: `sale_price` editable + `required`; the `discount_price` input and its hint are removed.
- **Products page quick "record sale" modal**: identical treatment — one editable required price field (the read-only pre-set price and the discount field are removed) (clarification, session 2026-10-03).
- **Product add/edit form**: the sale-price input is removed; cost price remains.
- **Sale detail panel (sold.js)**: single price rows — `قیمت فروش` and `قیمت پرداخت‌شده توسط خریدار`; the `قیمت نهایی (با تخفیف)` and `میزان تخفیف` rows are gone.
- **Calendar (calendar.js)**: sale price shown via the entered price only; paid-cash/POS/card breakdown rows unchanged.
- **Dashboard**: two stat-box label/sub-text renames and two brand-table label changes (research D5/D6); chart gains two series + legend + tooltip rows (research D7).

## Import / export
- Product CSV/Excel: `قیمت فروش` column removed from both export and import; a legacy file that still contains the column imports fine (column ignored).
- Sales export: `قیمت نهایی` column removed (rows: purchase, sale, profit).
