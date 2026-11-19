// ============================================================================
// TikoTime — Sale detail modal (مودال جزئیات فروش) browser checks
// Redesigned layout: header (image + name) + card 1 «اطلاعات ساعت» +
// card 2 «اطلاعات فروش» with a fixed tile order per payment type.
//
// Run with:
//   TIKOTIME_DB=/tmp/check_sale_detail.db ../.venv/bin/python manage.py runserver
//   npx playwright test sale-detail-check.js
// Temp DB only — this script never touches db/db.sqlite3. It reads one
// existing image file name from db/images (read-only) so the header thumb
// renders a real picture.
// ============================================================================

const fs = require("fs");
const path = require("path");
const { test, expect } = require("@playwright/test");

const BASE = "http://127.0.0.1:8000";
const SHOTS = __dirname;

/* یک تصویر موجود در db/images برای تصویر سرصفحه (فقط خواندن نام فایل) */
const IMG_DIR = path.resolve(__dirname, "../../db/images");
// فقط تصویرهای واقعی (بزرگ‌تر از ۲۰KB) — بعضی فایل‌های تست ۱×۱ پیکسلی‌اند
const PRODUCT_IMAGE = fs.existsSync(IMG_DIR)
  ? fs
      .readdirSync(IMG_DIR)
      .filter((f) => /\.(png|jpe?g|webp|gif)$/i.test(f) && !f.startsWith("icon_"))
      .filter((f) => fs.statSync(path.join(IMG_DIR, f)).size > 20000)
      .sort()[0] || ""
  : "";

/* ترتیب اجباری کاشی‌ها */
const CARD1_LABELS = [
  "برند",
  "کد رفرانس",
  "کد دفتر فروشگاه",
  "کد انبار سایت",
  "قیمت خرید",
  "تاریخ خرید",
  "تأمین‌کننده",
];
const CARD2_BASE = [
  "خریدار",
  "شماره تماس خریدار",
  "قیمت فروش",
  "سود این فروش",
  "کد فاکتور",
  "تاریخ فروش",
  "نوع فروش",
  "نوع پرداخت",
];
const CARD2_LABELS = {
  cash: [...CARD2_BASE],
  credit: [...CARD2_BASE, "سرویس", "کد رهگیری"],
  deposit: [...CARD2_BASE, "پرداخت‌شده تاکنون", "مانده", "وضعیت تسویه"],
};

const RUN = Date.now();

/* فروش‌های ساخته‌شده در beforeAll */
const seeded = {};

async function createProduct(request, payload) {
  const res = await request.post(`${BASE}/api/products`, { data: payload });
  if (!res.ok()) throw new Error(`product create failed: ${await res.text()}`);
  return (await res.json()).product;
}

async function createSale(request, payload) {
  const res = await request.post(`${BASE}/api/sales`, { data: payload });
  if (!res.ok()) throw new Error(`sale create failed: ${await res.text()}`);
  return (await res.json()).sale;
}

