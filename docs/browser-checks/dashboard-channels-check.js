// ============================================================================
// TikoTime — Dashboard channels chart browser checks
// Seeds a month with snappay×2, digipay×1, torob×3 credit sales (+ person/online
// sales) via the real API, then asserts the channels-chart tooltip shows the
// credit breakdown sub-rows (اسنپ‌پی / دیجی‌پی / 트وبی) and that both charts stay
// inside the plot area. Light + dark screenshots saved next to this file.
//
// Run with:
//   TIKOTIME_DB=/tmp/check_dash_channels.db .venv/bin/python backend/manage.py migrate --noinput
//   TIKOTIME_DB=/tmp/check_dash_channels.db .venv/bin/python backend/manage.py runserver 127.0.0.1:8013 --noreload
//   TIKOTIME_BASE=http://127.0.0.1:8013 npx playwright test dashboard-channels-check.js
// Temp DB only — never touches db/db.sqlite3.
// ============================================================================

const { test, expect } = require("@playwright/test");

const BASE = process.env.TIKOTIME_BASE || "http://127.0.0.1:8000";
const SHOTS = __dirname;

/* Today's Jalali month (1405/08 = Aban) — seed in the current month so the
   sales are drawn (not future). Sale_date is ISO Gregorian. */
const TODAY = "2026-11-19"; // ۱۴۰۵/۰۸/۲۸ — Aban 1405

