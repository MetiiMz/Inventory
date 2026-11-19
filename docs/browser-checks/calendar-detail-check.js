// ============================================================================
// TikoTime — Calendar event-detail modal (مودال جزئیات رویداد تقویم) checks
// The calendar modal now uses the same card layout as the sold page detail:
// header (image + name) + «tile» cards.  Four event kinds are covered:
// sell (جزئیات فروش), buy (جزئیات خرید), rep_in / rep_out (ساعت تعمیری).
//
// Run with:
//   TIKOTIME_DB=/tmp/check_calendar_detail.db .venv/bin/python backend/manage.py runserver
//   npx playwright test calendar-detail-check.js
// Temp DB only — this script never touches db/db.sqlite3. It reads one
// existing image file name from db/images (read-only) so the header thumb
// renders a real picture.
// ============================================================================

const fs = require("fs");
const path = require("path");
const { test, expect } = require("@playwright/test");

const BASE = process.env.TIKOTIME_BASE || "http://127.0.0.1:8000";
const SHOTS = __dirname;

/* یک تصویر موجود در db/images برای تصویر سرصفحه (فقط خواندن نام فایل) */
const IMG_DIR = path.resolve(__dirname, "../../db/images");
const PRODUCT_IMAGE = fs.existsSync(IMG_DIR)
  ? fs
      .readdirSync(IMG_DIR)
      .filter((f) => /\.(png|jpe?g|webp|gif)$/i.test(f) && !f.startsWith("icon_"))
      .filter((f) => fs.statSync(path.join(IMG_DIR, f)).size > 20000)
      .sort()[0] || ""
  : "";

/* ترتیب اجباری کاشی‌ها — همان قرارداد صفحه‌ی فروش‌ها */
const CARD1_LABELS = [
  "برند",
  "کد رفرانس",
  "کد دفتر فروشگاه",
  "کد انبار سایت",
  "قیمت خرید",
  "تاریخ خرید",
  "تأمین‌کننده",
];
const SALE_CARD2_BASE = [
  "خریدار",
  "شماره تماس خریدار",
  "قیمت فروش",
  "سود این فروش",
  "کد فاکتور",
  "تاریخ فروش",
  "نوع فروش",
  "نوع پرداخت",
];
const SALE_CARD2 = {
  cash: [...SALE_CARD2_BASE, "یادداشت"],
  credit: [...SALE_CARD2_BASE, "سرویس", "کد رهگیری"],
  deposit: [...SALE_CARD2_BASE, "پرداخت‌شده تاکنون", "مانده", "وضعیت تسویه"],
};
const BUY_CARD2_LABELS = ["وضعیت", "یادداشت"];
const REPAIR_CARD1_LABELS = ["کد ساعت", "ایراد"];
const REPAIR_CARD2_LABELS = [
  "مشتری",
  "شماره تماس مشتری",
  "تاریخ دریافت",
  "تاریخ بازگشت",
  "گارانتی",
  "وضعیت",
  "هزینه تعمیر",
  "یادداشت",
];

const RUN = Date.now();
const seeded = {};

async function post(request, url, data) {
  const res = await request.post(`${BASE}${url}`, { data });
  if (!res.ok()) throw new Error(`${url} failed: ${await res.text()}`);
  return res.json();
}

