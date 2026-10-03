# Command Log — TikoTime

> Persistent log of every shell command executed on this project (user request, 2026-09-03).
> Newest first. Grouped by task. Paths abbreviated as `<root>` = `/media/MyShit/Works/Tick O Time/DB/Watch Inventory`.

## 2026-10-03 — Step 3: split services.py into the 11-module services/ package
```bash
# T029: clear stale dir + back up before deleting
rm -rf inventory/api/services/                 # stale __pycache__ only (0 tracked files)
cp inventory/api/services.py /tmp/service_before.py   # kept for the diff gate
# split: generator extracts each top-level fn/class/const VERBATIM (ast.get_source_segment),
#   computes per-module imports, writes 11 modules + re-exporting __init__.py (54 names + __all__)
python3 /tmp/split_services.py
# diff-based verification (user-required): byte-identity of every moved top-level node + no undefined names
python3 /tmp/verify_split.py                    # 64/64 byte-identical; no undefined names; VERDICT PASS
git rm inventory/api/services.py                # T036
export DJANGO_SETTINGS_MODULE=tikotime.settings
.venv/bin/python -c "import django; django.setup(); from inventory.api import services; print(services.__file__)"
.venv/bin/python -c "import django; django.setup(); from inventory.api.services import ApiError, product_queryset, _parse_iso_or_raise"
.venv/bin/python manage.py check                # no issues
find inventory/api/services -name '*.py' -exec wc -l {} + | sort -n | tail -1   # sales.py 277 (<=400)
git add -A && git --no-pager diff --cached --name-status   # D services.py + A 11 modules; zero caller changes
.venv/bin/python manage.py test 2>&1 | tail -4   # Found 153 test(s) + OK
git commit -m 'refactor(api): split services.py into the 11-module domain services/ package'   # 059c3a9
```

## 2026-10-03 — Step 2: drop gunicorn/whitenoise; static independent of DEBUG
```bash
# requirements.txt: -gunicorn -whitenoise   -> 3 lines (Django, Jinja2, openpyxl)
# settings.py: -WhiteNoiseMiddleware, -STORAGES, -WHITENOISE_MAX_AGE, docstring prod=runserver
# urls.py: + path("static/<path:path>", serve_static, {"insecure": True})  (staticfiles.views.serve, R3)
# rm -rf staticfiles ; .gitignore: -staticfiles/ ; wsgi/jinja/README/INDEX doc updates
.venv/bin/python manage.py check                                    # no issues
grep -rn 'gunicorn\|whitenoise\|collectstatic' --include=*.py --include=*.md --include=*.txt \
     tikotime inventory README.md .memory/INDEX.md                  # (no matches)
DJANGO_DEBUG=0 .venv/bin/python manage.py runserver 127.0.0.1:8114 &
#   curl /static/css/app.css -> 200 ; /static/js/app.js -> 200 ; /static/fonts/Vazirmatn-Regular.woff2 -> 200
#   curl /dashboard -> 200 ; /api/products -> 200
.venv/bin/python manage.py test 2>&1 | tail -3                      # Found 153 test(s) + OK
git add -A && git commit --amend --no-edit                            # 76c7a2b (folded first static-route attempt + R3 correction + .gitignore/README)
```

## 2026-10-03 — Step 1: drop the `/api/v1` layer + DRF
```bash
git rm inventory/api/views.py inventory/api/serializers.py inventory/api/fields.py \
       inventory/api/exceptions.py inventory/api/urls.py tests/test_api_v1.py
# doc-only cleanups: tikotime/{urls,settings}.py, requirements.txt,
#   inventory/api/{compat,services,__init__}.py, inventory/views/{__init__,pages}.py,
#   README.md, .memory/INDEX.md   (also removed compat fns: api_brands_add, _page_ctx)
.venv/bin/python manage.py check                                    # no issues
grep -rn 'rest_framework\|api/v1\|djangorestframework' --include=*.py --include=*.md --include=*.txt \
     inventory tikotime tests README.md requirements.txt
#   -> only hit = tests/test_legacy_api_baseline.py:7 (frozen docstring; zero code refs)
.venv/bin/python manage.py test 2>&1 | tail -4                      # Found 153 test(s) + OK (= 131 + N=22)
.venv/bin/python manage.py runserver 127.0.0.1:8111 &               # live gate
#   curl /api/v1/products -> 404 text/html (default Django 404, NOT JSON)
#   curl /api/products    -> 200 application/json ; 8/8 pages -> 200
git add -A && git commit -m 'refactor(api): drop the unused versioned /api/v1 layer and DRF'   # 2aeb840
```

