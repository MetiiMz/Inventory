# -*- coding: utf-8 -*-
"""Tests for dbhelpers (settings/brands/backups/clear) and reports.

The backup/clear helpers use module-level ``DB_PATH``/``BACKUP_DIR``
constants (set at import from settings), so these tests patch the module
attributes directly instead of ``override_settings`` — and they point
them at a temp *file* DB, since the Django test database is in-memory
and invisible to the raw sqlite3 connections those helpers use.
"""
import os
import tempfile
from unittest import mock

from django.test import TestCase

from inventory import dbhelpers, reports
from inventory.models import Payment, Product, Sale, Setting
from tests.helpers import make_product, today_iso


class SettingTests(TestCase):
    """get_setting / set_setting."""

    def test_default_when_missing(self):
        self.assertEqual(dbhelpers.get_setting("nope", "d"), "d")

    def test_set_then_get(self):
        dbhelpers.set_setting("store_name", "تیک")
        self.assertEqual(dbhelpers.get_setting("store_name", ""), "تیک")
        dbhelpers.set_setting("store_name", "تیک۲")  # update path
        self.assertEqual(dbhelpers.get_setting("store_name", ""), "تیک۲")


class BrandTests(TestCase):
    """Brands live in the Setting table under 'brand:' keys."""

    def test_add_list_delete(self):
        good, err = dbhelpers.add_brand("رولکس")
        self.assertTrue(good, err)
        good, err = dbhelpers.add_brand("رولکس")
        self.assertFalse(good)
        self.assertIn("قبلاً", err)
        good, err = dbhelpers.add_brand("   ")
        self.assertFalse(good)
        self.assertIn("خالی", err)
        dbhelpers.add_brand("امگا")
        self.assertEqual(dbhelpers.get_brands(), ["امگا", "رولکس"])  # sorted by value
        self.assertTrue(dbhelpers.delete_brand("رولکس"))
        self.assertEqual(dbhelpers.get_brands(), ["امگا"])


class BackupTests(TestCase):
    """backup/restore/delete helpers run against a temp dir + temp file DB."""

    def test_backup_list_restore_delete(self):
        with tempfile.TemporaryDirectory() as backup_dir:
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as db_file:
                db_path = db_file.name
            with mock.patch.object(dbhelpers, "BACKUP_DIR", backup_dir), \
                 mock.patch.object(dbhelpers, "DB_PATH", db_path):
                target = dbhelpers.backup_db()
                self.assertTrue(os.path.isfile(target))
                names = dbhelpers.list_backups()
                self.assertEqual(len(names), 1)
                self.assertEqual(names[0]["name"], os.path.basename(target))
                good, err = dbhelpers.restore_db(os.path.basename(target))
                self.assertTrue(good, err)
                # restore created a safety copy (pre_restore_*.db) of current state
                good, err = dbhelpers.delete_backup(os.path.basename(target))
                self.assertTrue(good)
                names = dbhelpers.list_backups()
                self.assertTrue(
                    all(n["name"].startswith("pre_restore_") for n in names),
                    names)
                good, err = dbhelpers.restore_db("ghost.db")
                self.assertFalse(good)
            os.unlink(db_path)


