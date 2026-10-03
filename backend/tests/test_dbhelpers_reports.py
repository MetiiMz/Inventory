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

    def test_clear_removes_orphaned_images_keeps_site_icon(self):
        """Data wipe removes orphaned images but keeps the site logo."""
        dbhelpers.set_setting("site_icon", "logo.png")  # set via the ORM test DB
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/clear_test.db"
            self._make_raw_db(db_path)
            img_dir = f"{tmp}/images"
            os.makedirs(img_dir)
            for name in ("orphan_a.jpg", "orphan_b.png", "stale.gif",
                        "logo.png"):
                with open(os.path.join(img_dir, name), "w") as f:
                    f.write("x")
            with tempfile.TemporaryDirectory() as bdir, \
                 mock.patch.object(dbhelpers, "BACKUP_DIR", bdir), \
                 mock.patch.object(dbhelpers, "DB_PATH", db_path), \
                 mock.patch.object(dbhelpers, "IMG_DIR", img_dir):
                counts = dbhelpers.clear_database()
            # Orphans are gone; only the site logo survives
            self.assertEqual(counts["images_removed"], 3)
            self.assertEqual(os.listdir(img_dir), ["logo.png"])

    def test_clear_removes_all_images_when_no_site_icon(self):
        """With no site icon set, every image file is removed."""
        Setting.objects.filter(key="site_icon").delete()  # ensure unset
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/clear_test.db"
            self._make_raw_db(db_path)
            img_dir = f"{tmp}/images"
            os.makedirs(img_dir)
            for name in ("orphan_a.jpg", "orphan_b.png"):
                with open(os.path.join(img_dir, name), "w") as f:
                    f.write("x")
            with tempfile.TemporaryDirectory() as bdir, \
                 mock.patch.object(dbhelpers, "BACKUP_DIR", bdir), \
                 mock.patch.object(dbhelpers, "DB_PATH", db_path), \
                 mock.patch.object(dbhelpers, "IMG_DIR", img_dir):
                counts = dbhelpers.clear_database()
            self.assertEqual(counts["images_removed"], 2)
            self.assertEqual(os.listdir(img_dir), [])


class ReportTests(TestCase):
    """Dashboard aggregates."""

    def test_dashboard_stats_shape(self):
        make_product(purchase_price=1000, available=True)
        make_product(office_code="OF-S", website_code="WS-S",
                     purchase_price=500, available=False)
        stats = reports.get_dashboard_stats()
        for key in ("total_purchase_value",
                    "available_count", "product_count",
                    "sold_count", "sold_revenue", "sold_profit",
                    "open_repairs", "open_tracking",
                    "unpaid_count", "unavailable_count"):
            self.assertIn(key, stats)
        # Spec-002: the product-projection boxes are gone
        self.assertNotIn("total_sale_value", stats)
        self.assertNotIn("total_profit_value", stats)
        self.assertEqual(stats["product_count"], 2)
        self.assertEqual(stats["available_count"], 1)
        self.assertEqual(stats["total_purchase_value"], 1500)

    def test_dashboard_sales_boxes_are_current_jalali_year(self):
        # one sale this Jalali year, one in an earlier Jalali year
        make_product(office_code="OF-DY", website_code="WS-DY")
        make_product(office_code="OF-DO", website_code="WS-DO")
        Sale.objects.create(
            product=Product.objects.get(office_code="OF-DY"),
            sale_price=1000, purchase_price=400, profit=600,
            sale_date=today_iso(), customer="x", customer_phone="09123456789",
            paid_cash=1000, payment_type="cash", is_settled=True)
        Sale.objects.create(
            product=Product.objects.get(office_code="OF-DO"),
            sale_price=5000, purchase_price=1000, profit=4000,
            sale_date="2025-06-15", customer="y", customer_phone="09123456788",
            paid_cash=5000, payment_type="cash", is_settled=True)
        stats = reports.get_dashboard_stats()
        self.assertEqual(stats["sold_count"], 1)
        self.assertEqual(stats["sold_revenue"], 1000)
        self.assertEqual(stats["sold_profit"], 600)

    def test_brand_breakdown_stock_and_sales_combined(self):
        p_in = make_product(brand="Rolex", purchase_price=1000, available=True)
        p_sold_r = make_product(brand="Rolex", office_code="OF-BR",
                                website_code="WS-BR",
                                purchase_price=700, available=False)
        p_sold_o = make_product(brand="Omega", office_code="OF-BO",
                                website_code="WS-BO",
                                purchase_price=900, available=False)
        Sale.objects.create(
            product=p_sold_r, sale_price=1500, purchase_price=700, profit=800,
            sale_date=today_iso(), customer="x", customer_phone="09123456789",
            paid_cash=1500, payment_type="cash", is_settled=True)
        Sale.objects.create(
            product=p_sold_o, sale_price=2000, purchase_price=900, profit=1100,
            sale_date=today_iso(), customer="y", customer_phone="09123456788",
            paid_cash=2000, payment_type="cash", is_settled=True)
        rows = reports.get_brand_breakdown()
        by_brand = {r["brand"]: r for r in rows}
        self.assertEqual(set(by_brand), {"Rolex", "Omega"})
        self.assertEqual(
            set(rows[0]),
            {"brand", "in_stock_count", "sold_count", "in_stock_value",
             "sold_purchase_value", "sold_value", "sold_profit"})
        # in-stock Rolex watch feeds the stock columns
        self.assertEqual(by_brand["Rolex"]["in_stock_count"], 1)
        self.assertEqual(by_brand["Rolex"]["in_stock_value"], 1000)
        # sold columns come from that brand's Sale rows only
        self.assertEqual(by_brand["Rolex"]["sold_count"], 1)
        self.assertEqual(by_brand["Rolex"]["sold_purchase_value"], 700)
        self.assertEqual(by_brand["Rolex"]["sold_value"], 1500)
        self.assertEqual(by_brand["Rolex"]["sold_profit"], 800)
        # a brand with sales but no remaining stock still appears,
        # with zero stock and its real sold numbers
        self.assertEqual(by_brand["Omega"]["in_stock_count"], 0)
        self.assertEqual(by_brand["Omega"]["in_stock_value"], 0)
        self.assertEqual(by_brand["Omega"]["sold_count"], 1)
        self.assertEqual(by_brand["Omega"]["sold_purchase_value"], 900)
        self.assertEqual(by_brand["Omega"]["sold_value"], 2000)
        self.assertEqual(by_brand["Omega"]["sold_profit"], 1100)
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
        # (Spec-002, corrected) a brand with stock but no sales: stock
        # columns are real, ALL four sold-* columns are None together
        # (rendered blank, not zero).
        make_product(brand="Omega", purchase_price=2500, available=True)
        make_product(brand="Omega", office_code="OF-BS",
                     website_code="WS-BS",
                     purchase_price=500, available=False)  # unavailable, no sale
        rows = reports.get_brand_breakdown()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["brand"], "Omega")
        self.assertEqual(row["in_stock_count"], 1)
        self.assertEqual(row["in_stock_value"], 2500)
        self.assertIsNone(row["sold_count"])
        self.assertIsNone(row["sold_purchase_value"])
        self.assertIsNone(row["sold_value"])
        self.assertIsNone(row["sold_profit"])
