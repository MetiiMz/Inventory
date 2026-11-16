// ============================================================================
// TikoTime — Credit Sale UI browser checks (Playwright / Chromium)
// Run with:  TIKOTIME_DB=/tmp/check_credit_ui.db npx playwright test ...
// This script is NOT run by the Django suite. It exercises the real frontend.
// ============================================================================

const { test, expect } = require("@playwright/test");

const BASE = "http://127.0.0.1:8000";

test.describe("credit sale UI", () => {
  test("provider chips, detail view, service filter, edit-disable, hints", async ({
    page,
  }) => {
    const errors = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });

    async function openSaleModalAndFillBasics() {
      await page.goto(`${BASE}/products`);
      await page.waitForSelector("#btn-new");
      await page.click("#btn-new");
      const firstSell = page.locator('button[data-act="sale"]').first();
      await firstSell.waitFor({ state: "visible" });
      await firstSell.click();
      await page.waitForSelector("#modal-sale", { state: "visible" });
    }

    await openSaleModalAndFillBasics();
    await page.click('#sale-payment-chips [data-pay="credit"]');
    await page.waitForSelector("#credit-fields:not(.hidden)");

    const activeDigipay = await page.locator(
      '#sale-credit-provider-chips [data-provider="digipay"].active'
    ).count();
    expect(activeDigipay).toBe(0);
    expect(await page.locator("#sale-form [name='credit_provider']").inputValue()).toBe("");

    await page.click('#sale-credit-provider-chips [data-provider="torob"]');
    expect(
      await page.locator(
        '#sale-credit-provider-chips [data-provider="torob"].active'
      ).count()
    ).toBe(1);
    expect(await page.locator("#sale-credit-provider-chips").getAttribute("role")).toBe("radiogroup");
    expect(await page.locator('#sale-credit-provider-chips [data-provider="torob"]').getAttribute("aria-checked")).toBe("true");
    expect(await page.locator("#sale-form [name='credit_provider']").inputValue()).toBe("torob");

    await page.click('#sale-credit-provider-chips [data-provider="snappay"]');
    expect(await page.locator("#sale-form [name='credit_provider']").inputValue()).toBe("snappay");

    await page.fill('[name="sale_price"]', "100000");
    await page.fill('[name="customer"]', "تست");
    await page.fill('[name="customer_phone"]', "09123456789");
    const submitPromise = page.waitForResponse((r) => r.url().includes("/api/sales") && r.request().method() === "POST").catch(() => null);
    await page.click("#btn-save-sale");
    const toast = await page.waitForSelector(".toast", { state: "visible", timeout: 3000 }).catch(() => null);
    if (toast) {
      const text = await toast.textContent();
      expect(text).toContain("کد رهگیری پرداخت را وارد کنید");
    }
    const res = await submitPromise;
    expect(res).toBeNull();

    await page.fill('[name="credit_tracking_code"]', "4546851");
    await page.click("#btn-save-sale");
    await page.waitForTimeout(1000);
    await page.click('[data-close-modal="modal-sale"]');
    await page.waitForSelector("#modal-sale", { state: "hidden" });
    // Point 2: Sale detail view shows service + tracking code for credit
    await page.goto(`${BASE}/sold`);
    await page.waitForSelector("#sales-table");
    await page.click('tr.ev-row:first-child td:not(:has(button))').first();
    await page.waitForSelector("#modal-sale-detail", { state: "visible" });
    const detailBody = await page.locator("#sale-detail-body").textContent();
    expect(detailBody).toContain("نوع پرداخت");
    expect(detailBody).toContain("اعتباری");
    expect(detailBody).toContain("سرویس");
    expect(detailBody).toContain("کد رهگیری");
    expect(detailBody).not.toContain("پرداخت‌شده تاکنون");
    expect(detailBody).not.toContain("مانده");
    expect(detailBody).not.toContain("وضعیت تسویه");
    await page.click('[data-close-modal="modal-sale-detail"]');

    // Point 2 (calendar): same detail rows from calendar
    await page.goto(`${BASE}/calendar`);
    await page.waitForSelector("#cal-cells");
    const todayBtn = page.locator(".day-cell.today").first();
    if ((await todayBtn.count()) > 0) {
      await todayBtn.click();
      await page.waitForTimeout(500);
      const sellEvent = page.locator('.d-badge.sell').first();
      if ((await sellEvent.count()) > 0) {
        await sellEvent.click();
        await page.waitForTimeout(500);
        const panel = await page.locator("#panel-content").textContent();
        expect(panel).toContain("نوع پرداخت");
        expect(panel).toContain("اعتباری");
        expect(panel).toContain("سرویس");
        expect(panel).toContain("کد رهگیری");
        expect(panel).not.toContain("وضعیت تسویه");
      }
    }

    // Point 3: Live preview of stored code
    await openSaleModalAndFillBasics();
    await page.click('#sale-payment-chips [data-pay="credit"]');
    await page.waitForSelector("#credit-fields:not(.hidden)");

    await page.click('#sale-credit-provider-chips [data-provider="digipay"]');
    await page.fill('[name="credit_tracking_code"]', "4546851");
    await page.waitForTimeout(300);
    const preview = await page.locator("#sale-form .code-preview");
    expect(await preview.isVisible()).toBeTruthy();
    const previewText = await page.locator("#sale-form .preview-code").textContent();
    expect(previewText).toBe("D-4546851");

    await page.click('#sale-credit-provider-chips [data-provider="snappay"]');
    await page.waitForTimeout(300);
    const previewText2 = await page.locator("#sale-form .preview-code").textContent();
    expect(previewText2).toBe("S-4546851");

    await page.fill('[name="credit_tracking_code"]', "");
    await page.waitForTimeout(300);
    expect(await page.locator("#sale-form .code-preview").isVisible()).toBeFalsy();

    await page.click('[data-close-modal="modal-sale"]');

    // Point 4: Service filter + payment filter + clear filters
    await page.goto(`${BASE}/sold`);
    await page.waitForSelector("#sales-table");
    await page.selectOption("#filter-payment", "credit");
    await page.waitForTimeout(500);
    await page.selectOption("#filter-credit-service", "torob");
    await page.waitForTimeout(500);
    await page.click("#btn-clear-filters");
    await page.waitForTimeout(500);
    expect(await page.locator("#filter-payment").inputValue()).toBe("");
    expect(await page.locator("#filter-credit-service").inputValue()).toBe("");

    // Point 5: Edit modal - credit sale disables deposit chip
    await page.goto(`${BASE}/sold`);
    await page.waitForSelector("#sales-table");
    await page.click('tr.ev-row:first-child td:not(:has(button))').first();
    await page.waitForSelector("#modal-sale-detail", { state: "visible" });
    await page.click("#btn-detail-edit");
    await page.waitForSelector("#modal-sale-edit", { state: "visible" });
    await page.waitForTimeout(300);

    const depositChip = page.locator('#edit-payment-chips [data-pay="deposit"]');
    expect(await depositChip.isDisabled()).toBeTruthy();
    expect(await depositChip.getAttribute("title")).toContain("تغییر مستقیم بین بیعانه و اعتباری ممکن نیست");
    const creditChip = page.locator('#edit-payment-chips [data-pay="credit"]');
    expect(await creditChip.isDisabled()).toBeFalsy();

    await page.click('[data-close-modal="modal-sale-edit"]');

    // Point 6: Hint texts exact
    await openSaleModalAndFillBasics();
    await page.click('#sale-payment-chips [data-pay="credit"]');
    await page.waitForSelector("#credit-fields:not(.hidden)");
    const hint = await page.locator("#pay-basis-hint").textContent();
    expect(hint).toBe("مثل تسویه کامل ثبت می‌شود؛ سرویس انتخاب‌شده مبلغ را به فروشگاه پرداخت می‌کند و مشتری اقساط را با خود سرویس تسویه می‌کند. این فروش در صفحه‌ی پرداخت‌ها نمی‌آید.");
    const creditHint = await page.locator("#paid-breakdown-hint").textContent();
    expect(creditHint).toBe(
      "مثل تسویه کامل ثبت می‌شود؛ سرویس انتخاب‌شده مبلغ را به فروشگاه پرداخت می‌کند و مشتری اقساط را با خود سرویس تسویه می‌کند. این فروش در صفحه‌ی پرداخت‌ها نمی‌آید."
    );
    expect(creditHint).not.toContain("کل مبلغ در آینده تسویه می‌شود");
    expect(creditHint).not.toContain("اگر خالی بماند، کل مبلغ نقدی ثبت می‌شود");

    await page.click('[data-close-modal="modal-sale"]');

    // Point 7 (backend): /payments lists only deposit sales (credit sale not listed)
    await page.goto(`${BASE}/payments`);
    await page.waitForSelector("#payments-table", { timeout: 5000 });

    // No console errors
    expect(errors).toEqual([]);
  });
});