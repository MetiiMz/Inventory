# -*- coding: utf-8 -*-
"""Tests for /api/ledger/* — the exact JSON envelopes the ledger page uses."""
import os
import tempfile
from unittest import mock

from django.test import TestCase

from inventory import dbhelpers


class LedgerSupplierCompatTests(TestCase):
    """POST /api/ledger/suppliers — wrapped create + validation envelopes."""

    def test_post_supplier_returns_ok_envelope(self):
        r = self.client.post("/api/ledger/suppliers", {"name": "امید ساعت"},
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertIn("id", body["supplier"])
        self.assertEqual(body["supplier"]["name"], "امید ساعت")
        self.assertNotIn("detail", body)

    def test_post_supplier_validation_envelopes(self):
        r = self.client.post("/api/ledger/suppliers", {"name": "  "},
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)
        body = r.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "نام تأمین‌کننده خالی است")
        self.assertNotIn("detail", body)

        self.client.post("/api/ledger/suppliers", {"name": "آبان"},
                         content_type="application/json")
        r = self.client.post("/api/ledger/suppliers", {"name": "آبان"},
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"],
                         "این تأمین‌کننده قبلاً ثبت شده است")
        self.assertNotIn("detail", r.json())


class LedgerInvoiceCreateCompatTests(TestCase):
    """POST /api/ledger/invoices — full detail object + validation envelopes."""

    def setUp(self):
        self.sid = self.client.post(
            "/api/ledger/suppliers", {"name": "آبان"},
            content_type="application/json").json()["supplier"]["id"]

    def test_post_invoice_returns_full_detail(self):
        r = self.client.post("/api/ledger/invoices", {
            "supplier_id": self.sid, "purchase_date": "1405/03/31",
            "lines": [
                {"watch_name": "روکسول", "reference": "RX-4250",
                 "quantity": 2, "unit_price": "3000000"},
                {"watch_name": "دنیلا", "unit_price": "3500000"},
            ]},
            content_type="application/json")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        inv = body["invoice"]
        self.assertEqual(len(inv["lines"]), 2)
        self.assertEqual(inv["total_quantity"], 3)
        self.assertEqual(inv["total_amount"], 9500000.0)
        self.assertEqual(inv["lines"][1]["quantity"], 1)  # blank ⇒ 1
        self.assertEqual(inv["lines"][1]["line_total"], 3500000.0)
        self.assertEqual(inv["images"], [])
        self.assertNotIn("detail", body)

    def test_post_invoice_photos_in_submitted_order(self):
        r = self.client.post("/api/ledger/invoices", {
            "supplier_id": self.sid, "purchase_date": "2026-06-21",
            "images": ["b.jpg", "a.jpg"],
            "lines": [{"watch_name": "A", "unit_price": "1"}]},
            content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["invoice"]["images"], ["b.jpg", "a.jpg"])

    def test_post_invoice_validation_envelopes(self):
        r = self.client.post("/api/ledger/invoices", {
            "supplier_id": 999999, "purchase_date": "1405/03/31"},
            content_type="application/json")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "تأمین‌کننده یافت نشد")

        r = self.client.post("/api/ledger/invoices", {
            "supplier_id": self.sid, "purchase_date": "xx"},
            content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "تاریخ معتبر نیست")

        r = self.client.post("/api/ledger/invoices", {
            "supplier_id": self.sid, "purchase_date": "1405/03/31",
            "lines": [{"unit_price": "1"}]},
            content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "نام ساعت را وارد کنید")

        r = self.client.post("/api/ledger/invoices", {
            "supplier_id": self.sid, "purchase_date": "1405/03/31",
            "images": ["", "x.jpg"]},
            content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "عکس معتبر نیست")


