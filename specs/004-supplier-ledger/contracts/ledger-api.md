# Contract: Ledger API + Page (Spec-004)

The project's sole HTTP contract is the set of `/api/*` routes the frontend
calls. This feature **adds** a new `ledger` family; every pre-existing route
keeps its exact shape (constitution rule 1). Conventions (from
`inventory/api/compat/common.py`):

- success envelope: `{ "ok": true, ...payload }`
- error envelope: `{ "ok": false, "error": "<Persian message>" }` with the
  matching HTTP status (400 business error, 404 not found, 405 bad method)
- create responses wrap the entity: `{ "ok": true, "supplier": { … } }` /
  `{ "ok": true, "invoice": { … } }`
- list responses: `{ "ok": true, "items": [ … ] }`
- all bodies are JSON (`Content-Type: application/json`); dates are ISO
  `YYYY-MM-DD` strings, accepted also in Jalali form on input.

Routes registered in `backend/tikotime/urls.py` (page + API):

```
GET  /ledger                                   page shell (views.ledger_page)
GET  /api/ledger/suppliers
POST /api/ledger/suppliers
PUT  /api/ledger/suppliers/<supplier_id>
DELETE /api/ledger/suppliers/<supplier_id>
GET  /api/ledger/invoices?supplier_id=<n>
POST /api/ledger/invoices
GET  /api/ledger/invoices/<invoice_id>
PUT  /api/ledger/invoices/<invoice_id>
DELETE /api/ledger/invoices/<invoice_id>
```

(Photos use the pre-existing `POST /api/upload` — called **once per photo** —
and `GET /data/images/<name>`; both are unchanged.)

## 1. `GET /api/ledger/suppliers`

Lists ledger suppliers, ordered by name ascending.

```json
{ "ok": true,
  "items": [
    { "id": 1, "name": "فروشگاه آبان", "invoice_count": 3 },
    { "id": 2, "name": "امید ساعت", "invoice_count": 0 }
  ] }
```

## 2. `POST /api/ledger/suppliers`

Create a supplier. Body: `{ "name": "<string>" }`.

- 200 → `{ "ok": true, "supplier": { "id": 3, "name": "امید ساعت" } }`
- 400 → `{ "ok": false, "error": "نام تأمین‌کننده خالی است" }`
- 400 → `{ "ok": false, "error": "این تأمین‌کننده قبلاً ثبت شده است" }`
  (exact match on the stripped name)

## 3. `PUT /api/ledger/suppliers/<supplier_id>`

Rename a supplier. Body: `{ "name": "<string>" }`.

- 200 → `{ "ok": true, "supplier": { "id": 3, "name": "امید" } }`
- 404 → `{ "ok": false, "error": "یافت نشد" }`
- 400 → blank name / duplicate-of-another-supplier (same messages as create)

## 4. `DELETE /api/ledger/suppliers/<supplier_id>`

Delete the supplier with full cascade (invoices + line items + photo files).

- 200 → `{ "ok": true }`
- 404 → `{ "ok": false, "error": "یافت نشد" }`

## 5. `GET /api/ledger/invoices?supplier_id=<n>`

Invoice **summary** list for one supplier (no line detail), ordered by
`purchase_date` desc, then `id` desc. `supplier_id` is required and must
exist.

```json
{ "ok": true,
  "items": [
    {
      "id": 10,
      "supplier_id": 1,
      "purchase_date": "2026-06-21",
      "purchase_date_fa": "۱۴۰۵/۰۳/۳۱",
      "images": ["img_20260621_101500_ab12cd34.jpg"],
      "total_quantity": 4,
      "total_quantity_display": "۴",
      "total_amount": 12500000.0,
      "total_amount_display": "۱۲٬۵۰۰٬۰۰۰"
    }
  ] }
```

- 404 → unknown `supplier_id`: `{ "ok": false, "error": "یافت نشد" }`
- Empty list → `{ "ok": true, "items": [] }`

## 6. `POST /api/ledger/invoices`

Create an invoice with its complete line list (one transaction). Body:

```json
{
  "supplier_id": 1,
  "purchase_date": "1405/03/31",
  "images": ["img_page1.jpg", "img_page2.jpg"],
  "lines": [
    { "watch_name": "روکسول", "reference": "RX-4250", "quantity": "2", "unit_price": "3000000" },
    { "watch_name": "دنیلا", "reference": "", "quantity": "", "unit_price": "3500000" }
  ]
}
```