## 2026-10-03 — Step 0: freeze the legacy `/api/*` contract (reference test module)
```bash
grep -c 'def test_' tests/test_legacy_api_baseline.py   # N = 22 (fix this number for all later gates)
.venv/bin/python manage.py test 2>&1 | tail -4         # Found 169 test(s) + OK   (= 147 baseline + N=22)
git add tests/test_legacy_api_baseline.py
git commit -m 'test(api): freeze the legacy /api/* contract before the restructure'   # 443bff6
git --no-pager show --stat HEAD      # exactly 1 file: tests/test_legacy_api_baseline.py (563 insertions)
# N is FIXED at 22 for every later gate: pre-step-1 base = 147 -> expect >=147+22; post-step-1 base = 131 -> expect >=131+22
```

## 2026-10-01 — Refactor preflight: baseline numbers + rescue net (16:47–16:49)
```bash
git --no-pager status --short                       # empty (clean tree)
.venv/bin/python manage.py check                    # no issues
.venv/bin/python manage.py test 2>&1 | tail -4      # Found 147 test(s) + OK
ls data/images | wc -l                              # 139   (artifacts say 135 -> stale, see NOTE)
ls data/backups | wc -l ; ls data/exports | wc -l   # 42 ; 54
sha256sum data/db.sqlite3                           # f753fc1cc299f31762d4c9a2b8751af27c0300dfb933abcda7a008b8cf69444f
rm -rf /tmp/tiko-preflight && mkdir -p /tmp/tiko-preflight && cp -a data /tmp/tiko-preflight/data
tar czf /tmp/tiko-preflight/code.tgz manage.py requirements.txt tikotime inventory tests static templates README.md .gitignore
find /tmp/tiko-preflight/data/images -maxdepth 1 -type f | wc -l   # 139 (matches repo)
sha256sum /tmp/tiko-preflight/data/db.sqlite3       # same hash as repo (verified)
# NOTE (found during preflight): the test suite writes 2 x 58-byte PNGs into the REAL
# data/images/ on every run — tests/test_services_misc.py:90,100 call
# services.save_upload() without override_settings(IMG_DIR=...). Orphans observed at
# 2026-09-17, 09-27, 09-28, 09-29 and 10-01 (58 bytes = that file's 1x1 PNG constant).
# Consequence: live image count is 139, so the step-5 gate must compare the image SET
# before vs after the move instead of a hardcoded 135.
```

## 2026-09-06 — Git initialized, initial commit (session IV)
```bash
git init -b main                                   # .git created (root-owned dir → dubious-ownership fix below)
git config --global --add safe.directory '/media/MyShit/Works/Tick O Time/DB/Watch Inventory'
git config user.name 'meti' ; git config user.email 'meti@local'   # local identity (none existed)
# .gitignore created: __pycache__ *.pyc .venv staticfiles data/ .codebase-memory
git add -A && git status --short | wc -l           # 71 staged, 0 from data/
git commit -m 'Initial commit: TikoTime watch-inventory app (Django port complete & verified)'
git log --oneline                                  # 776891f (root-commit), 71 files, 12658 insertions
# rule: one commit per completed task (user request)
```

---

## 2026-09-06 — Session IV started: 22-item multi-page feature request (context gathering)
```bash
# codebase-memory full re-index (end of session III): 963 nodes / 4,346 edges, 0 skipped,
#   parse_partial: templates/dashboard.html:108 (known cosmetic)
# reads (read_files): inventory/reports.py, templates/dashboard.html (tail truncated), inventory/utils.py, inventory/models.py
grep -rn 'moneyIn' static/js | head        # pending — shared thousands-sep helper
ls static/js/                              # pending — check for jalali lib / shared utils
# NO edits made yet in session IV — state saved to .memory/JOURNAL.md (b7d2f90) + .claude/PROGRESS.md
```