class LedgerReadCompatTests(TestCase):
    """GET list + detail — the read side the accordion renders from."""

    def setUp(self):
        self.s1 = self.client.post(
            "/api/ledger/suppliers", {"name": "ب"},
            content_type="application/json").json()["supplier"]["id"]
        self.s2 = self.client.post(
            "/api/ledger/suppliers", {"name": "ا"},
            content_type="application/json").json()["supplier"]["id"]

    def _invoice(self, sid, date, **kw):
        payload = {"supplier_id": sid, "purchase_date": date}
        payload.update(kw)
        r = self.client.post("/api/ledger/invoices", payload,
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        return r.json()["invoice"]

    def test_supplier_list_ordered_by_name_with_counts(self):
        self._invoice(self.s1, "2026-06-21",
                      lines=[{"watch_name": "A", "unit_price": "1"}])
        r = self.client.get("/api/ledger/suppliers")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        items = body["items"]
        self.assertEqual([i["name"] for i in items], ["ا", "ب"])
        counts = {i["id"]: i["invoice_count"] for i in items}
        self.assertEqual(counts[self.s2], 0)
        self.assertEqual(counts[self.s1], 1)

    def test_invoice_list_summary_shape_and_order(self):
        i1 = self._invoice(self.s1, "2026-06-20",
                           images=["p1.jpg", "p2.jpg"],
                           lines=[{"watch_name": "A", "unit_price": "10"}])
        i2 = self._invoice(self.s1, "2026-06-21",
                           lines=[{"watch_name": "B", "quantity": 2,
                                   "unit_price": "5"}])
        r = self.client.get(f"/api/ledger/invoices?supplier_id={self.s1}")
        self.assertEqual(r.status_code, 200)
        items = r.json()["items"]
        self.assertEqual([i["id"] for i in items], [i2["id"], i1["id"]])
        newest, oldest = items
        self.assertNotIn("lines", newest)          # summary, not detail
        self.assertEqual(oldest["images"], ["p1.jpg", "p2.jpg"])
        self.assertEqual(oldest["total_amount"], 10.0)
        self.assertEqual(newest["total_amount"], 10.0)
        self.assertEqual(newest["total_quantity"], 2)
        self.assertIn("total_amount_display", newest)
        self.assertIn("purchase_date_fa", newest)

    def test_invoice_list_unknown_supplier_404(self):
        r = self.client.get("/api/ledger/invoices?supplier_id=999999")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "یافت نشد")
        r = self.client.get("/api/ledger/invoices")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "یافت نشد")

    def test_invoice_detail_full_shape(self):
        inv = self._invoice(
            self.s1, "2026-06-21", images=["p1.jpg", "p2.jpg"],
            lines=[
                {"watch_name": "A", "reference": "R1",
                 "quantity": 2, "unit_price": "3000000"},
                {"watch_name": "B", "unit_price": "3500000"},
            ])
        r = self.client.get(f"/api/ledger/invoices/{inv['id']}")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertNotIn("detail", body)
        d = body["invoice"]
        self.assertEqual(d["id"], inv["id"])
        self.assertEqual(d["supplier_id"], self.s1)
        self.assertEqual(d["images"], ["p1.jpg", "p2.jpg"])
        self.assertEqual(len(d["lines"]), 2)
        self.assertEqual(d["total_quantity"], 3)
        self.assertEqual(d["total_amount"], 9500000.0)
        self.assertEqual(d["lines"][0]["line_total"], 6000000.0)
        self.assertIn("created_at", d)

    def test_invoice_detail_unknown_404(self):
        r = self.client.get("/api/ledger/invoices/999999")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "یافت نشد")

    def test_invoice_list_date_range_filters(self):
        for d in ("2026-06-20", "2026-06-25", "2026-07-05"):
            self._invoice(self.s1, d, lines=[{"watch_name": "A", "unit_price": "1"}])
        r = self.client.get(
            f"/api/ledger/invoices?supplier_id={self.s1}"
            "&date_from=2026-06-21&date_to=2026-07-01")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            [i["purchase_date"] for i in r.json()["items"]], ["2026-06-25"])

    def test_invoice_list_date_range_accepts_jalali(self):
        self._invoice(self.s1, "2026-06-20", lines=[{"watch_name": "A", "unit_price": "1"}])
        self._invoice(self.s1, "2026-06-21", lines=[{"watch_name": "B", "unit_price": "1"}])
        r = self.client.get(
            f"/api/ledger/invoices?supplier_id={self.s1}&date_from=1405/03/31")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            [i["purchase_date"] for i in r.json()["items"]], ["2026-06-21"])

    def test_invoice_list_date_range_without_dates_unfiltered(self):
        self._invoice(self.s1, "2026-06-20", lines=[{"watch_name": "A", "unit_price": "1"}])
        r = self.client.get(
            f"/api/ledger/invoices?supplier_id={self.s1}&date_from=&date_to=")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["items"]), 1)

    def test_invoice_list_invalid_filter_date_400(self):
        r = self.client.get(
            f"/api/ledger/invoices?supplier_id={self.s1}&date_from=xx")
        self.assertEqual(r.status_code, 400)
        body = r.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "تاریخ معتبر نیست")
        self.assertNotIn("detail", body)


