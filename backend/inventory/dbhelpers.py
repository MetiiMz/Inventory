# -*- coding: utf-8 -*-
"""تنظیمات، برندها و پشتیبان‌گیری — پورت database.py قدیمی روی Django."""
import datetime
import os
import sqlite3

from django.conf import settings

from inventory.models import Setting

DATA_DIR = settings.DATA_DIR
IMG_DIR = settings.IMG_DIR
BACKUP_DIR = settings.BACKUP_DIR
DB_PATH = settings.DB_PATH


# ---------------------------------------------------------------- settings
def get_setting(key, default=""):
    row = Setting.objects.filter(key=key).values_list("value", flat=True).first()
    return row if row is not None else default


def set_setting(key, value):
    Setting.objects.update_or_create(key=key, defaults={"value": value})


# ---------------------------------------------------------------- brands
def get_brands():
    return list(
        Setting.objects.filter(key__startswith="brand:")
        .order_by("value")
        .values_list("value", flat=True)
    )


def add_brand(name):
    name = (name or "").strip()
    if not name:
        return False, "نام برند خالی است"
    if Setting.objects.filter(key="brand:" + name).exists():
        return False, "این برند قبلاً ثبت شده است"
    Setting.objects.create(key="brand:" + name, value=name)
    return True, ""


def delete_brand(name):
    Setting.objects.filter(key="brand:" + name).delete()
    return True, ""


# ---------------------------------------------------------------- backups
def _stamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_db(filename=None):
    """ایجاد نسخه‌ی پشتیبان امن (شامل فایل‌های WAL) از پایگاه‌داده."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    fname = filename or ("backup_" + _stamp() + ".db")
    if not fname.endswith(".db"):
        fname += ".db"
    target = os.path.join(BACKUP_DIR, os.path.basename(fname))
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(target)
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    return target


def list_backups():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    out = []
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if f.endswith(".db"):
            p = os.path.join(BACKUP_DIR, f)
            out.append({
                "name": f,
                "size": os.path.getsize(p),
                "modified": os.path.getmtime(p),
            })
    return out


def restore_db(filename):
    """بازگردانی نسخه‌ی پشتیبان. ابتدا از وضعیت فعلی یک بکاپ می‌گیرد."""
    safe = os.path.basename(filename or "")
    target = os.path.join(BACKUP_DIR, safe)
    if not os.path.isfile(target):
        return False, "فایل نسخه‌ی پشتیبان یافت نشد"
    backup_db("pre_restore_" + _stamp() + ".db")
    src = sqlite3.connect(target)
    dst = sqlite3.connect(DB_PATH)
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    _ensure_schema()
    return True, ""


def delete_backup(filename):
    safe = os.path.basename(filename or "")
    p = os.path.join(BACKUP_DIR, safe)
    if os.path.isfile(p):
        os.remove(p)
        return True, ""
    return False, "فایل یافت نشد"


# ---------------------------------------------------------------- clear database
_CLEAR_TABLES = ("payments", "sales", "products", "repairs", "tracking")


def count_records():
    """شمارش رکوردهای داده‌ای — پیش‌نمایش قبل از پاک‌سازی."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        out = {}
        for t in _CLEAR_TABLES:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                out[t] = cur.fetchone()[0]
            except sqlite3.Error:
                out[t] = 0
        return out
    finally:
        conn.close()


def clear_database():
    """پاک‌سازی کامل داده‌های دوره برای شروع سال جدید.

    اول به‌صورت خودکار از وضعیت فعلی پشتیبان گرفته می‌شود
    (pre_clear_...)، بعد ساعت‌ها، فروش‌ها، پرداخت‌ها، تعمیرات و
    پیگیری‌ها در یک تراکنش حذف می‌شوند؛ شمارنده‌ی id ها صفر می‌شود
    (شماره‌گذاری از ۱ شروع می‌شود) و فایل VACUUM می‌شود.
    تنظیمات فروشگاه، برندها و آیکون سایت دست‌نخورده می‌مانند.
    """
    backup_db("pre_clear_" + _stamp() + ".db")
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    try:
        cur = conn.cursor()
        counts = {}
        cur.execute("PRAGMA foreign_keys = OFF")
        cur.execute("BEGIN")
        for t in _CLEAR_TABLES:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                counts[t] = cur.fetchone()[0]
                cur.execute(f"DELETE FROM {t}")
            except sqlite3.Error:
                counts[t] = 0
        # سال تازه، شماره‌های تازه — id از ۱ شروع شود
        try:
            cur.execute(
                "DELETE FROM sqlite_sequence WHERE name IN (?, ?, ?, ?, ?)",
                _CLEAR_TABLES)
        except sqlite3.Error:
            pass  # sqlite_sequence هنوز وجود ندارد
        cur.execute("COMMIT")
        cur.execute("VACUUM")
    finally:
        conn.close()
    return counts


