# Journal — TikoTime (Watch Inventory)

> Commit-style activity log. Newest entries first. One entry per meaningful action.

## 2026-10-01 — Layout-refactor preflight + test-isolation leak found

- Baseline recorded before any structural change: `147 tests OK`, `manage.py check` clean, images **139**, backups 42, exports 54, db `sha256=f753fc1cc299f31762d4c9a2b8751af27c0300dfb933abcda7a008b8cf69444f`. Rescue net verified at `/tmp/tiko-preflight` (full `data` copy + `code.tgz`; DB hash identical to the repo).
- **Pre-existing bug found (out of scope, to fix standalone):** the suite leaks **2 × 58-byte PNGs per run** into the real `data/images/` — `tests/test_services_misc.py:90,100` call `services.save_upload()` without `override_settings(IMG_DIR=…)` (write path `services.py:955-956`). Recorded as an OPEN known issue in `INDEX.md`; FR-010 forbids touching those test files during the refactor.
- **Artifact correction (this commit):** stale `۱۳۵`-image figures replaced with the measured `۱۳۹`, and the step-5 data gate became a before/after **image-set** comparison (SC-004, T047/T048, quickstart V4) so later full-suite gate runs cannot drift the count.
- Reason it matters: every gate run of the full suite adds 2 orphans, so any gate written as "= 135 files" would have failed for reasons unrelated to the refactor.


## 2026-09-10 — Full test suite (`e7d6628`)

- **147 tests / 10 modules** in the dedicated `tests/` directory (the established convention), all passing via `manage.py test tests`:
  - `test_jalali.py` — g↔j anchors (Nowruz 1404/1405), round-trips, leap years, `fa_num`, `parse_jalali_date` (Persian/Latin digits, all separators, ISO, 8-digit, invalid → None).
  - `test_utils.py` — `fa_date`/`fa_money`, tolerant parsers, phone normalization, `invoice_code`, all five `*_dict` builders incl. missing-product degradation.
  - `test_service_products.py` / `test_service_sales.py` / `test_service_infra.py` — every service function: queryset filters/sort fallback, create/update validation with exact Persian messages, duplicate codes (case-insensitive), cash vs deposit flows, stock flip + restore, deposit-receipt creation + date sync, settlement sync, `add`/`settle-full`, status flows, bulk deletes.
  - `test_dbhelpers_reports.py` — settings, brands (sorted), backup/restore/delete, `clear_database` on a throwaway sqlite file (data gone, ids restart at 1, settings kept), dashboard stats, monthly activity, brand breakdown (in-stock only).
  - `test_services_misc.py` — calendar month grid (35 cells) + day detail, report validation, uploads (multipart + JSON base64 + ext/size rejections), real openpyxl export/import round-trip.
  - `test_api_v1.py` — DRF endpoints: CRUD, native PATCH semantics, pagination, `summary` action, `{"error": ..., "ok": false}` contract, bulk-delete, 404 JSON.
  - `test_compat_contract.py` — the byte-level legacy JSON shapes the frontend depends on (plain arrays, `ok(...)` envelopes, wrapped creates, `{items, summary}`, `next_invoice_code`, pages, 404s).
- **Safety rule enforced by design:** tests never touch the real `data/db.sqlite3` — raw-sqlite helpers (`clear_database`, `backup_db`) run against `mock.patch`ed temp paths, because the Django test DB is in-memory and invisible to them.
- **Lessons:** `override_settings` cannot affect `dbhelpers` module-level constants (patch the module attrs instead); first draft of the clear-test wrote to the real DB path — caught and rewritten before commit; restore always leaves a `pre_restore_*.db` safety copy (asserted, not assumed).
- **Verified:** 147/147 pass, `check` clean, tree clean, no artifacts left in `data/backups/` (test-generated ones deleted).

## 2026-09-10 — API-first backend cleanup (`96687f8`)