---

## 2026-09-06 — Quantity feature reverted to pre-quantity state (session III)
```bash
# reverts via editor: models.py (-quantity), utils.py (unit-price totals),
#   views/products.py (_product_values/_update back), views/sales.py (available-only flow, -F import),
#   excel_io.py (11-col format), dbhelpers.py (-_REQUIRED_COLS qty), templates/products.html, static/js/products.js
grep -rn 'quantity' inventory/ static/js/ templates/ | grep -v legacy_flask   # only migrations + import fallback left
.venv/bin/python manage.py migrate inventory          # 0003_remove_product_quantity... OK
.venv/bin/python manage.py makemigrations --check --dry-run   # No changes detected
.venv/bin/python manage.py check                      # no issues
python3 -c "import sqlite3;c=sqlite3.connect('data/db.sqlite3');print([r[1] for r in c.execute('PRAGMA table_info(products)')])"  # no quantity col
node --check static/js/products.js                    # JS_OK
```

---

## 2026-09-06 — Quantity field restored + serializer/edit bugs fixed (11:30–12:55)
```bash
# graph scout: product_dict / sale flow / legacy *_dict key diff (codebase-memory MCP)
sed -n '125,260p' inventory/utils.py ; sed -n '1,200p' inventory/views/products.py ; sed -n '1,300p' inventory/views/sales.py
grep -rn 'status_color\|is_warranty_fa\|total_value\|profit_per_unit\|paid_percent' static/js templates | grep -v legacy
# fixes via editor: models.py (+quantity), utils.py (serializer keys, TRACKING_STATUS_COLOR),
#   views/products.py (quantity, availability preserved on edit), views/sales.py (stock decrement/restore/guard),
#   excel_io.py (تعداد column), dbhelpers.py (_REQUIRED_COLS), templates/products.html, static/js/products.js,
#   .claude/launch.json, inventory/migrations/0002_product_quantity.py (created)
.venv/bin/python -m py_compile inventory/*.py inventory/views/*.py inventory/migrations/0002_product_quantity.py   # PY_OK
.venv/bin/python manage.py check                     # no issues
.venv/bin/python manage.py makemigrations --check --dry-run   # No changes detected
.venv/bin/python manage.py migrate inventory          # 0002_product_quantity... OK
node --check static/js/products.js                    # JS_OK
(.venv/bin/python manage.py runserver 127.0.0.1:8765 --noreload &)   # live smoke test
curl -s -X POST :8765/api/products ... quantity=3 ; 3x POST /api/sales ; 4th sale -> «این ساعت ناموجود است»
curl -X PUT :8765/api/products/<id> quantity=0 (unchanged) -> stays unavailable ; DELETE sale -> qty+1/موجود
pkill -f '[r]unserver 127.0.0.1:8765'                 # stop server (note: pkill -f self-match killed 2 earlier attempts)
.venv/bin/python -c "import sqlite3;..."              # db.sqlite3: 0 TEST rows, quantity column present
```

---

## 2026-09-05/06 — Django port finished, full verification, memory save (23:30–01:40)
```bash
ls -la '<root>' ; find '<root>' -type f | head -50 ; find '<root>' -type f | wc -l
# codebase-memory MCP: index_repository (full) -> 797 nodes / 3,549 edges, status ready
grep -rn 'qty' templates/ static/js/          # -> dashboard.html qty remnant found
sed -n '85,115p' templates/dashboard.html      # context read, then editor fix line ~100
(.venv/bin/python manage.py runserver 127.0.0.1:8000 &)   # started in background for spot checks
curl -s http://127.0.0.1:8000/products | grep -c 'no such element'   # 0 after fix
grep -n 'available\|موجود' templates/products.html
grep -rn 'is_available\|\.available' static/js/*.js   # -> products.js/calendar.js expect is_available
# /tmp/tikotime_fulltest.py written via editor (3 chunks) — full E2E suite, isolated TIKOTIME_DB
rm -f /tmp/tikotime_fulltest.db*
.venv/bin/python /tmp/tikotime_fulltest.py     # run1: 70/74 (test-script bugs); run2: 75/75 PASS
ls -la data/images/img_20260906_*              # identify 108-byte test PNGs
rm -f data/images/img_20260906_011126_19ac33a5.png data/images/img_20260906_011336_a2a01d3e.png
rm -f /tmp/tikotime_fulltest.db* /tmp/tikotime_import_test.xlsx
.venv/bin/python manage.py check               # "System check identified no issues"
pgrep -af 'manage.py runserver'                # 2 procs found
pkill -f 'manage.py runserver' ; pgrep -af runserver ; ss -tlnp | grep 8000   # port free
```