function isoShift(iso, days) {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

test.describe("calendar event detail modal", () => {
  test.beforeAll(async ({ request }) => {
    // روزِ امروز از خود سرور (ماه جاری تقویم) — نه ساعت سیستم تست
    const month = await (await request.get(`${BASE}/api/calendar`)).json();
    const today = month.cells.find((c) => c && c.is_today);
    expect(today, "امروز باید در ماه جاری تقویم باشد").toBeTruthy();
    seeded.day = today.iso;
    const before = isoShift(today.iso, -3); // تاریخ خریدِ ساعت‌های فروخته‌شده

    const product = (tag, extra = {}) =>
      post(request, "/api/products", {
        name: `ساعت تقویم ${tag} ${RUN}`,
        reference: `REF-${tag}-${RUN}`,
        office_code: `OF-${tag}-${RUN}`,
        website_code: `WS-${tag}-${RUN}`,
        brand: "سیکو",
        supplier: "تأمین‌کننده تست",
        purchase_price: "1000000",
        purchase_date: before,
        image: PRODUCT_IMAGE,
        ...extra,
      }).then((r) => r.product);

    const sale = (pid, extra) =>
      post(request, "/api/sales", {
        product_id: pid,
        sale_price: "1500000",
        customer: `خریدار ${RUN}`,
        customer_phone: "09123456789",
        sale_date: today.iso,
        ...extra,
      }).then((r) => r.sale);

    /* سه فروش روی همان روز — نقدی، بیعانه، اعتباری */
    seeded.cash = await sale(await product("نقدی").then((p) => p.id), {
      payment_type: "cash",
      customer: `خریدار نقدی ${RUN}`,
      notes: "یادداشت فروش نقدی",
    });
    seeded.deposit = await sale(await product("بیعانه").then((p) => p.id), {
      payment_type: "deposit",
      sale_price: "2000000",
      deposit_amount: "500000",
      customer: `خریدار بیعانه ${RUN}`,
      customer_phone: "09121112233",
    });
    seeded.credit = await sale(await product("اعتباری").then((p) => p.id), {
      payment_type: "credit",
      sale_price: "1800000",
      credit_provider: "torob",
      credit_tracking_code: `${RUN}`.slice(-7),
      customer: `خریدار اعتباری ${RUN}`,
      customer_phone: "09124445566",
    });

    /* خرید همان روز — یکی کامل، یکی بدون مشخصات (برای «—») */
    seeded.buy = await product("خرید", {
      name: `ساعت خرید تقویم ${RUN}`,
      purchase_date: today.iso,
      notes: "یادداشت خرید تقویم",
    });
    seeded.buyEmpty = await product("خرید خالی", {
      name: `ساعت خرید بدون مشخصات ${RUN}`,
      purchase_date: today.iso,
      reference: "",
      brand: "",
      supplier: "",
      image: "",
      notes: "",
    });

    /* تعمیر دریافتی امروز (بدون تاریخ بازگشت، بدون هزینه/یادداشت) */
    seeded.repIn = (await post(request, "/api/repairs", {
      watch_name: `ساعت تعمیر دریافتی ${RUN}`,
      watch_code: `RP-IN-${RUN}`,
      issue: "شیشه خط افتاده\nبند شل شده",
      delivery_date: today.iso,
      return_date: "",
      customer_name: `مشتری تعمیر ${RUN}`,
      customer_phone: "09127778899",
      is_warranty: 0,
      status: "received",
      repair_price: "0",
      image: PRODUCT_IMAGE,
      notes: "",
    })).repair;

    /* تعمیر بازگشتی امروز (تاریخ دریافت سه روز قبل) */
    seeded.repOut = (await post(request, "/api/repairs", {
      watch_name: `ساعت تعمیر بازگشتی ${RUN}`,
      watch_code: `RP-OUT-${RUN}`,
      issue: "تعویض باتری",
      delivery_date: before,
      return_date: today.iso,
      customer_name: `مشتری بازگشت ${RUN}`,
      customer_phone: "09125556677",
      is_warranty: 1,
      status: "delivered",
      repair_price: "250000",
      image: PRODUCT_IMAGE,
      notes: "یادداشت تعمیر بازگشتی",
    })).repair;
  });

  /* ---------------- helpers ---------------- */

  async function setTheme(page, theme) {
    const vp = page.viewportSize();
    if (vp && vp.width > 600) {
      // بلندترین مودال (بیعانه) کامل در اسکرین‌شات جا شود
      await page.setViewportSize({ width: 1280, height: 1260 });
    }
    await page.goto(`${BASE}/calendar`);
    await page.evaluate((t) => localStorage.setItem("satchour-theme", t), theme);
    await page.goto(`${BASE}/calendar`);
    await page.waitForSelector("#cal-cells .day-cell.today");
    await page.waitForFunction(
      (t) => document.documentElement.getAttribute("data-theme") === t,
      theme
    );
  }

  /* انتخاب روزِ امروز در تقویم و باز کردن یک رویداد از پنل روز */
  async function openDay(page) {
    await page.click("#cal-cells .day-cell.today");
    await page.waitForSelector("#panel-content .ev-click");
    await page.waitForTimeout(150);
  }

  async function openEvent(page, text, shotName, opts = {}) {
    const item = page
      .locator("#panel-content button.ev-click")
      .filter({ hasText: text })
      .first();
    await expect(item).toBeVisible({ timeout: 10000 });
    if (opts.directClick) {
      // در شبیه‌سازی موبایل، اسکرولِ خودکار Playwright + فوکوسِ لمسی نقطه‌ی
      // کلیک را جابه‌جا می‌کند (کلیک روی «عنوان گروه» می‌افتد)؛ پس همان
      // کلیکِ خودِ دکمه را اجرا می‌کنیم — همان هندلر کلیک صفحه.
      await item.evaluate((el) => el.click());
    } else {
      // وسط کادر دید بیاید تا نوار پایین موبایل روی آن نیفتد
      await item.evaluate((el) => el.scrollIntoView({ block: "center", inline: "nearest" }));
      await page.waitForTimeout(120);
      // کلیک روی نام (نه تصویر): کلیک روی تصویر لایت‌باکس سراسری را باز می‌کند
      await item.locator(".e-name").click();
    }
    await page.waitForSelector("#modal-event-detail.open");
    await page.waitForSelector("#event-detail-body .sd-card");
    await page.waitForTimeout(400); // پایان انیمیشن باز شدن
    if (shotName) await shot(page, shotName);
  }

  async function closeEvent(page) {
    await page.click(
      '#modal-event-detail .modal-foot [data-close-modal="modal-event-detail"]'
    );
    await page.waitForSelector("#modal-event-detail", { state: "hidden" });
  }

  const cardTitles = (page, body) =>
    page.$$eval(`${body} .sd-card-title`, (els) =>
      els.map((e) => e.textContent.trim())
    );

  const cardLabels = (page, body, card) =>
    page.$$eval(`${body} .sd-card:nth-of-type(${card}) .sd-k`, (els) =>
      els.map((e) => e.textContent.trim())
    );

  const cardValues = (page, body, card) =>
    page.$$eval(`${body} .sd-card:nth-of-type(${card}) .sd-v`, (els) =>
      els.map((e) => e.textContent.trim())
    );

  const tileValue = (page, body, label) =>
    page
      .locator(`${body} .sd-tile`, { has: page.locator(".sd-k", { hasText: label }) })
      .first()
      .locator(".sd-v")
      .innerText();

  async function expectHeader(page, body, name, withImage) {
    const head = page.locator(`${body} .sd-header`);
    await expect(head).toBeVisible();
    await expect(head.locator(".sd-name")).toHaveText(name);
    if (withImage) {
      const img = head.locator("img.sd-thumb");
      await expect(img).toBeVisible();
      const natural = await img.evaluate((el) => el.naturalWidth);
      expect(natural).toBeGreaterThan(50); // تصویر واقعی، نه فایل ۱×۱
      const size = await img.evaluate((el) => {
        const cs = getComputedStyle(el);
        return [cs.width, cs.height];
      });
      expect(size).toEqual(["96px", "96px"]);
    } else {
      await expect(head.locator("span.sd-thumb svg")).toBeVisible();
    }
  }

  async function expectFooterLink(page, text, href) {
    const link = page.locator("#event-detail-link");
    await expect(link).toBeVisible();
    await expect(link).toHaveText(text);
    expect(await link.getAttribute("href")).toBe(href);
  }

  async function expectNoOverflow(page) {
    const overflow = await page.evaluate(() => {
      const body = document.querySelector("#event-detail-body");
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
      path: path.join(SHOTS, `calendar-detail-${name}.png`),
      fullPage: false,
    });
  }

  /* کل جزئیات یک مودال: عنوان کارت‌ها + برچسب/مقدارِ هر کاشی */
  async function readDetail(page, body) {
    const titles = await cardTitles(page, body);
    const cards = [];
    for (let i = 1; i <= titles.length; i += 1) {
      cards.push({
        title: titles[i - 1],
        labels: await cardLabels(page, body, i),
        values: await cardValues(page, body, i),
      });
    }
    const name = await page.locator(`${body} .sd-name`).innerText();
    return { name, cards };
  }

  /* ---------------- فروش: نقدی / بیعانه / اعتباری ---------------- */

  test.describe("sell", () => {
    test("cash: tiles are identical to the sold page", async ({ page }) => {
      const errors = [];
      page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
      page.on("pageerror", (e) => errors.push(String(e)));

      await setTheme(page, "light");
      await openDay(page);
      await openEvent(page, seeded.cash.product_name, "sell-light");

      await expectHeader(page, "#event-detail-body", seeded.cash.product_name, !!PRODUCT_IMAGE);
      expect(await cardTitles(page, "#event-detail-body")).toEqual([
        "اطلاعات ساعت",
        "اطلاعات فروش",
      ]);
      expect(await cardLabels(page, "#event-detail-body", 1)).toEqual(CARD1_LABELS);
      expect(await cardLabels(page, "#event-detail-body", 2)).toEqual(SALE_CARD2.cash);

      expect(await tileValue(page, "#event-detail-body", "برند")).toBe("سیکو");
      expect(await tileValue(page, "#event-detail-body", "قیمت خرید")).toBe("۱٬۰۰۰٬۰۰۰ تومان");
      expect(await tileValue(page, "#event-detail-body", "قیمت فروش")).toBe(seeded.cash.sale_price_display + " تومان");
      expect(await tileValue(page, "#event-detail-body", "خریدار")).toBe(seeded.cash.customer);
      expect(await tileValue(page, "#event-detail-body", "شماره تماس خریدار")).toBe(seeded.cash.customer_phone_fa);
      expect(await tileValue(page, "#event-detail-body", "نوع پرداخت")).toBe("تسویه کامل");
      await expect(page.locator("#event-detail-body .sd-v.sd-profit")).toHaveCount(1);
      await expect(
        page.locator("#event-detail-body .sd-tile.span-2:has(.sd-v.sd-notes)")
      ).toContainText("یادداشت فروش نقدی");

      await expectFooterLink(page, "مشاهده در فروش‌ها", `/sold?highlight=${seeded.cash.id}`);
      await expectNoOverflow(page);

      const fromCalendar = await readDetail(page, "#event-detail-body");
      await closeEvent(page);

      // همان ردیف در صفحه‌ی فروش‌ها — باید دقیقاً همان کارت‌ها را بدهد
      await page.goto(`${BASE}/sold`);
      await page.waitForSelector("#sales-table");
      const row = page.locator(`tr.ev-row[data-id="${seeded.cash.id}"]`);
      await expect(row).toBeVisible({ timeout: 10000 });
      await row.locator("td").nth(2).click();
      await page.waitForSelector("#modal-sale-detail.open");
      await page.waitForSelector("#sale-detail-body .sd-card");
      await page.waitForTimeout(400);
      const fromSold = await readDetail(page, "#sale-detail-body");
      expect(fromCalendar.cards).toEqual(fromSold.cards);
      expect(fromCalendar.name).toBe(fromSold.name);

      // اسکرین‌شات دارکِ همان فروش (۹۶px سرصفحه، دو کارت کامل)
      await setTheme(page, "dark");
      await openDay(page);
      await openEvent(page, seeded.cash.product_name, "sell-dark");
      expect(await cardLabels(page, "#event-detail-body", 2)).toEqual(SALE_CARD2.cash);
      await closeEvent(page);

      expect(errors).toEqual([]);
    });

    test("deposit: paid / remaining / settlement tiles", async ({ page }) => {
      const errors = [];
      page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
      page.on("pageerror", (e) => errors.push(String(e)));

      await setTheme(page, "light");
      await openDay(page);
      await openEvent(page, seeded.deposit.product_name, "deposit-light");

      await expectHeader(page, "#event-detail-body", seeded.deposit.product_name, !!PRODUCT_IMAGE);
      expect(await cardLabels(page, "#event-detail-body", 2)).toEqual(SALE_CARD2.deposit);
      expect(await tileValue(page, "#event-detail-body", "پرداخت‌شده تاکنون")).toBe("۵۰۰٬۰۰۰ تومان");
      expect(await tileValue(page, "#event-detail-body", "مانده")).toBe("۱٬۵۰۰٬۰۰۰ تومان");
      expect(await tileValue(page, "#event-detail-body", "وضعیت تسویه")).toBe("در انتظار تسویه");
      // دو بج کهربایی: نوع پرداخت + وضعیت تسویه
      await expect(page.locator("#event-detail-body .sd-tile .badge.amber.plain")).toHaveCount(2);
      await expectFooterLink(page, "مشاهده در فروش‌ها", `/sold?highlight=${seeded.deposit.id}`);
      await expectNoOverflow(page);
      await closeEvent(page);

      await setTheme(page, "dark");
      await openDay(page);
      await openEvent(page, seeded.deposit.product_name, "deposit-dark");
      expect(await cardLabels(page, "#event-detail-body", 2)).toEqual(SALE_CARD2.deposit);
      expect(await tileValue(page, "#event-detail-body", "مانده")).toBe("۱٬۵۰۰٬۰۰۰ تومان");
      await closeEvent(page);

      expect(errors).toEqual([]);
    });

    test("credit: service + tracking code with prefix", async ({ page }) => {
      const errors = [];
      page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
      page.on("pageerror", (e) => errors.push(String(e)));

      await setTheme(page, "light");
      await openDay(page);
      await openEvent(page, seeded.credit.product_name, "credit-light");

      await expectHeader(page, "#event-detail-body", seeded.credit.product_name, !!PRODUCT_IMAGE);
      expect(await cardLabels(page, "#event-detail-body", 2)).toEqual(SALE_CARD2.credit);
      expect(await tileValue(page, "#event-detail-body", "سرویس")).toBe("ترب‌پی");
      const tracking = page.locator('#event-detail-body .code-pill[dir="ltr"]');
      await expect(tracking).toHaveCount(1);
      await expect(tracking).toHaveText(`T-${`${RUN}`.slice(-7)}`);
      await expect(page.locator("#event-detail-body .sd-tile .badge.blue.plain")).toHaveCount(1);
      await expectNoOverflow(page);
      await closeEvent(page);

      await setTheme(page, "dark");
      await openDay(page);
      await openEvent(page, seeded.credit.product_name, "credit-dark");
      await expect(
        page.locator('#event-detail-body .code-pill[dir="ltr"]')
      ).toHaveText(`T-${`${RUN}`.slice(-7)}`);
      await closeEvent(page);

      expect(errors).toEqual([]);
    });
  });

  /* ---------------- خرید ---------------- */

  test("buy: header + ساعت + موجودی cards, empty values show «—»", async ({ page }) => {
    const errors = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(String(e)));

    await setTheme(page, "light");
    await openDay(page);
    await openEvent(page, `ساعت خرید تقویم ${RUN}`, "buy-light");

    await expectHeader(page, "#event-detail-body", seeded.buy.name, !!PRODUCT_IMAGE);
    expect(await cardTitles(page, "#event-detail-body")).toEqual([
      "اطلاعات ساعت",
      "اطلاعات موجودی",
    ]);
    expect(await cardLabels(page, "#event-detail-body", 1)).toEqual(CARD1_LABELS);
    expect(await cardLabels(page, "#event-detail-body", 2)).toEqual(BUY_CARD2_LABELS);

    expect(await tileValue(page, "#event-detail-body", "برند")).toBe("سیکو");
    expect(await tileValue(page, "#event-detail-body", "کد رفرانس")).toBe(seeded.buy.reference);
    expect(await tileValue(page, "#event-detail-body", "تاریخ خرید")).toBe(seeded.buy.purchase_date_fa);
    expect(await tileValue(page, "#event-detail-body", "قیمت خرید")).toBe("۱٬۰۰۰٬۰۰۰ تومان");
    expect(await tileValue(page, "#event-detail-body", "وضعیت")).toBe("موجود");
    await expect(page.locator("#event-detail-body .sd-v .badge.green.plain")).toHaveCount(1);
    await expect(
      page.locator("#event-detail-body .sd-tile.span-2:has(.sd-v.sd-notes)")
    ).toContainText("یادداشت خرید تقویم");

    await expectFooterLink(page, "مشاهده در انبار", "/products");
    await expectNoOverflow(page);
    await closeEvent(page);

    // خرید بدون مشخصات: کارت ۱ همه «—» و بدون کاشی یادداشت
    await openEvent(page, `ساعت خرید بدون مشخصات ${RUN}`);
    await expectHeader(page, "#event-detail-body", seeded.buyEmpty.name, false);
    const values = await cardValues(page, "#event-detail-body", 1);
    expect(values[0]).toBe("—"); // برند
    expect(values[1]).toBe("—"); // کد رفرانس
    expect(values[4]).toBe("۱٬۰۰۰٬۰۰۰ تومان"); // قیمت خرید
    expect(values[5]).toBe(seeded.buyEmpty.purchase_date_fa); // تاریخ خرید
    expect(values[6]).toBe("—"); // تأمین‌کننده
    expect(await cardLabels(page, "#event-detail-body", 2)).toEqual(["وضعیت"]);
    await expect(page.locator("#event-detail-body .sd-v.sd-notes")).toHaveCount(0);
    // تنها کاشی کارت ۲ تمام‌عرض است
    await expect(page.locator("#event-detail-body .sd-card:nth-of-type(2) .sd-tile.span-2")).toHaveCount(1);
    await expectNoOverflow(page);
    await closeEvent(page);

    await setTheme(page, "dark");
    await openDay(page);
    await openEvent(page, `ساعت خرید تقویم ${RUN}`, "buy-dark");
    expect(await cardTitles(page, "#event-detail-body")).toEqual([
      "اطلاعات ساعت",
      "اطلاعات موجودی",
    ]);
    await closeEvent(page);

    expect(errors).toEqual([]);
  });

  /* ---------------- تعمیرات ---------------- */

  test.describe("repairs", () => {
    test("received: کد ساعت + ایراد (multi-line), both dates, empty price", async ({ page }) => {
      const errors = [];
      page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
      page.on("pageerror", (e) => errors.push(String(e)));

      await setTheme(page, "light");
      await openDay(page);
      await openEvent(page, seeded.repIn.watch_name, "rep-in-light");

      await expect(page.locator("#event-detail-title")).toHaveText("ساعت تعمیری — دریافت");
      await expectHeader(page, "#event-detail-body", seeded.repIn.watch_name, !!PRODUCT_IMAGE);
      expect(await cardTitles(page, "#event-detail-body")).toEqual([
        "اطلاعات ساعت",
        "اطلاعات تعمیر",
      ]);
      expect(await cardLabels(page, "#event-detail-body", 1)).toEqual(REPAIR_CARD1_LABELS);
      // بدون یادداشت → کاشی یادداشت وجود ندارد
      expect(await cardLabels(page, "#event-detail-body", 2)).toEqual(
        REPAIR_CARD2_LABELS.filter((l) => l !== "یادداشت")
      );

      expect(await tileValue(page, "#event-detail-body", "کد ساعت")).toBe(seeded.repIn.watch_code);
      const issue = page.locator("#event-detail-body .sd-tile.span-2 .sd-v.sd-pre");
      await expect(issue).toHaveCount(1);
      expect(await issue.evaluate((el) => getComputedStyle(el).whiteSpace)).toBe("pre-wrap");
      // شکست خط حفظ شده (دو خط)
      const issueHeight = await issue.evaluate((el) => el.getBoundingClientRect().height);
      const oneLine = await issue.evaluate((el) => parseFloat(getComputedStyle(el).lineHeight));
      expect(issueHeight).toBeGreaterThan(oneLine * 1.5);

      expect(await tileValue(page, "#event-detail-body", "مشتری")).toBe(seeded.repIn.customer_name);
      expect(await tileValue(page, "#event-detail-body", "شماره تماس مشتری")).toBe(seeded.repIn.customer_phone_fa);
      expect(await tileValue(page, "#event-detail-body", "تاریخ دریافت")).toBe(seeded.repIn.delivery_date_fa);
      expect(await tileValue(page, "#event-detail-body", "تاریخ بازگشت")).toBe("—");
      expect(await tileValue(page, "#event-detail-body", "گارانتی")).toBe("خیر");
      expect(await tileValue(page, "#event-detail-body", "وضعیت")).toBe("دریافت شده");
      await expect(page.locator("#event-detail-body .sd-v .badge.blue.plain")).toHaveCount(1);
      expect(await tileValue(page, "#event-detail-body", "هزینه تعمیر")).toBe("—");

      await expectFooterLink(page, "مشاهده در تعمیرات", "/repairs");
      await expectNoOverflow(page);
      await closeEvent(page);

      await setTheme(page, "dark");
      await openDay(page);
      await openEvent(page, seeded.repIn.watch_name, "rep-in-dark");
      await expect(page.locator("#event-detail-title")).toHaveText("ساعت تعمیری — دریافت");
      await closeEvent(page);

      expect(errors).toEqual([]);
    });

    test("returned: both dates, price money, notes tile, status badge", async ({ page }) => {
      const errors = [];
      page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
      page.on("pageerror", (e) => errors.push(String(e)));

      await setTheme(page, "light");
      await openDay(page);
      await openEvent(page, seeded.repOut.watch_name, "rep-out-light");

      await expect(page.locator("#event-detail-title")).toHaveText("ساعت تعمیری — بازگشت");
      await expectHeader(page, "#event-detail-body", seeded.repOut.watch_name, !!PRODUCT_IMAGE);
      expect(await cardLabels(page, "#event-detail-body", 1)).toEqual(REPAIR_CARD1_LABELS);
      expect(await cardLabels(page, "#event-detail-body", 2)).toEqual(REPAIR_CARD2_LABELS);

      expect(await tileValue(page, "#event-detail-body", "تاریخ دریافت")).toBe(seeded.repOut.delivery_date_fa);
      expect(await tileValue(page, "#event-detail-body", "تاریخ بازگشت")).toBe(seeded.repOut.return_date_fa);
      expect(await tileValue(page, "#event-detail-body", "گارانتی")).toBe("بله");
      expect(await tileValue(page, "#event-detail-body", "وضعیت")).toBe("تحویل شده");
      await expect(page.locator("#event-detail-body .sd-v .badge.gray.plain")).toHaveCount(1);
      expect(await tileValue(page, "#event-detail-body", "هزینه تعمیر")).toBe("۲۵۰٬۰۰۰ تومان");
      await expect(
        page.locator("#event-detail-body .sd-tile.span-2:has(.sd-v.sd-notes)")
      ).toContainText("یادداشت تعمیر بازگشتی");

      await expectFooterLink(page, "مشاهده در تعمیرات", "/repairs");
      await expectNoOverflow(page);
      await closeEvent(page);

      await setTheme(page, "dark");
      await openDay(page);
      await openEvent(page, seeded.repOut.watch_name, "rep-out-dark");
      expect(await tileValue(page, "#event-detail-body", "هزینه تعمیر")).toBe("۲۵۰٬۰۰۰ تومان");
      await closeEvent(page);

      expect(errors).toEqual([]);
    });
  });

  /* ---------------- موبایل ۳۹۰px ---------------- */

  test.describe("mobile 390px", () => {
    test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

    test("all four kinds at 390px: one column, scrollable body, visible footer", async ({
      page,
    }) => {
      const cases = [
        ["sell", seeded.cash.product_name],
        ["buy", `ساعت خرید تقویم ${RUN}`],
        ["rep-in", seeded.repIn.watch_name],
        ["rep-out", seeded.repOut.watch_name],
      ];
      await setTheme(page, "light");
      await openDay(page);

      for (const [shotName, text] of cases) {
        await openEvent(page, text, `${shotName}-mobile`, { directClick: true });

        const cols = await page.$eval(
          "#event-detail-body .sd-grid",
          (el) => getComputedStyle(el).gridTemplateColumns.split(" ").length
        );
        expect(cols).toBe(1);
        await expectNoOverflow(page);

        // فوتر (لینک + دکمه‌ی بستن) همیشه در کادر دید است
        const footBtn = page.locator(
          '#modal-event-detail .modal-foot [data-close-modal="modal-event-detail"]'
        );
        await expect(footBtn).toBeVisible();
        const box = await footBtn.boundingBox();
        const vh = page.viewportSize().height;
        expect(box.y + box.height).toBeLessThanOrEqual(vh + 1);

        // بدنه‌ی مودال خودش اسکرول می‌شود (نه کل صفحه)
        const scroll = await page.$eval("#event-detail-body", (el) => {
          el.scrollTop = 99999;
          return {
            scrollable: el.scrollHeight > el.clientHeight,
            moved: el.scrollTop > 0,
          };
        });
        if (scroll.scrollable) expect(scroll.moved).toBe(true);

        await closeEvent(page);
      }
    });
  });
});