# --- schema fixup ---
# بکاپ‌های نسخه‌ی Flask ممکن است ساختار قدیمی داشته باشند (بدون PK واقعی).
# بعد از بازگردانی، ساختار را هم‌تراز Django می‌کنیم.
_REQUIRED_COLS = {
    # جدول: ((نام ستون، تعریف SQL برای ALTER TABLE), ...)
    "payments": (("sale_id", "INTEGER"), ("updated_at", "TEXT")),
}

_EXTRA_INDEXES = {
    "products": (
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_products_office_code"
        " ON products(office_code COLLATE NOCASE)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_products_website_code"
        " ON products(website_code COLLATE NOCASE)",
        "CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)",
        "CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand)",
    ),
    "sales": ("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date)",),
}


def _has_real_pk(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    for _cid, name, _typ, _notnull, _dflt, pk in cur.fetchall():
        if name == "id" and pk == 1:
            return True
    return False


def _rebuild_with_pk(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    info = cur.fetchall()
    names = [c[1] for c in info]
    has_id = "id" in names
    defs = []
    if not has_id:
        # جدول‌های قدیمی مثل settings با key به‌عنوان PRIMARY KEY ساخته شده‌اند
        defs.append('"id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT')
    for _cid, name, typ, notnull, dflt, pk in info:
        if name == "id":
            defs.append('"id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT')
            continue
        piece = f'"{name}" {typ or "TEXT"}'
        if notnull and dflt is not None:
            piece += f" NOT NULL DEFAULT {dflt}"
        defs.append(piece)
    collist = ", ".join(f'"{n}"' for n in names if n != "id")
    cur.execute(f'ALTER TABLE "{table}" RENAME TO "{table}__old"')
    cur.execute(f'CREATE TABLE "{table}" ({", ".join(defs)})')
    cur.execute(f'INSERT INTO "{table}" ({collist}) SELECT {collist} FROM "{table}__old"')
    cur.execute(f'DROP TABLE "{table}__old"')


def _ensure_schema():
    """بعد از restore، ساختار را با انتظارات Django هم‌تراز می‌کند."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys = OFF")
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
            "('products','sales','payments','repairs','tracking','settings')"
        )
        existing = {r[0] for r in cur.fetchall()}
        for table in existing:
            # ستون‌های لازم که در بکاپ‌های خیلی قدیمی نیست
            for col, typedef in _REQUIRED_COLS.get(table, ()):
                cur.execute(f"PRAGMA table_info({table})")
                cols = {c[1] for c in cur.fetchall()}
                if col not in cols:
                    cur.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" {typedef}')
            # PK واقعی
            if not _has_real_pk(cur, table):
                _rebuild_with_pk(cur, table)
            for ddl in _EXTRA_INDEXES.get(table, ()):
                cur.execute(ddl)
        # جدول مهاجرت‌های Django را هم بساز/تکمیل کن تا `migrate` بعدی تمیز باشد
        cur.execute(
            "CREATE TABLE IF NOT EXISTS django_migrations ("
            "id integer NOT NULL PRIMARY KEY AUTOINCREMENT, "
            "app varchar(255) NOT NULL, name varchar(255) NOT NULL, "
            "applied datetime NOT NULL)"
        )
        cur.execute(
            "SELECT 1 FROM django_migrations WHERE app='inventory' AND name='0001_initial'"
        )
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO django_migrations (app, name, applied) "
                "VALUES ('inventory', '0001_initial', datetime('now'))"
            )
        conn.commit()
    finally:
        conn.close()