test.describe("sale detail modal", () => {
  test.beforeAll(async ({ request }) => {
    // یک ساعت کامل (تصویر/برند/رفرنس/کدها/تأمین‌کننده/تاریخ خرید) برای هر سه نوع
    const full = (tag) =>
      createProduct(request, {
        name: `ساعت تست ${tag} ${RUN}`,
        reference: `REF-${tag}-${RUN}`,
        office_code: `OF-${tag}-${RUN}`,
        website_code: `WS-${tag}-${RUN}`,
        brand: "رولکس",
        supplier: "تأمین‌کننده تست",
        purchase_price: "1000000",
        purchase_date: "2026-09-10",
        image: PRODUCT_IMAGE,
      });

    const pCash = await full("نقدی");
    const pCredit = await full("اعتباری");
    const pDeposit = await full("بیعانه");
    const pEmpty = await createProduct(request, {
      name: `ساعت بدون مشخصات ${RUN}`,
      office_code: `OF-EMPTY-${RUN}`,
      website_code: `WS-EMPTY-${RUN}`,
    });

    // تاریخ خرید باید شمسی برگردد؛ اگر نباشد تست باید بلند fail شود
    expect(pCash.purchase_date_fa).toBe("۱۴۰۵/۰۶/۱۹");

    seeded.image = PRODUCT_IMAGE;

    seeded.cash = await createSale(request, {
      product_id: pCash.id,
      sale_price: "1500000",
      payment_type: "cash",
      customer: `خریدار نقدی ${RUN}`,
      customer_phone: "09123456789",
      sale_date: "2026-09-12",
      notes: "یادداشت تست نقدی",
    });
    seeded.credit = await createSale(request, {
      product_id: pCredit.id,
      sale_price: "1800000",
      payment_type: "credit",
      credit_provider: "torob",
      credit_tracking_code: `${RUN}`.slice(-7),
      customer: `خریدار اعتباری ${RUN}`,
      customer_phone: "09121112233",
      sale_date: "2026-09-12",
    });
    seeded.deposit = await createSale(request, {
      product_id: pDeposit.id,
      sale_price: "2000000",
      deposit_amount: "500000",
      payment_type: "deposit",
      customer: `خریدار بیعانه ${RUN}`,
      customer_phone: "09124445566",
      sale_date: "2026-09-12",
    });
    seeded.empty = await createSale(request, {
      product_id: pEmpty.id,
      sale_price: "900000",
      payment_type: "cash",
      customer: `خریدار بدون مشخصات ${RUN}`,
      customer_phone: "09127778899",
      sale_date: "2026-09-12",
    });
  });

  /* ---------------- helpers ---------------- */

  async function setTheme(page, theme) {
    // ارتفاع کافی تا کل مودال (هر دو کارت) در اسکرین‌شات دیده شود؛
    // در تست موبایل دست نمی‌زنیم (viewport خودش ۳۹۰ است)
    const vp = page.viewportSize();
    if (vp && vp.width > 600) {
      // ۱۲۶۰px: بلندترین مودال (بیعانه) هم کامل جا می‌شود
      await page.setViewportSize({ width: 1280, height: 1260 });
    }
    await page.goto(`${BASE}/sold`);
    await page.evaluate((t) => localStorage.setItem("satchour-theme", t), theme);
    await page.goto(`${BASE}/sold`);
    await page.waitForSelector("#sales-table");
    await page.waitForFunction(
      (t) => document.documentElement.getAttribute("data-theme") === t,
      theme
    );
  }

  async function openDetail(page, sale) {
    const row = page
      .locator(`tr.ev-row:has-text("${sale.customer}")`)
      .first();
    await expect(row).toBeVisible({ timeout: 10000 });
    await row.locator("td").nth(2).click();
    await page.waitForSelector("#modal-sale-detail.open", { state: "visible" });
    await page.waitForSelector("#sale-detail-body .sd-card");
    // صبر تا پایان انیمیشن باز شدن (scale 0.98) تا اندازه‌ها/اسکرین‌شات دقیق باشند
    await page.waitForTimeout(400);
  }

  async function closeDetail(page) {
    await page.click(
      '#modal-sale-detail .modal-foot [data-close-modal="modal-sale-detail"]'
    );
    await page.waitForSelector("#modal-sale-detail", { state: "hidden" });
  }

  const labels = (page, card) =>
    page.$$eval(`#sale-detail-body .sd-card:nth-of-type(${card}) .sd-k`, (els) =>
      els.map((e) => e.textContent.trim())
    );

  const tileValue = (page, label) =>
    page
      .locator("#sale-detail-body .sd-tile", { has: page.locator(".sd-k", { hasText: label }) })
      .first()
      .locator(".sd-v")
      .innerText();

  async function expectHeader(page, sale) {
    const head = page.locator("#sale-detail-body .sd-header");
    await expect(head).toBeVisible();
    await expect(head.locator(".sd-name")).toHaveText(sale.product_name);
    // کلاس‌های کد از سرصفحه برداشته شده‌اند
    expect(await head.locator(".code-pill").count()).toBe(0);
    if (PRODUCT_IMAGE) {
      const img = head.locator("img.sd-thumb");
      await expect(img).toBeVisible();
      const natural = await img.evaluate((el) => el.naturalWidth);
      expect(natural).toBeGreaterThan(50); // تصویر واقعی، نه فایل ۱×۱
      // اندازه‌ی CSS (مستقل از انیمیشن باز شدن که مقیاس ۰٫۹۸ دارد)
      const size = await img.evaluate((el) => {
        const cs = getComputedStyle(el);
        return [cs.width, cs.height];
      });
      expect(size).toEqual(["96px", "96px"]);
    } else {
      await expect(head.locator("span.sd-thumb svg")).toBeVisible();
    }
  }

  async function expectNoOverflow(page) {
    const overflow = await page.evaluate(() => {
      const body = document.querySelector("#sale-detail-body");
      return {
        page: document.documentElement.scrollWidth - window.innerWidth,
        body: body.scrollWidth - body.clientWidth,
      };
    });
    expect(overflow.page).toBeLessThanOrEqual(1);
    expect(overflow.body).toBeLessThanOrEqual(1);
  }

  async function shot(page, name) {
    await page.screenshot({
      path: path.join(SHOTS, `sale-detail-${name}.png`),
      fullPage: false,
    });
  }

  /* ---------------- تسویه کامل ---------------- */

  test("cash sale detail: header, card order, tiles, screenshots", async ({ page }) => {
    const errors = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

    await setTheme(page, "light");
    await openDetail(page, seeded.cash);

    await expectHeader(page, seeded.cash);
    expect(await labels(page, 1)).toEqual(CARD1_LABELS);
    // یادداشت آخرین کاشی کارت ۲ و تمام‌عرض است
    expect(await labels(page, 2)).toEqual([...CARD2_LABELS.cash, "یادداشت"]);

    expect(await tileValue(page, "برند")).toBe("رولکس");
    expect(await tileValue(page, "کد رفرانس")).toBe(`REF-نقدی-${RUN}`);
    expect(await tileValue(page, "کد دفتر فروشگاه")).toBe(`OF-نقدی-${RUN}`);
    expect(await tileValue(page, "کد انبار سایت")).toBe(`WS-نقدی-${RUN}`);
    expect(await tileValue(page, "قیمت خرید")).toBe("۱٬۰۰۰٬۰۰۰ تومان");
    expect(await tileValue(page, "تاریخ خرید")).toBe("۱۴۰۵/۰۶/۱۹");
    expect(await tileValue(page, "تأمین‌کننده")).toBe("تأمین‌کننده تست");
    expect(await tileValue(page, "قیمت فروش")).toBe("۱٬۵۰۰٬۰۰۰ تومان");
    expect(await tileValue(page, "سود این فروش")).toBe("۵۰۰٬۰۰۰ تومان");
    expect(await tileValue(page, "نوع فروش")).toBe("حضوری");
    expect(await tileValue(page, "نوع پرداخت")).toBe("تسویه کامل");

    // بج رنگی نوع پرداخت و رنگ سبز سود
    await expect(
      page.locator("#sale-detail-body .sd-tile .badge.green.plain")
    ).toHaveCount(1);
    await expect(page.locator("#sale-detail-body .sd-v.sd-profit")).toHaveCount(1);

    // یادداشت تمام‌عرض (span-2) در پایان کارت ۲
    const note = page.locator("#sale-detail-body .sd-tile.span-2:has(.sd-v.sd-notes)");
    await expect(note).toHaveCount(1);
    await expect(note).toContainText("یادداشت تست نقدی");

    await expectNoOverflow(page);
    await shot(page, "cash-light");

    await setTheme(page, "dark");
    await openDetail(page, seeded.cash);
    expect(await labels(page, 1)).toEqual(CARD1_LABELS);
    await shot(page, "cash-dark");
    await closeDetail(page);

    expect(errors).toEqual([]);
  });

  /* ---------------- اعتباری ---------------- */

  test("credit sale detail: سرویس + کد رهگیری with prefix", async ({ page }) => {
    const errors = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

    await setTheme(page, "light");
    await openDetail(page, seeded.credit);

    await expectHeader(page, seeded.credit);
    expect(await labels(page, 1)).toEqual(CARD1_LABELS);
    expect(await labels(page, 2)).toEqual(CARD2_LABELS.credit);

    await expect(page.locator("#sale-detail-body .sd-tile .badge.blue.plain")).toHaveCount(1);
    expect(await tileValue(page, "سرویس")).toBe("ترب‌پی");

    const tracking = page.locator('#sale-detail-body .code-pill[dir="ltr"]');
    await expect(tracking).toHaveCount(1);
    await expect(tracking).toHaveText(`T-${String(RUN).slice(-7)}`);

    // هیچ کاشی یادداشتی برای این فروش نیست
    await expect(page.locator("#sale-detail-body .sd-v.sd-notes")).toHaveCount(0);

    await expectNoOverflow(page);
    await shot(page, "credit-light");

    await setTheme(page, "dark");
    await openDetail(page, seeded.credit);
    await expect(
      page.locator('#sale-detail-body .code-pill[dir="ltr"]')
    ).toHaveText(`T-${String(RUN).slice(-7)}`);
    await shot(page, "credit-dark");
    await closeDetail(page);

    expect(errors).toEqual([]);
  });

  /* ---------------- بیعانه ---------------- */

  test("deposit sale detail: paid / remaining / settlement tiles", async ({ page }) => {
    const errors = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

    await setTheme(page, "light");
    await openDetail(page, seeded.deposit);

    await expectHeader(page, seeded.deposit);
    expect(await labels(page, 1)).toEqual(CARD1_LABELS);
    expect(await labels(page, 2)).toEqual(CARD2_LABELS.deposit);

    // دو بج کهربایی: «نوع پرداخت = بیعانه» و «وضعیت تسویه = در انتظار تسویه»
    await expect(page.locator("#sale-detail-body .sd-tile .badge.amber.plain")).toHaveCount(2);
    expect(await tileValue(page, "پرداخت‌شده تاکنون")).toBe("۵۰۰٬۰۰۰ تومان");
    expect(await tileValue(page, "مانده")).toBe("۱٬۵۰۰٬۰۰۰ تومان");
    expect(await tileValue(page, "وضعیت تسویه")).toBe("در انتظار تسویه");

    await expectNoOverflow(page);
    await shot(page, "deposit-light");

    await setTheme(page, "dark");
    await openDetail(page, seeded.deposit);
    expect(await tileValue(page, "مانده")).toBe("۱٬۵۰۰٬۰۰۰ تومان");
    await shot(page, "deposit-dark");
    await closeDetail(page);

    expect(errors).toEqual([]);
  });

  /* ---------------- ساعت بدون مشخصات ---------------- */

  test("empty product: card-1 values show «—» and keep the grid order", async ({ page }) => {
    await setTheme(page, "light");
    await openDetail(page, seeded.empty);

    expect(await labels(page, 1)).toEqual(CARD1_LABELS);
    const values = await page.$$eval(
      "#sale-detail-body .sd-card:nth-of-type(1) .sd-v",
      (els) => els.map((e) => e.textContent.trim())
    );
    // کد دفتر و کد انبار در این برنامه اجباری‌اند (API بدون آن‌ها محصول نمی‌سازد)
    expect(values[0]).toBe("—"); // برند
    expect(values[1]).toBe("—"); // رفرنس
    expect(values[3]).toBe(`WS-EMPTY-${RUN}`); // کد انبار سایت
    expect(values[5]).toBe("—"); // تاریخ خرید
    expect(values[6]).toBe("—"); // تأمین‌کننده
    // کارت ۲ همچنان کامل است (خریدار/تلفن فروش وجود دارند)
    expect(await labels(page, 2)).toEqual(CARD2_LABELS.cash);
    expect(await tileValue(page, "خریدار")).toBe(`خریدار بدون مشخصات ${RUN}`);

    await expectNoOverflow(page);
    await closeDetail(page);
  });

  /* ---------------- موبایل ۳۹۰px ---------------- */

  test.describe("mobile 390px", () => {
    test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

    test("all three detail modals at 390px", async ({ page }) => {
      for (const kind of ["cash", "credit", "deposit"]) {
        await setTheme(page, "light");
        await openDetail(page, seeded[kind]);
        // یک‌ستونه در موبایل
        const cols = await page.$eval(
          "#sale-detail-body .sd-grid",
          (el) => getComputedStyle(el).gridTemplateColumns.split(" ").length
        );
        expect(cols).toBe(1);
        await expectNoOverflow(page);
        await shot(page, `${kind}-mobile`);
        await closeDetail(page);
      }
    });
  });
});