test.describe("dashboard channels chart — credit breakdown tooltip", () => {
  test.beforeAll(async ({ request }) => {
    const prod = async (code) => {
      const res = await request.post(`${BASE}/api/products`, {
        data: {
          name: `ساعت داشبورد ${code} ${Date.now()}`,
          office_code: `OF-D-${code}-${Date.now()}`,
          website_code: `WS-D-${code}-${Date.now()}`,
          brand: "سیکو",
          supplier: "تأمین‌کننده داشبورد",
          purchase_price: "1000000",
          purchase_date: TODAY,
          image: "",
        },
      });
      if (!res.ok()) throw new Error(`product ${code}: ${await res.text()}`);
      return (await res.json()).product.id;
    };

    const sale = (pid, payload) =>
      request.post(`${BASE}/api/sales`, {
        data: {
          product_id: pid,
          sale_price: "1500000",
          sale_date: TODAY,
          ...payload,
        },
      });

    // unique product per sale (a product is unavailable once sold)
    const [p1, p2, p3, p4, p5, p6, p7, p8] = await Promise.all(
      ["1", "2", "3", "4", "5", "6", "7", "8"].map(prod),
    );

    // snappay × 2 (person + online)
    await sale(p1, {
      sale_type: "person",
      payment_type: "credit",
      credit_provider: "snappay",
      credit_tracking_code: "S-1000001",
      customer: "a",
      customer_phone: "09120000001",
    });
    await sale(p2, {
      sale_type: "online",
      payment_type: "credit",
      credit_provider: "snappay",
      credit_tracking_code: "S-1000002",
      customer: "b",
      customer_phone: "09120000002",
    });
    // digipay × 1 (person)
    await sale(p3, {
      sale_type: "person",
      payment_type: "credit",
      credit_provider: "digipay",
      credit_tracking_code: "D-1000003",
      customer: "c",
      customer_phone: "09120000003",
    });
    // torob × 3 (person ×2 + online ×1)
    await sale(p4, {
      sale_type: "person",
      payment_type: "credit",
      credit_provider: "torob",
      credit_tracking_code: "T-1000004",
      customer: "d",
      customer_phone: "09120000004",
    });
    await sale(p5, {
      sale_type: "person",
      payment_type: "credit",
      credit_provider: "torob",
      credit_tracking_code: "T-1000005",
      customer: "e",
      customer_phone: "09120000005",
    });
    await sale(p6, {
      sale_type: "online",
      payment_type: "credit",
      credit_provider: "torob",
      credit_tracking_code: "T-1000006",
      customer: "f",
      customer_phone: "09120000006",
    });
    // plain person + online sales (not credit)
    await sale(p7, {
      sale_type: "person",
      payment_type: "cash",
      customer: "g",
      customer_phone: "09120000007",
    });
    await sale(p8, {
      sale_type: "online",
      payment_type: "cash",
      customer: "h",
      customer_phone: "09120000008",
    });
  });

  test("tooltip shows credit breakdown sub-rows; both charts inside plot area; screenshots light+dark", async ({
    page,
  }) => {
    const errors = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(String(e)));

    await page.goto(`${BASE}/dashboard`);
    await page.waitForSelector("#channels-chart svg");

    /* ---------- structure ---------- */
    const title = await page.locator("#channels-title").innerText();
    expect(title).toContain("تعداد فروش به تفکیک نوع");

    /* ---------- geometry: both charts stay inside the plot area ---------- */
    const sample = (id) =>
      page.evaluate((id) => {
        const svg = document.querySelector(`#${id} svg`);
        const paths = [...svg.querySelectorAll("path[fill=\"none\"]")];
        let minY = Infinity,
          maxY = -Infinity;
        for (const p of paths) {
          const len = p.getTotalLength();
          for (let l = 0; l <= len; l += 0.5) {
            const y = p.getPointAtLength(l).y;
            if (y < minY) minY = y;
            if (y > maxY) maxY = y;
          }
        }
        const circles = [...svg.querySelectorAll("circle")].map(
          (c) => +c.getAttribute("cy"),
        );
        return {
          minY,
          maxY,
          circlesMin: Math.min(...circles),
          circlesMax: Math.max(...circles),
          hits: svg.querySelectorAll(".hit").length,
        };
      }, id);

    for (const id of ["sales-chart", "channels-chart"]) {
      const g = await sample(id);
      expect(g.minY).toBeGreaterThanOrEqual(26 - 0.05); // PAD_T
      expect(g.maxY).toBeLessThanOrEqual(306 + 0.05); // H - PAD_B
      expect(g.circlesMin).toBeGreaterThanOrEqual(26 - 0.05);
      expect(g.circlesMax).toBeLessThanOrEqual(306 + 0.05);
      expect(g.hits).toBe(8); // current month + future months drawn as hit areas
    }

    /* ---------- tooltip: hover the current month (last actual) ---------- */
    const hitCount = await page.evaluate(
      () => document.querySelectorAll("#channels-chart .hit").length,
    );
    // current month = last non-future hit = index hits-1
    const curIdx = hitCount - 1;
    await page.locator("#channels-chart .hit").nth(curIdx).hover();
    await page.waitForTimeout(300);
    const rows = await page.evaluate(() =>
      [...document.querySelectorAll("#channels-chart .bar-tooltip.show .bt-row")].map(
        (r) => [r.querySelector("span").textContent, r.querySelector("b").textContent],
      ),
    );

    // Aban 1405: credit = snappay 2 + digipay 1 + torob 3 = 6
    expect(rows).toContainEqual(["اعتباری", "۶"]);
    expect(rows).toContainEqual(["اسنپ‌پی", "۲"]);
    expect(rows).toContainEqual(["دیجی‌پی", "۱"]);
    expect(rows).toContainEqual(["ترب‌پی", "۳"]);
    // sub-rows are indented/smaller/muted (.bt-sub)
    const sub = await page.evaluate(() =>
      [...document.querySelectorAll("#channels-chart .bar-tooltip.show .bt-sub")].map(
        (r) => r.querySelector("span").textContent,
      ),
    );
    expect(sub).toContain("اسنپ‌پی");
    expect(sub).toContain("دیجی‌پی");
    expect(sub).toContain("ترب‌پی");

    /* ---------- screenshots: light + dark ---------- */
    await page.mouse.move(5, 5);
    await page.screenshot({
      path: `${SHOTS}/dashboard-channels-light.png`,
      fullPage: true,
    });

    await page.evaluate(() =>
      localStorage.setItem("satchour-theme", "dark"),
    );
    await page.reload();
    await page.waitForSelector("#channels-chart svg");
    const theme = await page.evaluate(
      () => document.documentElement.dataset.theme,
    );
    expect(theme).toBe("dark");
    await page.screenshot({
      path: `${SHOTS}/dashboard-channels-dark.png`,
      fullPage: true,
    });

    expect(errors).toEqual([]);
  });
});