class ClearDatabaseTests(TestCase):
    """Yearly-reset logic — always exercised on a throwaway sqlite file.

    ``clear_database()``/``count_records()`` use the module-level
    ``DB_PATH`` constant via raw sqlite3, so the tests mock it to a temp
    file and NEVER let it point at the real database.
    """

    def _make_raw_db(self, db_path):
        """Create a minimal products+settings schema with one row each."""
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE products (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                name varchar(200) NOT NULL, reference varchar(200) NOT NULL,
                office_code varchar(100) NOT NULL, website_code varchar(100) NOT NULL,
                brand varchar(100) NOT NULL, purchase_price REAL NOT NULL,
                sale_price REAL NOT NULL, available BOOL NOT NULL,
                supplier varchar(200) NOT NULL, purchase_date varchar(10) NOT NULL,
                purchase_type varchar(20) NOT NULL, notes TEXT NOT NULL,
                image varchar(255) NOT NULL, created_at datetime NOT NULL,
                updated_at datetime NOT NULL);
            CREATE TABLE settings (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                key varchar(100) NOT NULL UNIQUE, value TEXT NOT NULL);
        """)
        conn.execute(
            "INSERT INTO products (name, reference, office_code, website_code,"
            " brand, purchase_price, sale_price, available, supplier,"
            " purchase_date, purchase_type, notes, image, created_at, updated_at)"
            " VALUES ('w', '', 'OF-1', 'WS-1', '', 1, 2, 1, '', '', 'person',"
            " '', '', '2026-01-01', '2026-01-01')")
        conn.execute("INSERT INTO settings (key, value) VALUES ('store_name', 'تیک')")
        conn.commit()
        conn.close()

    def test_clear_deletes_data_keeps_settings_restarts_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/clear_test.db"
            self._make_raw_db(db_path)
            with tempfile.TemporaryDirectory() as bdir, \
                 mock.patch.object(dbhelpers, "BACKUP_DIR", bdir), \
                 mock.patch.object(dbhelpers, "DB_PATH", db_path):
                self.assertEqual(dbhelpers.count_records()["products"], 1)
                counts = dbhelpers.clear_database()
            self.assertEqual(counts["products"], 1)

            import sqlite3
            conn = sqlite3.connect(db_path)
            n = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            conn.execute(
                "INSERT INTO products (name, reference, office_code, website_code,"
                " brand, purchase_price, sale_price, available, supplier,"
                " purchase_date, purchase_type, notes, image, created_at, updated_at)"
                " VALUES ('w2', '', 'OF-2', 'WS-2', '', 1, 2, 1, '', '', 'person',"
                " '', '', '2026-01-02', '2026-01-02')")
            new_id = conn.execute(
                "SELECT id FROM products WHERE name='w2'").fetchone()[0]
            kept = conn.execute(
                "SELECT value FROM settings WHERE key='store_name'").fetchone()[0]
            conn.close()
            self.assertEqual(n, 0)       # data gone
            self.assertEqual(new_id, 1)  # id restarted at 1
            self.assertEqual(kept, "تیک")  # settings preserved


class ReportTests(TestCase):
    """Dashboard aggregates."""

    def test_dashboard_stats_shape(self):
        make_product(purchase_price=1000, sale_price=1500, available=True)
        make_product(office_code="OF-S", website_code="WS-S",
                     purchase_price=500, sale_price=800, available=False)
        stats = reports.get_dashboard_stats()
        for key in ("total_purchase_value", "total_sale_value",
                    "total_profit_value", "available_count", "product_count",
                    "sold_count", "open_repairs", "open_tracking",
                    "unpaid_count", "unavailable_count"):
            self.assertIn(key, stats)
        self.assertEqual(stats["product_count"], 2)
        self.assertEqual(stats["available_count"], 1)

    def test_monthly_activity_twelve_months(self):
        months = reports.get_monthly_activity(1404)
        self.assertEqual(len(months), 12)
        self.assertEqual(months[0]["jy"], 1404)
        self.assertEqual(months[0]["jm"], 1)
        # 1404 is entirely in the past → nothing is marked future
        self.assertFalse(months[0]["future"])
        # a future year is all zeros + future flags
        months = reports.get_monthly_activity(1500)
        self.assertTrue(months[0]["future"])
        self.assertEqual(months[0]["revenue"], 0)

    def test_brand_breakdown_in_stock_only(self):
        make_product(brand="Rolex", purchase_price=1000, sale_price=1500,
                     available=True)
        make_product(brand="Omega", office_code="OF-B2", website_code="WS-B2",
                     purchase_price=700, sale_price=900, available=False)
        rows = reports.get_brand_breakdown()
        self.assertEqual([r["brand"] for r in rows], ["Rolex"])
        self.assertEqual(rows[0]["count"], 1)
        self.assertEqual(rows[0]["sale_value"], 1500)
        self.assertEqual(rows[0]["profit"], 500)