---

---

## 2026-09-03 — Django port scaffolding (18:00–19:44)
```bash
# inventory check after scaffolding
find inventory -type f | sort
wc -l inventory/*.py tikotime/*.py
# created (via editor, not shell): requirements.txt, manage.py,
#   tikotime/{__init__,settings,jinja,urls,wsgi}.py,
#   inventory/{models,utils,reports,jalali}.py + empty views/, migrations/, management/commands/
```

## 2026-09-03 — Flask bug fixes + migration (16:20–17:30)
```bash
# DB inspection (production): NULL-id row, date formats, table DDLs
cd '<root>' && .venv/bin/python - <<'EOF'  # several heredoc scripts:
#   SELECT ... FROM sales WHERE id IS NULL        -> found rowid 11, id NULL, date '1405/06/07'
#   SELECT sql FROM sqlite_master WHERE name IN ('products','sales','payments','repairs','tracking')
#     -> products/sales had "id INT" (no PK); payments.sale_id had no FK
#   date-format census: GROUP BY CASE WHEN sale_date LIKE '____-__-__' ...
cp data/watch_inventory.db data/backups/pre_migration_backup_20260903.db && ls -la data/backups/
# migration repair executed via init_db() -> verified: 4 products / 11 sales preserved,
#   NULL-id row -> id=12, '1405/06/07' -> '2026-08-29', integrity_check=ok
grep -n '@app.route' app.py ; grep -n 'is_settled' app.py      # -> sales list filters is_settled=1 (Sales-page bug)
grep -n 'todayJalaliStr' -A6 static/js/*.js                     # -> UI sends Jalali '1405/06/12' format
which node && node --version                                    # v24.19.0
.venv/bin/python -c "import flask; print(flask.__version__)"    # Flask 3.1.3
.venv/bin/python /tmp/test_calendar_sale_deletion.py | tail -25 # first run: 3 FAIL (test bugs) -> fixed test
cd '<root>' && .venv/bin/python tests/test_calendar_sale_deletion.py   # 37/37 PASS
# app boot smoke test (Flask test client): /calendar /payments /api/calendar -> 200
```

## 2026-09-03 — Calendar fix + exploration (16:00–16:40)
```bash
ls -la '<root>'
find '<root>' -maxdepth 2 -type d
ls -la '<root>/.memory'
wc -l .memory/JOURNAL.md .memory/INDEX.md
head -15 .memory/JOURNAL.md
grep -o 'src="[^"]*"\|href="[^"]*"' templates/base.html | sort -u
grep -o '{{[^}]*}}' templates/dashboard.html | head -15
grep -n 'url_for\|request\.\|session\|loop\.\|csrf' templates/*.html | head -30
grep -n 'tojson\|{% block\|{% extends' templates/*.html | head -20
grep -n "def " jalali.py
```

## 2026-09-03 — Django setup begins (16:54–16:55)
```bash
.venv/bin/pip install Django
mkdir -p legacy_flask config inventory ... && mv app.py database.py reports.py excel_io.py run.sh legacy_flask/ && cp jalali.py inventory/jalali.py
mv run.bat legacy_flask/ ; ls tests/
# NOTE: Django installed via plain `pip install Django` (unpinned). When resuming,
# verify installed version matches requirements.txt (Django==5.2.6) and re-pin if needed.
```

## 2026-09-03 — Memory system init (16:05)
```bash
mkdir -p '<root>/.memory'    # created via editor files, not shell
# files created: .memory/JOURNAL.md, .memory/INDEX.md
```