class LedgerUpdateCompatTests(TestCase):
    """PUT /api/ledger/invoices/<id> — full-replace edit envelopes."""

    def setUp(self):
        self.sid = self.client.post(
            "/api/ledger/suppliers", {"name": "آبان"},
            content_type="application/json").json()["supplier"]["id"]
        inv = self.client.post("/api/ledger/invoices", {
            "supplier_id": self.sid, "purchase_date": "2026-06-21",
            "images": ["old1.jpg", "old2.jpg"],
            "lines": [{"watch_name": "A", "quantity": 2, "unit_price": "1000"}]},
            content_type="application/json").json()["invoice"]
        self.iid = inv["id"]

    def test_put_full_edit_returns_full_detail(self):
        r = self.client.put(f"/api/ledger/invoices/{self.iid}", {
            "purchase_date": "1405/03/31",
            "images": ["new.jpg"],
            "lines": [
                {"watch_name": "X", "quantity": "3", "unit_price": "5"},
                {"watch_name": "Y", "unit_price": "7"},
            ]},
            content_type="application/json")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        d = body["invoice"]
        self.assertEqual(d["purchase_date"], "2026-06-21")  # contract pair
        self.assertEqual(d["images"], ["new.jpg"])
        self.assertEqual(len(d["lines"]), 2)
        self.assertEqual(d["total_quantity"], 4)
        self.assertEqual(d["total_amount"], 22.0)
        self.assertNotIn("detail", body)

    def test_put_omitted_keys_kept(self):
        r = self.client.put(f"/api/ledger/invoices/{self.iid}", {
            "lines": [{"watch_name": "B", "unit_price": "9"}]},
            content_type="application/json")
        self.assertEqual(r.status_code, 200)
        d = r.json()["invoice"]
        self.assertEqual(d["purchase_date"], "2026-06-21")
        self.assertEqual(d["images"], ["old1.jpg", "old2.jpg"])
        self.assertEqual(d["total_amount"], 9.0)

    def test_put_unknown_invoice_404(self):
        r = self.client.put("/api/ledger/invoices/999999", {"lines": []},
                           content_type="application/json")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "یافت نشد")

    def test_put_invalid_date_envelope(self):
        r = self.client.put(f"/api/ledger/invoices/{self.iid}",
                            {"purchase_date": "xx"},
                            content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "تاریخ معتبر نیست")