- **Old static/legacy API views deleted:** the entire function-based API in `inventory/views/` (products, sales, payments, repairs, tracking, calendar, shared, backups, exportimport, settings_api, dashboard_api, common — ~1,550 lines) is gone. `inventory/views/` now contains ONLY `pages.py` (the 8 HTML page shells).
- **New service core — `inventory/api/services.py`:** every business rule (validation with the original Persian error messages, transactional sale+receipt creation, stock flip on sale/delete, cascade bulk deletes, settlement sync, invoice codes, image housekeeping, calendar/report/export logic) now lives in ONE module as plain functions raising `ApiError(status, message)`.
- **`/api/v1/` is now the real backend:** all 5 ViewSets perform writes directly through the services (no more `_legacy` adapters, no more PUT-juggling / `_complete_partial` merging — PATCH is native). Added `exceptions.py` so `ApiError` renders as `{"error": ..., "ok": false}` with the right status.
- **Frontend untouched:** the old `/api/*` routes remain via `inventory/api/compat.py` — thin adapters returning the EXACT legacy JSON shapes (`ok(...)` envelopes, wrapped `{product: ...}` creates, plain arrays, `{items, summary}` lists). Verified contract-by-contract against the JS (is_available, product_image, *_fa/*_display fields, res.path, res.deleted, next_invoice_code, error-toast shape).
- **Verified:** 86/86 E2E smoke checks across BOTH layers on a temp DB (CRUD, deposit receipts, settle-full, PATCH-preservation, filters, pagination, calendar day/month, exports xlsx/csv, import template, upload multipart+JSON, backups create/download/delete, database clear + id-restart, all 8 pages, 404 shapes). 3/3 Django tests pass, `check` clean, migrations in sync, real DB read smoke OK (7 products through both APIs).
- **Real bug found & fixed by the smoke run:** compat `api_brands` initially only allowed GET — brand-add POST (which the frontend sends) would 405. The old code's quirks were verified against a stash of the old code and preserved exactly (deposit-on-sold-out accepted, `add` doesn't flip `sale.is_settled`, `unpaid` count semantics).
- **English docstrings everywhere:** every class/function in `inventory/api/` (services, serializers, views, compat, exceptions, fields, urls) and `tikotime/urls.py` now documents purpose and behavior in English.

---
## 2026-09-08 — DRF API v1 (`5af7b97`)

- **New `inventory/api/` package** (1,082 lines): DRF 3.18 layer under **`/api/v1/`**, fully independent from the legacy `/api/*` views (which remain untouched for the current frontend).
  - `fields.py` — Jalali date converter + Persian-num helpers reused from `inventory.utils`.
  - `serializers.py` (495 l) — `Product/Sale/Payment/Repair/Tracking/SettingSerializer` porting every computed display field from `utils.py` dict builders (fa dates, weekday, availability/status fa+color, totals, paid_percent…).
  - `views.py` (519 l) — `ModelViewSet`s (filtering, ordering, search, bulk-delete actions) delegating writes to the battle-tested legacy view functions so business rules exist in ONE place (transactional sale+receipt creation, stock flip, cascade deletes, id-restart rules).
  - `urls.py` — DefaultRouter with `trailing_slash=''` (app convention; a 301 on POST would drop bodies).
- **Key fixes found by smoke tests:**
  - DRF default auth crashed (app has no `django.contrib.auth` by design) → `DEFAULT_AUTHENTICATION_CLASSES: []` + `UNAUTHENTICATED_USER: None` in settings.
  - Legacy detail views were PUT-only; PATCH fell through to **delete** → `update()` normalizes method, `partial_update` merges PATCH into current object values before delegating (`_complete_partial`).
- **Verified on temp DB copy:** full CRUD round-trip on all 5 resources; PATCH field-preservation per resource (sale buyer/phone/paid, payment name/amount, …); sale deposit → payment receipt created, settled flag correct; filters + pagination; all 8 pages 200; legacy API unchanged; `manage.py check` clean; existing 3 tests green.
- **Going forward:** new frontend work should target `/api/v1/`; legacy `/api/*` can be retired once the frontend migrates.
## 2026-09-08 — Cleanup: legacy Flask removal + dead-code sweep (331defd)
- **Removed:** `legacy_flask/` (app.py, database.py, reports.py, excel_io.py, run.sh/bat — ~2,900 lines), stale root `jalali.py` (superseded by `inventory/jalali.py`), old `tests/test_calendar_sale_deletion.py`, `.claude/PROGRESS.md`, stale `data/inventory.db` artifact.
- **Dead code swept:** `parse_date_or_none` from inventory/utils.py; unused `import json` from products/repairs/tracking views; stale bugfix narrative from sales.py docstring. Pyflakes run beforehand; all removals grep-verified unreferenced.
- **Ported:** calendar-sale-consistency tests to native Django `tests/test_calendar_sales.py` (3 tests: sale visible→deleted in both calendar views, deposit-receipt cascade on bulk delete, product-delete cascade). All 3 pass.
- **Docs:** README + .memory/INDEX.md updated to state Flask code fully removed.
- **Verify:** manage.py check clean, makemigrations --check clean, 8 pages 200, all JS node --check OK, zero flask references in code (memory COMMANDS.md history mentions are historical only).
- **Gotcha:** `sed -i` on this mount prints "preserving permissions" warnings — harmless.

---
## 2b9d117 — 2026-09-08 (session VIII, style)
**type:** style
**scope:** dark theme (static/css/app.css)

Apple-inspired dark pass (ref: apple.com/iphone-17-pro). User palette unchanged (#000000/#232324/#0070e2/#38383a/#f5f5f7 dark; #ffffff/#f5f5f7/#0070e2/#eeeef1/#232324 light).

- Dark bg = plain static `#000000`: `[data-theme="dark"] .bg-scene` forced to `#000`, `::after` glow removed, `.blob`s `display:none`, dark body `#000`. Light theme keeps its soft animated scene.
- Dark surfaces → Apple gray family: `--surface: rgba(29,29,31,0.68)`, `--surface-strong: rgba(44,44,46,0.92)`; 26px blur kept.
- Dark buttons glassy: new dark token `--btn-neutral-glass: rgba(56,56,58,0.55)` (translucent + existing 18px backdrop blur); `.btn-primary` flattened to solid `#0070e2`, hover `--accent-strong`.
- **Verified**: braces balanced; collectstatic --clear run BEFORE commit; served copy (read via `streaming_content` — WhiteNoiseFileResponse has NO `.content` attribute, that tripped the first check) contains every new rule; all 7 pages 200; cache auto-busts via static_v mtime.
- **Remember**: static_v() busts browser cache, but the SERVED copy is the collected one — always run `manage.py collectstatic --noinput` after editing static/.

---
---
## c5b9f29 — 2026-09-08 (session V, bugfix)
**type:** fix
**scope:** static serving / whitenoise (settings + jinja + templates)
**subject:** user saw zero visual changes — stale staticfiles copy + 1-year browser cache

- **User report:** «I don't see any changes … appearance hasn't changed» after the palette commit ab9d9a7. CSS itself was correct on disk and in git (tokens verified).
- **ROOT CAUSE 1:** app uses **whitenoise** (middleware + `CompressedStaticFilesStorage`, `WHITENOISE_MAX_AGE = 1 year`). WhiteNoise serves the **collected `staticfiles/` copy** (gitignored), last collected **Sep 6** — so every CSS/JS edit since (year pagination, brand cards, danger zone, full palette) was never served. `static/` edits are invisible until `collectstatic` runs.
- **ROOT CAUSE 2:** unversioned `/static/...` URLs + 1-year max-age = even after re-collecting, browsers would serve cached assets for up to a year.
- **Fix:** (1) `manage.py collectstatic --noinput --clear` — 14 files, 10 post-processed; collected app.css now has the new palette. (2) Cache-busting: new Jinja global **`static_v(path)`** in `tikotime/jinja.py` → `/static/<path>?v=<mtime-int>` (falls back to plain URL if file missing); applied to app.css + jalali.js + app.js + jalali-datepicker.js in base.html and the 6 page scripts. Every future static edit auto-busts cache on next load — **remember: still must re-run collectstatic after static changes** (whitenoise serves only staticfiles/).
- **Gotcha worth remembering:** Django test client hits whitenoise middleware → static responses are `WhiteNoiseFileResponse` (streaming) — `.content` raises AttributeError; read via `b''.join(r.streaming_content)`. Also `/` 302-redirects to `/dashboard` (pre-existing).
- **Verified end-to-end:** rendered pages emit `?v=1788816770` URLs; `/static/css/app.css?v=…` → 200 with btn-neutral ×4, #000000/#232324 present, old navy rgba(22,28,42) absent; all 7 other pages versioned; py_compile ok. Commit `c5b9f29`.

---
## ab9d9a7 — 2026-09-08 (session V, theme)
**type:** style
**scope:** app.css + base.html + app.js (theme tokens)
**subject:** user palette applied — glass design kept, colors swapped to neutral

- **User palette:** dark → main base #000000, secondary #232324, buttons #0070e2/#38383a, text #f5f5f7; light → #ffffff / #f5f5f7, buttons #0070e2/#eeeef1, text #232324. «appearance is great — just add these colors»: structure untouched, tokens recolored.
- **Token mapping:** `--bg-1`=main base, `--bg-2`=secondary base; blobs became neutral tints of the secondary base (light #e9e9ee/#f0f0f3/#e2e2e8, dark #2e2e30/#262628/#1c1c1e) — liquid-glass background preserved without the old blue cast. `--text-1` exact per palette; text-2/3 neutralized to Apple-style grays (light #48484d/#86868b, dark #aeaeb2/#6e6e73).
- **Buttons:** NEW `--btn-neutral` token — `.btn` + `.pager-btn` background now #38383a (dark) / #eeeef1 (light) instead of translucent surface. Primary = `--accent: #0070e2` with same-hue gradient top `--accent-strong: #1e80e8` (exact hex requested stays the dominant/read color). accent-soft rgba(0,112,226,…).
- **Dark surfaces rebuilt neutral:** `--surface` rgba(35,35,36,.60), `--surface-strong` rgba(44,44,46,.90) (from #232324 family, replacing navy rgba(22,28,42)/rgba(28,35,52)). Glass blur/borders/rim/shadow structure unchanged.
- **Global neutralization (sed):** bluish shadow/ring/hairline rgba(23,48,96|28,54,105|19,48,99 → rgba(0,0,0; rgba(23,43,82 → rgba(35,35,36 (also fixed --gray-soft). Theme-color meta: base.html default + app.js runtime switch now #ffffff/#000000.
- **Verified:** brace balance + both palettes asserted by script; zero stale values (#0a84ff/#0071e3/#dfeafa/#e9f0fb/#0a0f1a/#0d1524 and bluish rgba) remain anywhere; node --check on app.js; all 8 pages + root (follows pre-existing 302 → /dashboard, confirmed identical on clean tree via git stash) render 200. Commit `ab9d9a7`.

---
## c94df1f — 2026-09-08 (session V, feature batch)
**type:** feat
**scope:** dashboard + settings (yearly-reset workflow)
**subject:** chart year pagination + brand breakdown (count/purchase/sale/profit) + database clear for new year

Three features from session V (context was compacted mid-session — full details reconstructed here):

**1. Monthly-activity chart year pagination (dashboard):**
- New endpoint `GET api/reports/monthly-activity?year=<jy>` in `inventory/views/dashboard_api.py` (NEW file — was untracked until this commit). Jalali year validation; invalid/out-of-range → 400 with Persian error. No param = current year.
- `templates/dashboard.html` chart IIFE refactored: drawing logic extracted into `renderChart()`; `loadYear(jy)` fetches + re-renders with `.chart-loading` fade, guards concurrent loads; `updatePager()` sets `#chart-year-label` (Persian digits), syncs the h3 title + SVG aria-label, disables buttons while loading; `#chart-next-year` disabled at current Jalali year (resolved via `JalaliJS`, safe fallback). Initial render still uses server-provided `data-monthly` (no extra fetch on load). All visuals preserved: Catmull-Rom curves, gradient fills, dashed current-month marker, faded future labels, hover tooltip + cursor line.
- Simulated full script in Node with DOM stubs: prev → 1404 renders 12 real months (0 faded), next → back to 1405 (6 real + 6 faded), arrows enable/disable correctly.

**2. Inventory-by-Brand box metrics (dashboard):**
- `inventory/reports.py get_brand_breakdown()` now scopes to in-stock only (`available=True`; sold watches excluded — verified: brand sums = 29,000,000 of 72,300,000 total, sold 43,300,000 excluded) and adds `profit = Sum(sale_price − purchase_price)` (potential profit). Ordering kept: desc by purchase value. No signature change; `pages.py` caller untouched.
- Brand cards rebuilt in dashboard.html: brand + rank, «N عدد در انبار» subtitle, 3-col metrics row (ارزش خرید / ارزش فروش / سود بالقوه); profit green when ≥0, amber when negative. CSS: `.brand-item`, `.brand-top`, `.brand-metrics` (grid 260→300px), all via existing CSS vars (dark mode free). Math cross-checked against manual ORM aggregation for every brand; dev DB: رومانل 1 watch 17M/28M/11M, ویولت 1 watch 12M/35M/23M.
- NOTE (open item): top stat card «ارزش فروش کل انبار» still aggregates ALL products (pre-existing) — user may want it scoped to in-stock for consistency.

**3. Database clear for yearly reset (settings):**
- User workflow: enter everything all year → manual backup stored offsite → clear → start fresh. 
- `inventory/dbhelpers.py`: `count_records()` (preview) + `clear_database()` — auto safety backup `pre_clear_<ts>.db` FIRST, then one transaction deletes payments/sales/products/repairs/tracking, `DELETE FROM sqlite_sequence` for those 5 tables (ids restart at 1), VACUUM. Settings/brands/site icon/images preserved. `isolation_level=None` + explicit BEGIN/COMMIT for the transaction.
- API: `GET api/database/info` (preview), `POST api/database/clear` (require_POST; GET → 405). Wired through `views/__init__.py` + `urls.py`.
- settings.html danger-zone card below backup card: red border + «غیرقابل بازگشت» badge, live count pills (`.cc-item`, total in amber), button disabled when total=0, **double confirm**: dialog then typed phrase «پاک کن» (trim-compared; mismatch cancels with error toast). After clear: toast with deleted count, backups list + counts refresh.
- **Verified on temp copy only** (`TIKOTIME_DB=/tmp/tikot_clear_test.db`, copy of real DB; BACKUP_DIR monkeypatched to tmpdir — real data untouched, confirmed post-test: 6 products still in `data/db.sqlite3`): preview matched (6/4/2/1/1); clear emptied all 5 tables; brands+settings intact; pre_clear backup contained the 6 original products; info → all zeros; fresh Product got **id=1**.

---

## 7332513 — 2026-09-07 (session IV, ui change)
**type:** ui
**scope:** sidebar (base.html)
**subject:** removed count badge from Watch Inventory nav item; other badges kept

- **User request:** «عدد کنار بخش انبار ساعت‌ها در منوی کنار حذف شود؛ بج‌های تعمیرات، پیگیری و پرداخت‌ها بماند.»
- The products nav badge was `nav_badge_low` (count of out-of-stock watches, title «ساعت‌های ناموجود»). Removed the `{% if nav_badge_low %}…{% endif %}` line; left an HTML comment noting it was removed per user request. `nav_badge_low` is still computed in the context — only display removed, so it can be restored with one line.
- **Verified live:** dashboard 200; remaining badges exactly 3 — «تعمیرات در جریان» (repairs), «سفارش‌های در جریان» (tracking), «فقره‌های با مانده بدهی» (payments); products badge absent (grep count 0). Server stopped. Commit `7332513`.
- **Gotcha re-confirmed:** `pkill -f` self-match — a shell whose command line contains the plain `manage.py runserver 127.0.0.1:8765` string kills ITSELF when the same command also pkills that pattern (bracket trick in the pattern doesn't help if another part of the same command line matches plainly). Always run pkill and the server-start in SEPARATE shell invocations.

---


## 4fe5591 — 2026-09-07 (session IV, bugfix)
**type:** fix
**scope:** settings / app.js
**subject:** site-icon upload was silently swallowed by app.js auto-binding — now fixed + hardened

- **User report:** «انتخاب آیکون هیچ اتفاقی نمی‌افتد — آیا دکمه‌ی Apply لازم است؟»
- **ROOT CAUSE (real, confirmed):** app.js `$$(".img-upload").forEach(setupImageUpload)` auto-bound the icon wrapper in settings.html (same class). Its change handler runs FIRST, starts a generic multipart upload, and **synchronously clears `input.value = ""`** → the page's dedicated icon handler (bound second) reads `files[0]` → already empty → `return`. Result: icon uploaded as generic image, `site_icon` setting NEVER set, no preview update, no icon toast — "nothing happens". Server side was always fine (upload + /api/settings/site-icon verified by curl).
- **Debug journey (recorded for reuse):** CDP/headless Chromium harness (node 24 built-in WebSocket, /tmp/icon_cdp.js pattern): network capture showed `ERR_ALPN_NEGOTIATION_FAILED` on multipart POSTs with CDP-injected files — a SNAP-CHROMIUM artifact (confined browser can't read host files set via DOM.setFileInputFiles; JS-built `File`/Blob uploads work). Classic bug-masking lesson: `input.value=""` cannot clear a `defineProperty`-mocked FileList, which is why the first CDP test "passed" while the real flow was broken. Always pair mocked-input tests with handler-order analysis.
- **Fix:** (1) app.js auto-binding now skips `[data-manual]` (`.img-upload:not([data-manual])` in both init + modal:opened); settings icon wrapper marked `data-manual`. (2) Icon upload switched to robust JSON/base64 path: `api_upload` now accepts both multipart (unchanged for products/repairs) and `{kind,name,data}` JSON (dataURL/base64, 2MB cap, shared `_save_uploaded`). (3) UX: preview image is clickable, filename + «در حال ذخیره…» shown live, explicit success toast («همین حالا اعمال شد ✓»), button disabled during upload, cache-busted preview, placeholder SVG fixed (`innerHTML` on `<img>` never worked → inline data-URI src). **Answer to user: no Apply button — applies instantly on select**, now stated in the hint text.
- **Verified:** node --check; manage.py check; curl JSON upload (200, real PNG saved); headless full-flow with mocked File → single JSON upload, no stray multipart, site_icon persisted, correct toast, products-page auto-binding regression clean (1 img-upload bound, no exceptions). All test icon files deleted, site_icon reset to "", server stopped. Commit `4fe5591`.

---


## 7f1a632 — 2026-09-07 (session IV, feature)
**type:** feat
**scope:** calendar
**subject:** reference code shown on day-box items — رفرنس for buy/sell, watch_code for repairs

- **User request:** «شماره رفرنس ساعت خریداری‌شده، فروخته‌شده و تعمیری هم نمایش داده شود.»
- **Field reality:** purchases (`product_dict`) and sales (`sale_dict`, from linked product) have `reference`; Repair has NO reference column — its identifier is `watch_code` (user's own «کد ساعت» convention from the repair form), so repairs show that labeled «کد:».
- **eventItem meta line now:** buy/sell → `رفرنس: <reference>` (empty if the product has none); rep_in/rep_out → `<customer> — کد: <watch_code>` (parts omitted when blank). Card stays otherwise minimal per 1115b6d.
- **Verified:** node --check pass; isolated render test (buy «رفرنس: 2105», sell «رفرنس: R-99», rep «اسدی — کد: WC-12», all with image); live API real data: 2026-09-06 sales refs 3185 / LJ.160.21.721, repair «الکسا» code 2019 customer اسدی, 2026-09-01 purchase ref 0595. Server stopped. Committed `7f1a632`.

---


## 1115b6d — 2026-09-07 (session IV, feature)
**type:** feat
**scope:** calendar
**subject:** day-box items minimized to image+name+price (repairs: +customer, no price); totals جمع مبلغ خرید / جمع مبلغ فروش

- **User request:** «جعبه‌ی سمت چپ فقط تصویر، نام ساعت و قیمت را نشان دهد — خرید: قیمت خرید، فروش: قیمت فروش، تعمیر: فقط تصویر و نام ساعت و نام شخص — و زیر خریدها و فروش‌ها جمع مبلغ خرید و جمع مبلغ فروش.»
- **eventItem changes (static/js/calendar.js:93):** removed the sub-line for buy/sell (supplier / sale-type+buyer+phone gone — details remain in the click modal); buy price now `purchase_price_display` (was `total_value_display` — same value post-quantity-removal but explicit); sell price `final_price_display || sale_price_display` (final==sale when no discount, discounted price otherwise); repairs (`rep_in`/`rep_out`): NO price element, meta = customer name only (`customer_name || customer` — the old code read `e.customer` which repair_dict doesn't even have, so customer never showed before); name resolution `name || product_name || watch_name`; image `image || product_image` fallback (same as detail modal).
- **Totals:** purchases → «جمع مبلغ خرید» (sum of `purchase_price` numeric, blue); sales → «جمع مبلغ فروش» (sum of `final_price`, green). REMOVED the «جمع سود روز» row per the minimal-box request (profit still visible per-sale in the click modal and on the dashboard chart). Was: «جمع ارزش خرید روز»/«جمع فروش روز»+«جمع سود روز».
- **Verified:** node --check pass; isolated eventItem render test for all 4 kinds (img/price/meta flags correct — sell img:false in first run was a test-object artifact using old keys, re-verified true with product_image fallback); live API data shapes confirmed: 2026-09-06 sales carry name+image+final_price_display, rep_in «الکسا/اسدی», 2026-09-01 purchase «ویولت زنانه کرنو/۱۲٬۰۰۰٬۰۰۰». Server stopped. Committed `1115b6d`.

---


## 6364203 — 2026-09-07 (session IV, fix)
**type:** fix
**scope:** calendar
**subject:** sold watch image missing in day-panel list — sale_dict key mismatch (product_image/product_name vs image/name)

- **User report:** day box shows purchase/repair thumbnails but sold products show the placeholder clock icon until clicked.
- **Root cause:** the shared left-box renderer `eventItem(e, kind)` in `static/js/calendar.js:93` reads `e.image` and `e.name`. Month-view sale entries (built inline in `calendar.py` month loop) carry `image`/`name`, but the DAY panel (`api_calendar_day`) used `sale_dict`, whose keys are `product_image`/`product_name` → falsy `e.image` → placeholder branch. Purchases (`product_dict`) and repairs (`repair_dict`) already had `image`/`name`, hence «everything is perfect for purchases and repairs».
- **Fix (backend only, calendar.py):** day API now emits `{**sale_dict(s), "name": product.name or "محصول حذف‌شده", "image": product.image or ""}` — additive aliases, legacy keys kept (serializer gotcha). No JS change; the already-proven eventItem path picks them up. Deleted-product sales degrade gracefully (empty image → placeholder, name fallback).
- **Verified live:** `check` clean; `/api/calendar/day?date=2026-09-07` sale entry now has `name: الکسا اتومات`, `image: img_20260906_140316_7c34f189.webp` (plus legacy `product_image`), customer + final_price_display intact. Server stopped. Committed `6364203`.

---


## 7551e14 — 2026-09-07 (session IV, feature)
**type:** feat
**scope:** sales (inventory sell modal)
**subject:** optional manual invoice-code input — user enters their own value, auto TT-code only when left empty

- **User request:** «در بخش فروش صفحه انبار، زیر فیلد نوع فروش یک فیلد اختیاری کد فاکتور اضافه کن تا خودم مقدارش را وارد کنم — نه مقدار پیش‌فرض تو.»
- **Why a migration was needed:** `invoice_code` was NOT a DB column — it was computed on the fly in `sale_dict` as `invoice_code(r.id, r.sale_date)` → `TT-<jy><jm>-<sale_id:04d>` (utils.py:141). To store a manual value, added `Sale.invoice_code` CharField(40, blank) — migration `0006_sale_invoice_code` (applied).
- **Changes:** models.py (field) · utils.py `sale_dict`: `r.invoice_code or invoice_code(...)` (single display point — sold list, detail modal, calendar all follow) · sales.py `_create`: accepts `invoice_code` payload key, `clean()`ed, ≤40 chars, **duplicate rejected** with Persian error, passed to `Sale.objects.create` · products.html: new optional field «کد فاکتور (اختیاری)» right below «نوع فروش», dir=ltr, maxlength=40, with `#invoice-code-hint` moved under it and reworded to «اگر خالی بگذارید، خودکار صادر می‌شود: TT-…» · products.js: `invoice_code` added to sell payload; `form.reset()` on modal open clears it (line 295 path).
- **Bonus fix found while testing:** `/api/sales?q=` search did NOT cover invoice_code — `q=MY-CODE` returned nothing. Added `Q(invoice_code__icontains=q)` to the search filter in `api_sales`.
- **Verified live (runserver):** POST with `invoice_code=MY-CODE-77` → stored + echoed in `sale.invoice_code`; duplicate POST → `{"ok":false, "error":"کد فاکتور «MY-CODE-77» قبلاً استفاده شده است"}`; POST with empty code → auto `TT-140506-0014`; search `q=MY-CODE` finds it after the Q-fix; field renders on `/products` (grep count 1). Test sales 13/14 deleted afterward — DB back to 4 original sales, both test products re-available. `check` clean, migration applied, `node --check` pass. Server stopped. Committed `7551e14`.
- **Note:** edit flow (sold.js PUT) does not expose invoice_code — out of scope of the request; the manual code is fixed at creation for now.

---


## 6e8cce4 — 2026-09-07 (session IV, hotfix)
**type:** fix
**scope:** sales (sold page)
**subject:** /sold page rendered nothing — missing $() wrapper killed the whole sold.js script

- **Symptom (user):** «صفحه فروش‌ها هیچ چیز نشان نمی‌دهد». API `/api/sales` and the template were fine (curl 200, 4 sales, all fields present), but headless Chromium showed 0 rows.
- **Root cause:** `static/js/sold.js:323` — `["#filter-date-from","#filter-date-to"].forEach((sel) => { sel.addEventListener(...) })` was missing the `$()` wrapper, so `sel` was the selector STRING → `TypeError: sel.addEventListener is not a function`. Because the throw happens at TOP-LEVEL evaluation, everything after it — including the `DOMContentLoaded → loadSales()` registration — never ran → table stayed empty forever. Note the earlier `node --check` could not catch this (it's a runtime error, not syntax).
- **Fix:** one char-class change — `$(sel).addEventListener(...)`. Audited all `static/js/*.js` for the same pattern (`[...].forEach((sel)=>` loops): `products.js:481/484` already correct; bug was only in sold.js.
- **Debug technique that nailed it (remember):** grep-based ID checks and API curls were all green — only real execution exposed it. `chromium --headless --no-sandbox --virtual-time-budget=6000 --dump-dom URL` + `--enable-logging=stderr --v=0` prints CONSOLE errors to stderr. Repro signature: summary chips rendered («فقره» present) but `ev-row` count 0 and `#sold-empty` still hidden = render() threw between chips and rows.
- **Verified after fix:** node --check pass; headless DOM now has 4 `ev-row`s, no console errors; row for sale 12 shows every required detail — image `/data/images/img_….webp`, name «الکسا اتومات», reference pill `2105`, site-code pill `121553`, office-code pill `159`, buyer «علی», phone ۰۹۱۲۲۴۶۰۳۵۷, Jalali date ۱۴۰۵/۰۶/۱۶. Click-row detail modal (showSaleDetail) adds invoice code, prices/discount/profit/purchase, brand, supplier, sale type, payment breakdown, settlement status, notes.
- Committed `6e8cce4` (sold.js only). Smoke server stopped.

---


## 3984de6 — 2026-09-07 (session IV, correction)
**type:** fix
**scope:** dashboard
**subject:** 12-month chart corrected per user: THREE lines (purchases, sales, profit) — not profit-only

- **User clarification:** «در نمودار ۱۲ماه، خرید، فروش و سود فروش — یک نمودار با سه خط که مشخص باشد هر ماه چه خریدی، چه فروشی و چه سودی داشتم.» The earlier task_0001 interpretation (profit-only green line, commit `277eacf`) was wrong.
- **Fix (templates/dashboard.html only — `reports.get_monthly_activity` already returned `revenue`/`purchase_value`/`profit` per month, no backend change):** card retitled «فعالیت ۱۲ ماه اخیر — خرید، فروش و سود» with a 3-item legend (فروش `--accent` آبی / خرید `--amber` کهربایی / سود `--green` سبز — all theme-aware vars); Y-scale now maxes over all three series; three paths drawn back-to-front (purchases w2.2 → sales w2.6 → profit w2.8, subtle green area under profit kept); dots per series per month; tooltip now lists فروش/خرید/سود فروش (+تعداد فروش) per month with matching colors; empty-state text mentions خرید یا فروش.
- **Verified:** `manage.py check` clean; live curl of /dashboard shows 3-item legend + new title + monthly JSON with `revenue`/`purchase_value` keys; inline chart JS extracted and `node --check` pass; server stopped. Committed `3984de6`.

---

## f985c66 — 2026-09-07 (session IV, completed)
**type:** feat
**scope:** multi-page-features
**subject:** All 22 items of the session-IV request done, verified live, committed per feature

- **Commits (in order):** `277eacf` dashboard (chart initially profit-only — corrected to 3 lines خرید/فروش/سود in `3984de6`; brand sales value, out-of-stock images) · `7a4ed12` inventory/sale modal (shared Jalali popup datepicker `static/js/jalali-datepicker.js`, final-price required + thousands-sep, buyer name+phone required, invoice code TT-YYYYMM-NNNN via `utils.invoice_code`) · `841dd1d` calendar (images + full detail modals, day-panel price fix) · `daaf190` sales (sold-list subtitle, invoice in detail, sale-date edit syncs linked Payment.pay_date) · `28ea0fb` repairs/tracking (shared `bindMoneyInput`/`moneyIn` moved to app.js) · `8efd352` payments (product image + full details on cards/edit, settlement date: new `settled_at` on Sale+Payment, migration `0004_sale_payment_settled_at`, inventory picker hidden when editing) · `170e266` settings (store name drives sidebar brand + tab title on every page, live update on save) · `f985c66` settings (default name = «Tick O Time», migration `0005_store_name_default` seeds the Setting row).
- **Settings item ㉑ note:** site-icon file upload already existed and persists (`/api/settings/site-icon` → `Setting.key=site_icon`, rendered in favicon + sidebar brand mark by `page_ctx.site_icon`).
- **Final verification (task_0009):** `manage.py check` clean · `makemigrations --check` in sync (0001–0005 applied) · `node --check` pass on all 9 files in `static/js/` · live curl: all 8 pages 200, `/api/products`, `/api/calendar/day`, `/api/payments`, `/api/settings` return data; store name «Tick O Time» renders in `<title>` and `.brand-name`.
- **Serializer gotcha to remember:** when adding keys, keep legacy ones too (see session II) — this session followed it (payment_dict extended, nothing dropped).

---

## c4e8a12 — 2026-09-06 (session IV)
**type:** chore
**scope:** git
**subject:** Git repository initialized — every completed task gets a commit from now on

- **Repo:** `git init -b main` + local identity (`meti <meti@local>`) + global `safe.directory` exception (repo dir owned by root → "dubious ownership" error otherwise).
- **`.gitignore` (new):** `__pycache__/`, `*.py[cod]`, `.venv/`, `staticfiles/`, `data/` (live DBs `db.sqlite3`/`watch_inventory.db`, images, backups, exports), `.codebase-memory/`. `.memory/` + `.claude/` ARE versioned.
- **Commit `776891f` (initial):** 71 files / 12,658 insertions — full working app (Django port complete & verified, all session I–III fixes included).
- **New standing rule (user request):** after each completed task, commit with a descriptive message.
- **Bonus finding:** `static/js/jalali.js` exists (client-side Jalali math) — reuse it for the planned Jalali date-picker component.
- Next: resume session IV feature work (22-item list, state in JOURNAL b7d2f90); commit per page/feature as each is completed and verified.

---
## b7d2f90 — 2026-09-06 (session IV, in progress)
**type:** explore
**scope:** multi-page-features
**subject:** Large 8-page feature request received — context gathering started, NO code edits yet

**Full request breakdown (user, verbatim intent):**
- **Dashboard:** ① 12-month activity chart = watch-sale profit ONLY (green), no purchases line ② Brand box: show sales value next to purchase value ③ Out-of-Stock box: show watch images.
- **Inventory page:** ④ purchase date → popup Jalali date-picker (month+year filters, mouse-selectable) ⑤ sale modal: sale-price field fixed; REQUIRED field = final discounted price, thousands-separated while typing ⑥ Deposit section: final-price field too, thousands-sep ⑦ payment-method fields optional/informational only ⑧ sale date → same popup picker ⑨ buyer name + phone REQUIRED ⑩ show invoice code under sale-type field.
- **Calendar:** ⑪ product image next to sale/purchase/repair details; click → all details.
- **Sales page:** ⑫ sold product not appearing — investigate ⑬ verify payments/deposit rows appear on correct date AND in Sales page ⑭ clicking a sold product → ALL details incl. watch image.
- **Repairs:** ⑮ repair cost thousands-sep while typing. **Tracking:** ⑯ price thousands-sep while typing.
- **Payments:** ⑰ show watch image ⑱ all product details (reference, office/site codes, …) ⑲ show purchase date + settlement date; settlement date also in Sales list ⑳ remove «محصول از انبار» search field from Edit modal (keep in Add).
- **Settings:** ㉑ site-icon upload + save ㉒ site name = «Tick O Time».

**Findings so far (files read: reports.py, dashboard.html [truncated tail], utils.py, models.py):**
- Chart is inline JS at the end of `templates/dashboard.html`: two lines — `revenue` (accent) + `purchase_value` (amber), fed by `reports.get_monthly_activity()` which already returns `revenue/profit/count/purchase_value` per Jalali month → ① = drop purchase line, plot `profit` in `var(--green)`, adjust tooltip.
- `reports.get_brand_breakdown()` returns only brand/count/purchase `value` → ② needs `Sum("sale_price")` added + template box edit.
- `payment_dict` has only `product_name` → ⑰/⑱ need product join fields (image, reference, office_code, website_code, purchase_date…).
- No `settled_at`/`settled_date` on `Sale` (only `is_settled` bool, `created_at`) → ⑲ needs a new model field + migration, or derive from linked Payment `updated_at`. Decision pending.
- No invoice-code field on `Sale` → ⑩ likely format from `sale.id` (e.g. فاکتور-<id>); decision pending.
- No reusable Jalali date-picker component exists → ④/⑧ need a new shared JS component (check `static/js/` for existing jalali math first).
- Thousands-sep-while-typing: products.js has `moneyIn()` helper → extract to shared util for ⑤/⑥/⑮/⑯.
- E2E history says `/api/sales` lists ALL sales regardless of `is_settled` — ⑫ must be reproduced live before fixing (sold.html/sold.js + views/sales.py not yet re-read).

**Next steps:** read dashboard.html 60–200, products.html/js, views/sales.py, sold.html/js, payments.html/js + views/payments.py, calendar.js/py, repairs/tracking js, settings.html + settings_api.py + shared.py; check static/js for jalali lib; then implement in page order (shared datepicker + money-format util first).

---
## a1c7e44 — 2026-09-06 (session III)
**type:** revert
**scope:** inventory-quantity
**subject:** Quantity field removed — reverted to one-row-one-watch model (user request)

- **Full revert of f5a9d21's quantity feature** (user asked to go back to the previous state): `products.quantity` removed from the model (`0003_remove_product_quantity`, applied to `data/db.sqlite3`), form field + table column removed from `templates/products.html`, render/edit/payload references removed from `products.js`, `product_dict` back to unit-price totals (`total_value` = purchase price, `total_sale_value` = sale price — legacy semantics), Excel headers/rows/import back to the 11-column format (import still tolerates old files that had a count in the وضعیت column), `_REQUIRED_COLS` quantity entry removed, sale flow back to available=True→False on sale, True on delete (F-import and stock guard removed).
- **Kept (pre-existing bug fixes, unrelated to quantity):** restored legacy serializer keys (`total_value*`, `total_sale_value*`, `profit_per_unit*`, `availability_fa`, `purchase_date_weekday`, `status_color`, `is_warranty_fa`, `paid_percent`, `TRACKING_STATUS_COLOR`), edit no longer resurrects sold products (`values.pop("available")` in `_update`), `.claude/launch.json` → `manage.py runserver 8000`.
- **Migration history:** 0002 (add) → 0003 (remove) both kept — Django requires the chain; the column never ships to fresh DBs.
- **Verified:** `manage.py check` clean, `makemigrations --check` = "No changes detected", migration applied OK, `PRAGMA table_info(products)` has no quantity column, `node --check` products.js OK, grep shows no quantity references outside migration files + the intentional import fallback.

---
## f5a9d21 — 2026-09-06 12:55
**type:** fix
**scope:** inventory-quantity
**subject:** Quantity field restored end-to-end + dropped serializer keys fixed + edit-flips-availability bug + stale launch.json

- **Quantity field restored (user request):** the Add-Product form had no تعداد field (removed in the 1404/06/07 Flask redesign, never restored). Re-added end-to-end: `products.quantity` column (`0002_product_quantity`, applied), form field + table column in `templates/products.html`, `products.js` (render/edit payload/sale-modal stock hint), `product_dict` serializer, Excel export/import (`تعداد` column; legacy files that stored the count in the وضعیت column still parse), and `dbhelpers._REQUIRED_COLS` so old restored backups get the column.
- **Stock semantics:** selling decrements quantity (ناموجود only at 0); deleting a sale/bulk-deleting sales restores one unit each (`F("quantity") + 1`); API now rejects selling an unavailable/0-stock product (previously only the frontend disabled the button).
- **Bug fix 3 (NaN chips / undefined cells):** `product_dict` dropped legacy keys `total_value*`, `total_sale_value*`, `profit_per_unit*`, `availability_fa`, `purchase_date_weekday` → inventory summary chips showed `NaN` and the سود واحد column `undefined`. Recomputed with quantity (total = unit price × qty). `repair_dict` gained `status_color`, `is_warranty_fa`, `delivery_date_weekday`; `tracking_dict` gained `status_color` (`TRACKING_STATUS_COLOR` added to utils); `payment_dict` gained `paid_percent` (payments progress bars were stuck at 0).
- **Bug fix 4 (edit resurrects sold items):** `products._update` applied `available=True` from `_product_values` unconditionally — editing a sold (ناموجود) product flipped it back to موجود while its sale still existed. Now availability is preserved unless the quantity actually changes (`available = quantity > 0` on change; zero allowed on update, min 1 on create).
- **Fix 5:** `.claude/launch.json` still launched the removed Flask `app.py` on port 5000 → now `manage.py runserver 8000`.
- **Verified:** `py_compile` all touched files, `manage.py check` clean, `makemigrations --check` = "No changes detected", migration applied, `node --check` products.js OK. Live curl smoke test: create qty=3 → 3 sales → qty 0/ناموجود → 4th sale rejected («این ساعت ناموجود است») → edit with qty 0 stays unavailable → delete sale → qty 1/موجود. Test rows deleted; real `data/db.sqlite3` otherwise untouched; server stopped.

---

## e4b2c08 — 2026-09-06 01:30
**type:** feat
**scope:** django-port
**subject:** Django port completed & fully verified — qty remnant fixed, is_available bug fixed, 75/75 tests pass

- **Indexing:** repo indexed into codebase-memory graph (797 nodes / 3,549 edges; project `media-MyShit-Works-Tick-O-Time-DB-Watch-Inventory`). Only flagged file: `templates/dashboard.html` (parse_partial at line 108 — cosmetic).
- **Bug fix 1 (qty remnant):** `templates/dashboard.html` line ~100 still referenced removed `qty` dict key → rendered `{{ no such element: dict object['qty'] }}` on dashboard AND inside the Add-Watch modal area of the inventory list. Replaced with the `available`-based (موجود/ناموجود) display per the 1404/06/07 design decision.
- **Bug fix 2 (real, found by testing):** `inventory/utils.py::product_dict` returned only `available` but ALL frontend JS uses `p.is_available` (`static/js/products.js` lines 47/88/95/189, `static/js/calendar.js` line 151) → availability badges, available-count chip and the "ثبت فروش" button were broken for every row. Added `"is_available": bool(r.available)` next to `available`.
- **Full E2E test run** (test-client script, isolated DB via `TIKOTIME_DB=/tmp/...`): **75/75 PASS, 0 FAIL** — pages (8), products CRUD + duplicate-code rejection, brands, sales (cash w/ breakdown, discount, deposit → auto Payment receipt, Persian phone → latin, available flip on sale/delete), payments (remaining math, /add over-remaining rejected, settle-full cascades to sale.is_settled + paid_cash, manual receipt, unpaid filter), repairs (status flow, delivered auto return_date, bulk delete, search), tracking, Jalali calendar (events + day detail), settings, all 5 exports (xlsx/csv) + import template, Excel import (1 added + 1 updated verified), image upload (response key `path`) + serving, backups (create/list/download/upload valid+invalid/restore/delete), sale-delete → product available again, 404 JSON.
- Status-name facts verified: repairs `received|in_progress|waiting_parts|done|delivered`; tracking `new|ordered|found|delivered|cancelled`; bulk-delete returns `deleted=len(ids)`.
- **README.md rewritten in Persian** (~2.7KB): install, venv, runserver, usage per section, backup/export notes.
- Verified real DB untouched; server stopped at session end (`pkill -f manage.py runserver`, port 8000 free); temp test DB/xlsx/images cleaned.

---


## a3d7f19 — 2026-09-03 19:44
**type:** chore
**scope:** memory
**subject:** memory checkpoint: save all progress (Sales-page bug + Django port state)

- Full progress checkpoint written to `.memory/` at user request: this journal (entries 9b2e4c6, 7f1d0a8, a3d7f19), updated `INDEX.md` (Django migration state + known-issue list), and new `COMMANDS.md` (persistent log of every command executed, per user request).

---

## 9b2e4c6 — 2026-09-03 19:40
**type:** chore
**scope:** memory
**subject:** handoff: record pending Django-port work and open decisions

- Pending (user paused work with «stop»):
  1. Finish Django port — views package (products/sales/repairs/tracking/payments/calendar/export-import/backups/settings), URL wiring, template integration via django-jinja2 (UI/UX must stay untouched).
  2. Fix Sales-page bug **in the Django rewrite** (see 7f1d0a8): list must include deposit sales.
  3. Full DB reset (`makemigrations` + `migrate` on a fresh SQLite file) so the user can test from scratch.
  4. Run professionally in a virtualenv via `requirements.txt` (no shell script — user explicitly rejected `run.sh`).
  5. Performance: indexes already declared in models; keep queries batched (no N+1) and reuse the existing JS as-is.
  6. Tests: user will ask later — do NOT write tests until requested.
- Open items to verify when resuming: `inventory/views/` and `inventory/management/commands/` are empty packages; `inventory/migrations/` has no migration files yet; templates still reference `/static/...` and `/data/images/...` paths (must map to Django static/media serving); `excel_io.py` not yet ported.

---

## 7f1d0a8 — 2026-09-03 19:30
**type:** explore
**scope:** sales
**subject:** diagnose: deposit sales never appear on the Sales page

- User reported: «when a product is sold, it does not appear there [Sales page]».
- Root cause found in `legacy_flask/app.py::api_sales` (line ~607): the list query filters `WHERE s.is_settled = 1`, but deposit (بیعانه) sales are created with `is_settled = 0` (only flips to 1 when the receipt is fully settled via payments «settle-full»/«add»).
- Consequence: a product sold as deposit disappears from inventory (`available = 0`) **and** is invisible on the Sales page until fully paid — looks like the sale vanished.
- Evidence the UI intends to show deposits: `static/js/sold.js` defines `PAYMENT_BADGE = {cash: نقدی, deposit: بیعانه}` (amber badge) and the edit modal supports `payment_type=deposit`.
- Correct fix (to apply in Django port): filter by payment lifecycle, not settledness — e.g. list all sales (or `is_settled IN (0,1)`) and keep the بیعانه badge; settledness stays a payment-page concern. Calendar already lists both types.

---

## 4c8b2e1 — 2026-09-03 18:05
**type:** feat
**scope:** django
**subject:** scaffold Django rewrite: project, app, models, settings, requirements

- User decision: rebuild the app on **Django** instead of Flask; keep UI/UX byte-identical; run via venv + `requirements.txt` (no shell script); optimize for speed; tests come later on request.
- Moved the entire legacy Flask code to `legacy_flask/` (reference only — `app.py`, `database.py`, `excel_io.py`, `reports.py`, old `jalali.py`).
- Created `requirements.txt` (pinned): `Django==5.2.6`, `Jinja2==3.1.6`, `gunicorn==23.0.0`, `whitenoise==6.11.0`, `openpyxl==3.1.5`.
- Django project `tikotime/`: `settings.py` (SQLite in `data/`, whitenoise for static, Jinja2 template env for the existing templates), `jinja.py` (Jinja2 environment exposing `fa_date`/`fa_money`/`fa_num` and the same template globals Flask injected), `urls.py` (page routes mirroring legacy paths `/dashboard`, `/products`, …), `wsgi.py`, `manage.py`.
- App `inventory/`: `models.py` — ORM models mirroring the repaired legacy schema (`Setting`, `Product`, `Sale`, `Payment`, `Repair`, `Tracking`) with proper PK/FK (`Sale.product` CASCADE, `Payment.sale` CASCADE, `Payment.product` SET_NULL) and covering indexes for the hot sort/filter columns; ISO-string dates kept for drop-in compatibility with the existing JS; `jalali.py` copied unchanged; `utils.py` (fa_date/fa_money/parsers, product/sale dict serializers matching legacy JSON shape); `reports.py` (dashboard stats ported to ORM aggregates).
- Scaffolded empty packages: `inventory/views/`, `inventory/management/commands/`, `inventory/migrations/` — contents pending (see 9b2e4c6).

---

---

## f4a8c22 — 2026-09-03 17:05
**type:** fix
**scope:** db
**subject:** repair: rebuild products/sales with real PK/FK, fix NULL ids and raw Jalali dates

- Root cause of «deleted sales still showing in Calendar»: production `products`/`sales` tables had `id INT` (no PRIMARY KEY) instead of `INTEGER PRIMARY KEY`, so `PRAGMA foreign_keys=ON` cascades never fired — deleting a product left orphan sale rows that kept appearing in the Calendar as «محصول حذف‌شده», and inserts could even produce `id = NULL` rows that were undeletable from the UI (one found in production, customer «علی»).
- Added idempotent repair migration in `database.py::_migrate_inner`: rebuilds `products`/`sales` with full DDL (PK + FK ON DELETE CASCADE) using the existing `__rebuild` pattern, only when `PRAGMA table_info` shows the id column is not a true INTEGER PK.
- Assigns ids to NULL-id rows (collision-safe), normalizes raw Jalali sale dates (e.g. `1405/06/07` → `2026-08-29`) to ISO, adds missing columns for very old schemas, guards `payments`-update step, and syncs `sqlite_sequence` (guarding DBs where it doesn't exist yet).
- Migrated the real production DB after backing it up (see d9e1b05): all 4 products / 11 sales / 22 settings preserved, `integrity_check=ok`, `foreign_key_check` clean, NULL-id row now id=12 with correct ISO date.

---

## c5d9e17 — 2026-09-03 16:55
**type:** fix
**scope:** sales
**subject:** store parsed ISO dates, not raw Jalali strings, on sale create/deposit receipt

- `api_sales_create` parsed the incoming Jalali date (`۱۴۰۵/۰۶/۱۲` — the format the UI sends via `todayJalaliStr()`) but then INSERTed the raw string into `sales.sale_date`, so the row could never match the calendar's ISO date-range queries.
- Now inserts `parsed` (ISO) for `sales.sale_date`, and the auto-created deposit receipt (`payments.pay_date`) also stores `parsed`, matching the standalone payments route convention.
- `api_sales_update` already stored `parsed` — verified, no change needed.

---

## b3e7f60 — 2026-09-03 16:40
**type:** fix
**scope:** calendar
**subject:** auto-refresh calendar on bfcache back-navigation and tab focus

- Calendar is a live query over `sales`, but the page could show stale data after a sale was deleted elsewhere (browser Back restores the page from bfcache without refetching; another tab/computer on the LAN could delete while the calendar sits open).
- Added `refreshCalendar()` in `static/js/calendar.js`: re-fetches the current month and re-renders the selected day panel on `pageshow` (when `event.persisted`) and on `visibilitychange → visible`. Network errors are swallowed so the current view survives offline blips.

---

## d9e1b05 — 2026-09-03 16:28
**type:** chore
**scope:** data
**subject:** backup production DB before structural migration

- Copied `data/watch_inventory.db` → `data/backups/pre_migration_backup_20260903.db` (90,112 bytes) before running the PK/FK repair migration against the real database.

---

## e8c4a93 — 2026-09-03 17:10
**type:** test
**scope:** calendar
**subject:** add 37-check integration suite for sales/calendar consistency

- New `tests/test_calendar_sale_deletion.py` (Flask test client + temp DB via `TIKOTIME_DB`), covering: legacy-schema migration repair (NULL ids, raw Jalali dates, PK/FK rebuild, id preservation, sequence sync, no id collisions), Jalali→ISO date storage, calendar month/day visibility, single + bulk sale deletion removing entries from both calendar views, product-delete cascade removing its sales from the calendar, deposit receipt lifecycle, legacy undeletable row becoming deletable, and zero orphans in DB.
- Result: **37/37 PASS**. Run: `.venv/bin/python tests/test_calendar_sale_deletion.py`.
- App boot smoke-tested after changes: `/calendar`, `/payments`, `/api/calendar` → 200.



---

## a1f9c3e — 2026-09-03 00:00
**type:** chore
**scope:** memory
**subject:** init: create local memory/journal system

- Created `.memory/` directory at project root as the persistent local memory store.
- Added `JOURNAL.md` (this file) — GitHub-commit-style activity log for all work done on the project.
- Added `INDEX.md` — project context snapshot (stack, key files, domain concepts, data locations) for fast session orientation.
- Convention set: every future action on this project (code changes, fixes, exploration, decisions) will be logged here with a pseudo-hash, timestamp, type, scope, subject, and body.

---

## b7e2d41 — 2026-09-03 00:00
**type:** explore
**scope:** project
**subject:** docs: capture project baseline and structure

- Inspected project root: Flask app (`app.py`), SQLite layer (`database.py`), Excel/CSV I/O (`excel_io.py`), Jalali calendar (`jalali.py`), reports (`reports.py`), plus `templates/`, `static/`, and `data/` (db, images, backups, exports).
- Read `README.md`: TikoTime is a fully local, offline Persian watch-shop inventory system with Jalali calendar, one-row-per-watch inventory model, sales/repairs/payments/order-tracking modules, backup system, and light/dark RTL UI.
- No code modified — baseline observation only. Findings recorded in `.memory/INDEX.md`.
