// ============================================================================
// TikoTime — Deposit (بیعانه) Sale UI browser checks (Playwright / Chromium)
// Run with:  TIKOTIME_DB=/tmp/check_deposit_ui.db npx playwright test ...
// This script is NOT run by the Django suite. It exercises the real frontend.
// ============================================================================

const { test, expect } = require("@playwright/test");

const BASE = "http://127.0.0.1:8000";

// Mirror of frontend faMoney (faNum(n.toLocaleString("en-US")).replace(/,/g,"٬"))
// so assertions match the Persian-digit strings the UI renders.
const faMoney = (v) =>
  String(Math.round(Number(v) || 0))
    .replace(/\B(?=(\d{3})+(?!\d))/g, ",")
    .replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[+d])
    .replace(/,/g, "٬");

test.describe("deposit sale UI", () => {
  /* ---------------- helpers ---------------- */

  async function addProductViaUI(page, suf) {
    await page.goto(`${BASE}/products`);
    await page.waitForSelector("#btn-new");
    await page.click("#btn-new");
    await page.waitForSelector("#modal-product", { state: "visible" });
    const name = `تست بیعانه ${suf}`;
    const ws = `WS-D${suf}`;
    const of = `OF-D${suf}`;
    await page.fill('[name="name"]', name);
    await page.fill('[name="website_code"]', ws);
    await page.fill('[name="office_code"]', of);
    await page.click("#btn-save-product");
    await page.waitForSelector("#modal-product", { state: "hidden" });
    // wait until the new product row is rendered
    await page.waitForSelector(`#products-body tr:has-text("${of}")`);
    return { name, ws, of };
  }

  async function openSaleModalForProduct(page, of) {
    await page
      .locator(`#products-body tr:has-text("${of}") button[data-act="sale"]`)
      .first()
      .click();
    await page.waitForSelector("#modal-sale", { state: "visible" });
  }

  async function fillSaleBasics(page, { price, customer, phone }) {
    await page.fill('[name="sale_price"]', price);
    await page.fill('[name="customer"]', customer);
    await page.fill('[name="customer_phone"]', phone);
  }

  async function expectSuccessToast(page, contains) {
    const toast = page.locator(".toast").filter({ hasText: contains });
    await expect(toast).toBeVisible({ timeout: 8000 });
  }

  /* ---------------- tests ---------------- */

  test("create deposit sale from products page → sales list + payments receipt", async ({
    page,
  }) => {
    const errors = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });

    const suf = Date.now();
    const { of, name } = await addProductViaUI(page, suf);
    const customer = `خریدار بیعانه ${suf}`;
    const phone = "09123456789";
    const price = "2000000";
    const deposit = "500000";

    await openSaleModalForProduct(page, of);
    await page.click('#sale-payment-chips [data-pay="deposit"]');
    await page.waitForSelector("#deposit-fields:not(.hidden)");
    await fillSaleBasics(page, { price, customer, phone });
    await page.fill('[name="paid_amount"]', deposit);

    const submitted = page
      .waitForResponse(
        (r) => r.url().includes("/api/sales") && r.request().method() === "POST"
      )
      .catch(() => null);
    await page.click("#btn-save-sale");
    const res = await submitted;
    expect(res).not.toBeNull();
    await expectSuccessToast(page, "فروش بیعانه ثبت شد");

    // appears in the sales list as بیعانه with the paid amount
    await page.goto(`${BASE}/sold`);
    await page.waitForSelector("#sales-table");
    const row = page.locator(`tr.ev-row:has-text("${customer}")`).first();
    await expect(row).toContainText("بیعانه");

    // a receipt appears on the payments page with the right remaining amount
    await page.goto(`${BASE}/payments`);
    await page.waitForSelector("#payments-grid");
    const card = page
      .locator(`#payments-grid .entity-card:has-text("${name}")`)
      .first();
    await expect(card).toContainText("مانده دارد");
    await expect(card).toContainText(faMoney(price)); // کل مبلغ
    await expect(card).toContainText(faMoney(deposit)); // پرداخت‌شده
    await expect(card).toContainText(faMoney(+price - +deposit)); // مانده

    expect(errors).toEqual([]);
  });
  test("deposit sale with empty / zero deposit → Persian error, no request sent", async ({
    page,
  }) => {
    const errors = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    let saleRequested = false;
    page.on("request", (r) => {
      if (r.url().includes("/api/sales") && r.method() === "POST")
        saleRequested = true;
    });

    const suf = Date.now();
    const { of } = await addProductViaUI(page, suf);
    const customer = `خریدار بیعانه خالی ${suf}`;

    await openSaleModalForProduct(page, of);
    await page.click('#sale-payment-chips [data-pay="deposit"]');
    await page.waitForSelector("#deposit-fields:not(.hidden)");
    await page.fill('[name="sale_price"]', "2000000");
    await page.fill('[name="customer"]', customer);
    await page.fill('[name="customer_phone"]', "09123456789");
    // leave paid_amount empty (= 0)

    await page.click("#btn-save-sale");
    const errToast = page.locator(".toast").filter({
      hasText: "برای فروش بیعانه، دست‌کم مبلغ بیعانه را وارد کنید",
    });
    await expect(errToast.first()).toBeVisible({ timeout: 5000 });
    expect(saleRequested).toBe(false); // no request sent

    // zero explicitly entered
    await page.fill('[name="paid_amount"]', "0");
    await page.click("#btn-save-sale");
    await expect(errToast.first()).toBeVisible({ timeout: 5000 });
    expect(saleRequested).toBe(false);

    expect(errors).toEqual([]);
  });

  test("cash sale still works through UI", async ({ page }) => {
    const errors = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });

    const suf = Date.now();
    const { of } = await addProductViaUI(page, suf);
    const customer = `خریدار نقدی ${suf}`;

    await openSaleModalForProduct(page, of);
    await page.fill('[name="sale_price"]', "1500000");
    await page.fill('[name="customer"]', customer);
    await page.fill('[name="customer_phone"]', "09123456789");
    await page.click("#btn-save-sale");
    await expectSuccessToast(page, "فروش ثبت شد");

    await page.goto(`${BASE}/sold`);
    await page.waitForSelector("#sales-table");
    await expect(
      page.locator(`tr.ev-row:has-text("${customer}")`).first()
    ).toContainText("تسویه کامل");

    expect(errors).toEqual([]);
  });

  test("credit sale still works through UI (provider + code saved)", async ({
    page,
  }) => {
    const errors = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });

    const suf = Date.now();
    const { of } = await addProductViaUI(page, suf);
    const customer = `خریدار اعتباری ${suf}`;

    await openSaleModalForProduct(page, of);
    await page.click('#sale-payment-chips [data-pay="credit"]');
    await page.waitForSelector("#credit-fields:not(.hidden)");
    await page.click('#sale-credit-provider-chips [data-provider="torob"]');
    // unique per run so re-runs do not collide on an already-used tracking code
    await page.fill('[name="credit_tracking_code"]', String(suf).slice(-6));
    await page.fill('[name="sale_price"]', "1500000");
    await page.fill('[name="customer"]', customer);
    await page.fill('[name="customer_phone"]', "09123456789");
    await page.click("#btn-save-sale");
    await expectSuccessToast(page, "فروش ثبت شد");

    await page.goto(`${BASE}/sold`);
    await page.waitForSelector("#sales-table");
    await expect(
      page.locator(`tr.ev-row:has-text("${customer}")`).first()
    ).toContainText("اعتباری");

    expect(errors).toEqual([]);
  });

  test("edit a deposit sale → payments page receipt remaining amount updates", async ({
    page,
  }) => {
    const errors = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });

    const suf = Date.now();
    const { of, name } = await addProductViaUI(page, suf);
    const customer = `خریدار ویرایش بیعانه ${suf}`;
    const price = "2000000";
    const deposit1 = "500000";
    const deposit2 = "700000";

    await openSaleModalForProduct(page, of);
    await page.click('#sale-payment-chips [data-pay="deposit"]');
    await page.waitForSelector("#deposit-fields:not(.hidden)");
    await page.fill('[name="sale_price"]', price);
    await page.fill('[name="customer"]', customer);
    await page.fill('[name="customer_phone"]', "09123456789");
    await page.fill('[name="paid_amount"]', deposit1);
    await page.click("#btn-save-sale");
    await expectSuccessToast(page, "فروش بیعانه ثبت شد");

    // open the sale for edit from the sales list
    await page.goto(`${BASE}/sold`);
    await page.waitForSelector("#sales-table");
    const row = page.locator(`tr.ev-row:has-text("${customer}")`).first();
    await expect(row).toContainText("بیعانه");
    await row.locator("td:nth-child(3)").click();
    await page.waitForSelector("#modal-sale-detail", { state: "visible" });
    await page.click("#btn-detail-edit");
    await page.waitForSelector("#modal-sale-edit", { state: "visible" });

    await page.fill('[name="paid_amount"]', deposit2);
    await page.click("#btn-save-edit");
    await expect(
      page.locator(".toast").filter({ hasText: "تغییرات فروش ذخیره شد" })
    ).toBeVisible({ timeout: 5000 });

    // receipt on the payments page now shows the updated remaining amount
    await page.goto(`${BASE}/payments`);
    await page.waitForSelector("#payments-grid");
    const card = page
      .locator(`#payments-grid .entity-card:has-text("${name}")`)
      .first();
    await expect(card).toContainText(faMoney(price));
    await expect(card).toContainText(faMoney(deposit2));
    await expect(card).toContainText(faMoney(+price - +deposit2));

    expect(errors).toEqual([]);
  });
});

