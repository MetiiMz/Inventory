# Quickstart: Validate the Supplier Ledger (Spec-004)

Run guide for proving the feature works end-to-end. Endpoint/request/response
shapes are defined in [contracts/ledger-api.md](contracts/ledger-api.md);
entity/field/validation details in [data-model.md](data-model.md). This file
deliberately contains no implementation code.

## Prerequisites

- Python 3.10+ with the project venv: `.venv` at the repository root
  (install once: `.venv/bin/pip install -r backend/requirements.txt`)
- Repository layout: `backend/`, `frontend/`, `db/` at the project root
- Data lives in `db/db.sqlite3` (override with `TIKOTIME_DB=<path>` if needed)

## Setup & run

```bash
# from the repository root
.venv/bin/python backend/manage.py migrate     # creates ledger_* tables (0009)
.venv/bin/python backend/manage.py runserver   # → http://127.0.0.1:8000
```

## Automated validation (primary gate)

```bash
cd backend && ../.venv/bin/python manage.py test
```

- **Expected**: the full suite — the 167 pre-existing tests plus the new
  `tests/test_service_ledger.py` and `tests/test_compat_ledger.py` modules —
  passes with **0 failures** (FR-016, SC-006).
- Run only the new tests while iterating:
  `cd backend && ../.venv/bin/python manage.py test tests.test_service_ledger tests.test_compat_ledger`

## Manual end-to-end walkthrough (maps to the user stories)

1. **Nav** (SC-001): open `http://127.0.0.1:8000/ledger` from the sidebar —
   the "حساب معین" item sits immediately after "پرداخت‌ها"; the page loads in
   one click and shows the empty-state list with an "add supplier" control.
2. **Supplier** (US1/FR-003): add a supplier with a name; it appears in the
   list. Add a second one; verify a duplicate name is rejected with a toast
   and nothing is added.
3. **Invoice with photos** (US1/FR-005…007):
   - expand the supplier (accordion), add an invoice, set a Jalali purchase
     date, attach two page photos (add one photo at a time — page 1, then
     page 2), enter 3 lines — leave the 3rd line's quantity
     blank — and save.
   - Expected: the row shows the first photo as the thumbnail with a "+1"
     badge for the second page, the Jalali date, and a total you
     never typed; the blank-quantity line's total equals its unit price.
   - Reopen the invoice: both photos (in page order), date, line table,
     total quantity and total amount all match hand-computed values (SC-003).
   - Add a photo-less invoice: the row shows an empty placeholder; photos
     can be attached later from the detail view.
4. **Full-size photos** (US2/FR-008): click the thumbnail → the first photo
   opens at full size in the image-view modal; in the detail view, click each
   gallery photo → it opens at full size on its own. Close and continue.
5. **Edit everything** (US3/FR-009): in the detail view change the date,
   add/remove/reorder a page photo, add a line, edit a line's quantity/price,
   remove a line, save. The list-row total and the detail totals recompute
   from the new lines; a removed photo file no longer appears in `db/images/`
   (orphan cleanup).
6. **Cascade deletes** (US3/FR-004/FR-012, SC-002): delete an invoice → it and
   its lines are gone; delete a supplier that still has invoices (confirm in
   the modal) → supplier, all invoices, all lines, and all their photo files
   are gone. No deleted row remains visible after refresh.
7. **Independence spot-check** (SC-004): grep the new ledger modules —
   `grep -rn "ledger" backend/inventory/api/services/ledger.py backend/inventory/api/compat/ledger.py`
   — and confirm they import no product/sale/payment/repair/tracking/report
   module; create a product whose `supplier` field equals a ledger supplier
   name and verify the two lists do not interact (no shared suggestions).
8. **Clear Database** (US4/FR-014, SC-005): with ledger data present, run
   Clear Database from the settings page:
   - a `pre_clear_*.db` backup appears in `db/backups/` first;
   - afterwards: 0 suppliers / 0 invoices / 0 line items / 0 invoice images
     (e.g. `sqlite3 db/db.sqlite3 "select count(*) from ledger_suppliers"`),
     0 invoice photos left in `db/images/`, and the site logo file still
     present; other domains' data is wiped by the existing behaviour.
9. **Persistence** (FR-015): restart `runserver`; the ledger records and
   photos are still there.

## Done when

- `manage.py test` is 100% green (existing + new tests).
- Every step above behaves as written; the "حساب معین" nav item, accordion,
  detail modal, computed totals, and the Clear Database wipe all match
  [contracts/ledger-api.md](contracts/ledger-api.md).