class LedgerRenameCompatTests(TestCase):
    """PUT /api/ledger/suppliers/<id> — rename envelopes."""

    def test_put_rename_returns_supplier_with_real_count(self):
        sid = self.client.post(
            "/api/ledger/suppliers", {"name": "قدیم"},
            content_type="application/json").json()["supplier"]["id"]
        self.client.post("/api/ledger/invoices", {
            "supplier_id": sid, "purchase_date": "2026-06-21",
            "lines": [{"watch_name": "A", "unit_price": "1"}]},
            content_type="application/json")
        r = self.client.put(f"/api/ledger/suppliers/{sid}", {"name": "جدید"},
                            content_type="application/json")
        self.assertEqual(r.status_code, 200)
        s = r.json()["supplier"]
        self.assertEqual(s["name"], "جدید")
        self.assertEqual(s["invoice_count"], 1)

    def test_put_rename_validation_envelopes(self):
        sid = self.client.post(
            "/api/ledger/suppliers", {"name": "واحد"},
            content_type="application/json").json()["supplier"]["id"]
        self.client.post("/api/ledger/suppliers", {"name": "دو"},
                         content_type="application/json")
        r = self.client.put(f"/api/ledger/suppliers/{sid}", {"name": "  "},
                            content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "نام تأمین‌کننده خالی است")
        r = self.client.put(f"/api/ledger/suppliers/{sid}", {"name": "دو"},
                            content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"],
                         "این تأمین‌کننده قبلاً ثبت شده است")
        r = self.client.put("/api/ledger/suppliers/999999", {"name": "x"},
                            content_type="application/json")
        self.assertEqual(r.status_code, 404)


class LedgerDeleteCompatTests(TestCase):
    """DELETE /api/ledger/* — destructive envelopes + cascade results."""

    def setUp(self):
        self.sid = self.client.post(
            "/api/ledger/suppliers", {"name": "آبان"},
            content_type="application/json").json()["supplier"]["id"]
        self.iid = self.client.post("/api/ledger/invoices", {
            "supplier_id": self.sid, "purchase_date": "2026-06-21",
            "lines": [{"watch_name": "A", "unit_price": "1"}]},
            content_type="application/json").json()["invoice"]["id"]

    def test_delete_invoice_then_supplier_count_back_to_zero(self):
        r = self.client.delete(f"/api/ledger/invoices/{self.iid}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True})
        r = self.client.get(f"/api/ledger/invoices/{self.iid}")
        self.assertEqual(r.status_code, 404)
        counts = {i["id"]: i["invoice_count"] for i in
                  self.client.get("/api/ledger/suppliers").json()["items"]}
        self.assertEqual(counts[self.sid], 0)

    def test_delete_supplier_full_cascade(self):
        r = self.client.delete(f"/api/ledger/suppliers/{self.sid}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True})
        self.assertEqual(
            self.client.get("/api/ledger/suppliers").json()["items"], [])
        r = self.client.get(f"/api/ledger/invoices/{self.iid}")
        self.assertEqual(r.status_code, 404)

    def test_delete_unknown_404(self):
        r = self.client.delete("/api/ledger/invoices/999999")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "یافت نشد")
        r = self.client.delete("/api/ledger/suppliers/999999")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "یافت نشد")