- `supplier_id` required (404 "تأمین‌کننده یافت نشد" if unknown)
- `purchase_date` required, Jalali or ISO (400 "تاریخ معتبر نیست")
- `images` optional; omitted or `[]` = no photos (zero-photo invoice is legal).
  It is an **ordered array of stored filenames** (one per physical page, in
  display order — page 1, 2, 3…), each entry a non-empty string previously
  returned by `POST /api/upload`; one `LedgerInvoiceImage` row is created per
  entry with `order` = its array position (400 "عکس معتبر نیست" if any
  entry is blank or not a string).
- `lines` optional (absent or `[]` ⇒ zero-line invoice, totals 0); each line:
  `watch_name` required (400 "نام ساعت را وارد کنید"), `quantity` blank/0 → 1,
  `unit_price` ≥ 0
- 200 → `{ "ok": true, "invoice": <full invoice object, see §7> }`

## 7. `GET /api/ledger/invoices/<invoice_id>`

Full invoice **detail** — the list fields above plus the line items and
computed totals:

```json
{ "ok": true,
  "invoice": {
    "id": 10, "supplier_id": 1,
    "purchase_date": "2026-06-21", "purchase_date_fa": "۱۴۰۵/۰۳/۳۱",
    "images": ["img_page1.jpg", "img_page2.jpg"],
    "created_at": "2026-06-21T07:15:00.000000Z",
    "total_quantity": 3, "total_quantity_display": "۳",
    "total_amount": 9500000.0, "total_amount_display": "۹٬۵۰۰٬۰۰۰",
    "lines": [
      { "id": 1, "watch_name": "روکسول", "reference": "RX-4250",
        "quantity": 2, "quantity_display": "۲",
        "unit_price": 3000000.0, "unit_price_display": "۳٬۰۰۰٬۰۰۰",
        "line_total": 6000000.0, "line_total_display": "۶٬۰۰۰٬۰۰۰" },
      { "id": 2, "watch_name": "دنیلا", "reference": "",
        "quantity": 1, "quantity_display": "۱",
        "unit_price": 3500000.0, "unit_price_display": "۳٬۵۰۰٬۰۰۰",
        "line_total": 3500000.0, "line_total_display": "۳٬۵۰۰٬۰۰۰" }
    ] } }
```

- 404 → `{ "ok": false, "error": "یافت نشد" }`
- Every `*_total*` / `total_*` value is computed from the lines at read time
  (FR-007, SC-003) — never read from a stored column.

## 8. `PUT /api/ledger/invoices/<invoice_id>`

Full edit in one flow (FR-009): replaces the date, photos, and the entire line
list (full-replace semantics, one transaction). Body: same shape as §6 minus
`supplier_id` (a supplier's invoices cannot be re-parented).

- `lines` present ⇒ the whole set is replaced (add / change / remove all work
  through this); omitted ⇒ existing lines are kept
- `images` present ⇒ the whole photo set is replaced: existing rows are
  dropped, one row per submitted entry in order, and any file no longer
  referenced is removed (add / reorder / remove all work through this);
  omitted ⇒ kept; `[]` ⇒ all photos removed (files removed)
- 200 → `{ "ok": true, "invoice": <full invoice object> }`
- 404 → `{ "ok": false, "error": "یافت نشد" }`
- 400 → same line/date validations as §6

## 9. `DELETE /api/ledger/invoices/<invoice_id>`

Delete the invoice + its line items + its photo rows (and their files).

- 200 → `{ "ok": true }`
- 404 → `{ "ok": false, "error": "یافت نشد" }`

## Page & navigation contract

- `GET /ledger` renders the ledger page shell (`frontend/templates/ledger.html`),
  identical layout pattern to the other pages (topbar, glass sections, modals).
- Sidebar (`frontend/templates/base.html`): a new nav item **"حساب معین"**
  appears **immediately after** the **"پرداخت‌ها"** item and before
  "تنظیمات و پشتیبان" (FR-001, SC-001). No badge on the item.
- Accordion behaviour (FR-011): exactly one supplier expanded at a time;
  invoice row layout = first-photo thumbnail (or empty placeholder) +
  "+N" count badge when more than one photo + Jalali date + computed total +
  edit/delete controls; clicking the row body opens the detail/edit modal
  (§7 shape); clicking the thumbnail opens the first photo full-size in the
  page's image-view modal; the detail modal shows all of the invoice's photos
  as a thumbnail gallery, each individually clickable to open at full size.
  The create/edit form supports multiple photos (repeated "add photo" action,
  each uploading through `/api/upload`), with per-photo remove and reordering
  (display order = page order, submitted as the `images` array).
- Money values are displayed with the app's `faMoney` formatting
  (Persian digits + `٬` thousands separator); dates displayed in Jalali
  (`YYYY/MM/DD` with Persian digits) from `purchase_date_fa`.