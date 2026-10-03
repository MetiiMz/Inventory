# Quickstart / Validation: Manual Sale Price (Spec-002)

Run from the repository root. Development happens on the `test` git branch; all commands use the project `.venv`.

## Prerequisites

- Clean working tree; `.venv` present with Django installed.
- Back up the live database before any migration step:
  ```bash
  cp db/db.sqlite3 /tmp/db-manual-sale-price-backup.sqlite3
  ```

## Automated gates

```bash
.venv/bin/python backend/manage.py check           # expect: 0 issues
cd backend && ../.venv/bin/python manage.py test   # full suite green (updated + new tests; count will differ from 153)
```

Spot-check these specific behaviors in the suite (research refs in D-numbers):
- Creating a sale without a price → 400 rejection (D1).
- A `discount_price` payload key is ignored; responses contain no `final_price`/`final_price_display` (D4).
- Dashboard `total_sale_value` = Σ entered sale prices; `total_profit_value` excludes prior-year sales (D3/D5).
- Brand rows' sold sums come from actual sales; monthly `person_count`/`online_count` are correct (D3/D7).

## Migrations (apply last — only after code + tests are green)

```bash
.venv/bin/python backend/manage.py makemigrations inventory   # expect 0007_remove_sale_final_price, 0008_remove_product_sale_price
.venv/bin/python backend/manage.py migrate                    # against the local db
```

No-data-loss check (SC-005): before migrating, dump a sample of `products` (name, purchase_price, sale_price) and `sales` (sale_price, purchase_price, profit, paid_*); after, the same rows must be identical on every remaining column, and the two dropped columns must be gone.

## Manual end-to-end (runserver)

```bash
.venv/bin/python backend/manage.py runserver
```

1. **Products page → add a watch**: the form has only a cost-price input; no sale-price field anywhere; the list and the sort dropdown have no `قیمت فروش` option.
2. **Quick "record sale" modal (Products page)**: one editable required price field; no discount field. Submit with an empty price → Persian error, nothing saved. With a price → saved; profit = price − cost.
3. **Sold page**: same behavior; the `قیمت نهایی` sort option is gone; the "جمع فروش" summary chip equals the sum of entered prices.
4. **Dashboard**: box 2 equals the sum of entered prices over all recorded sales; box 3 equals profit of current-Jalali-year sales only (seed a prior-year sale to verify exclusion); the 12-month chart shows two new dashed lines (in-person / online counts) plus their tooltip rows and legend entries; stock boxes unchanged.
5. **Brand table**: "جمع ارزش فروش" and "سود فروش" come from actual sales; stock count/cost columns unchanged; a brand with no sales shows 0 for both.
6. **Calendar**: sale events show the entered price; the paid-cash/POS/card breakdown is unchanged.
7. **Exports**: product CSV/Excel has no `قیمت فروش` column; the sales export has no `قیمت نهایی` column; an old file that still contains the column imports fine (column ignored).
8. **Historical discounted sale**: displays its stored sale price and stored profit — no recomputation.

## Rollback

```bash
git revert --no-commit <feature-commits>          # or reset to the pre-feature commit
.venv/bin/python backend/manage.py migrate inventory 0006_sale_invoice_code   # undo both column drops
# last resort: restore /tmp/db-manual-sale-price-backup.sqlite3
```