class LedgerClearDatabaseTests(TestCase):
    """US4: Clear Database wipes ledger records + photos, keeps the site
    logo, and still takes its pre-clear backup (SC-005).

    Same raw-sqlite-file pattern as test_dbhelpers_reports: the clear
    helpers use the module-level ``DB_PATH``/``BACKUP_DIR``/``IMG_DIR``
    constants, so they are patched to throwaway locations.
    """

    def _make_raw_db(self, db_path):
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
            CREATE TABLE ledger_suppliers (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                name varchar(200) NOT NULL,
                created_at datetime NOT NULL, updated_at datetime NOT NULL);
            CREATE TABLE ledger_invoices (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                supplier_id integer NOT NULL,
                purchase_date varchar(10) NOT NULL,
                created_at datetime NOT NULL);
            CREATE TABLE ledger_lines (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                invoice_id integer NOT NULL,
                watch_name varchar(200) NOT NULL, reference varchar(100) NOT NULL,
                quantity integer NOT NULL, unit_price REAL NOT NULL);
            CREATE TABLE ledger_invoice_images (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                invoice_id integer NOT NULL,
                filename varchar(255) NOT NULL, "order" integer NOT NULL,
                created_at datetime NOT NULL);
        """)
        conn.execute(
            "INSERT INTO products (name, reference, office_code, website_code,"
            " brand, purchase_price, sale_price, available, supplier,"
            " purchase_date, purchase_type, notes, image, created_at, updated_at)"
            " VALUES ('w', '', 'OF-1', 'WS-1', '', 1, 2, 1, '', '', 'person',"
            " '', '', '2026-01-01', '2026-01-01')")
        conn.execute(
            "INSERT INTO ledger_suppliers (name, created_at, updated_at)"
            " VALUES ('آبان', '2026-01-01', '2026-01-01')")
        conn.execute(
            "INSERT INTO ledger_invoices (supplier_id, purchase_date, created_at)"
            " VALUES (1, '2026-06-21', '2026-01-01')")
        conn.execute(
            "INSERT INTO ledger_lines (invoice_id, watch_name, reference,"
            " quantity, unit_price) VALUES (1, 'رولکس', 'RX', 2, 5000)")
        conn.execute(
            'INSERT INTO ledger_invoice_images (invoice_id, filename, "order",'
            " created_at) VALUES (1, 'page_a.jpg', 0, '2026-01-01')")
        conn.execute(
            'INSERT INTO ledger_invoice_images (invoice_id, filename, "order",'
            " created_at) VALUES (1, 'page_b.jpg', 1, '2026-01-01')")
        conn.commit()
        conn.close()

    def test_clear_wipes_ledger_keeps_logo_and_backs_up(self):
        dbhelpers.set_setting("site_icon", "logo.png")
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/clear_test.db"
            self._make_raw_db(db_path)
            bdir = f"{tmp}/backups"
            idir = f"{tmp}/images"
            os.makedirs(bdir)
            os.makedirs(idir)
            for f in ("logo.png", "page_a.jpg", "page_b.jpg"):
                with open(os.path.join(idir, f), "wb") as fh:
                    fh.write(b"x")
            with mock.patch.object(dbhelpers, "BACKUP_DIR", bdir), \
                 mock.patch.object(dbhelpers, "IMG_DIR", idir), \
                 mock.patch.object(dbhelpers, "DB_PATH", db_path):
                counts = dbhelpers.clear_database()
            # the four ledger tables are counted AND wiped
            self.assertEqual(counts["ledger_suppliers"], 1)
            self.assertEqual(counts["ledger_invoices"], 1)
            self.assertEqual(counts["ledger_lines"], 1)
            self.assertEqual(counts["ledger_invoice_images"], 2)
            # products are still wiped exactly as before
            self.assertEqual(counts["products"], 1)
            import sqlite3
            conn = sqlite3.connect(db_path)
            for t in ("products", "ledger_suppliers", "ledger_invoices",
                      "ledger_lines", "ledger_invoice_images"):
                self.assertEqual(
                    conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0], 0,
                    f"rows left in {t}")
            # id restarts at 1 ⇒ the sqlite_sequence IN(…) covers the new
            # tables (placeholder count built from the tuple length)
            conn.execute(
                "INSERT INTO ledger_suppliers (name, created_at, updated_at)"
                " VALUES ('جدید', '2026-01-02', '2026-01-02')")
            self.assertEqual(conn.execute("SELECT id FROM ledger_suppliers").fetchone()[0], 1)
            conn.close()
            # invoice photos gone, site logo kept
            self.assertFalse(os.path.exists(f"{idir}/page_a.jpg"))
            self.assertFalse(os.path.exists(f"{idir}/page_b.jpg"))
            self.assertTrue(os.path.exists(f"{idir}/logo.png"))
            # the automatic pre-clear backup was taken first
            backups = [f for f in os.listdir(bdir) if f.startswith("pre_clear_")]
            self.assertEqual(len(backups), 1)