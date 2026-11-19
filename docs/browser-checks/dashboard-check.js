// Browser check: dashboard activity chart with negative profit (real browser).
// Run:  TIKOTIME_DB=/tmp/browser_check.db npx playwright test
//       (Django dev server must be running on http://127.0.0.1:8017)
import { test, expect } from "@playwright/test";

const BASE = "http://127.0.0.1:8017";
const PAD_T = 26;
const PAD_B = 34;
const H = 340;
const BOTTOM = H - PAD_B; // 306

test("activity chart with negative profit stays inside the plot area", async ({ page }) => {
  const errors = [];
  page.on("console", (m) => {
    if (m.type() === "error" || m.type() === "critical") errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto(`${BASE}/dashboard`);
  await page.waitForLoadState("networkidle");

  expect(errors).toEqual([]);

  const activity = page.locator("#sales-chart svg");
  await expect(activity).toBeVisible();

  /* every path/circle of the activity chart stays inside [PAD_T, H-PAD_B]
     (getBBox reports logical SVG user units, unaffected by CSS scaling) */
  /* every path/circle of the activity chart stays inside [PAD_T, H-PAD_B]
     (centres / curve coordinates, not the few px of stroke or marker radius) */
  const circles = activity.locator("circle");
  const cCount = await circles.count();
  for (let i = 0; i < cCount; i++) {
    const cy = +(await circles.nth(i).getAttribute("cy"));
    expect(cy).toBeGreaterThanOrEqual(PAD_T);
    expect(cy).toBeLessThanOrEqual(BOTTOM);
  }
  const badPaths = await activity.evaluate((svg) => {
    const out = [];
    const padT = 26, bottom = 306;
    svg.querySelectorAll("path").forEach((el) => {
      const b = el.getBBox();
      if (b.y < padT - 4 || b.y + b.height > bottom + 4) out.push(el.tagName);
    });
    return out;
  });
  expect(badPaths).toEqual([]);

  /* zero line exists because negative values exist */
  const zeroLine = activity.locator("line[opacity=\"0.5\"]");
  await expect(zeroLine).toHaveCount(1);
  const zeroY = +(await zeroLine.getAttribute("y1"));

  /* at least one profit point lies below the zero line and above the baseline */
  let belowZero = 0;
  for (let i = 0; i < cCount; i++) {
    const cy = +(await circles.nth(i).getAttribute("cy"));
    expect(cy).toBeGreaterThanOrEqual(24);
    expect(cy).toBeLessThanOrEqual(308);
    if (cy > zeroY + 1 && cy < 305) belowZero++;
  }
  expect(belowZero).toBeGreaterThan(0);

  /* tooltip shows a signed negative profit correctly: «-۶۰» not «۶۰-» */
  const hit = page.locator(".hit").nth(1); // ordibehesht ۱۴۰۵: profit -۶۰
  await hit.hover();
  const tooltip = page.locator(".bar-tooltip.show");
  await expect(tooltip).toBeVisible();
  const signed = tooltip.locator("span[dir=\"ltr\"]");
  await expect(signed).toHaveCount(1);
  await expect(signed).toHaveText(/-۶۰/);

  /* light screenshot of the activity chart with negative profit */
  await activity.screenshot({ path: "docs/browser-checks/activity-negative-light.png" });

  /* channels chart (counts, never negative) must stay inside the plot area too */
  const channels = page.locator("#channels-chart svg");
  await expect(channels).toBeVisible();
  const chBad = await channels.evaluate((svg) => {
    const out = [];
    const padT = 26, bottom = 306;
    svg.querySelectorAll("path, circle").forEach((el) => {
      const b = el.getBBox();
      if (el.tagName === "circle") {
        const cy = +el.getAttribute("cy");
        if (cy < padT || cy > bottom) out.push("circle");
      } else if (b.y < padT - 4 || b.y + b.height > bottom + 4) out.push("path");
    });
    return out;
  });
  expect(chBad).toEqual([]);

  /* dark theme screenshot */
  await page.locator('button.theme-toggle').click();
  await page.waitForTimeout(300);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await activity.screenshot({ path: "docs/browser-checks/activity-negative-dark.png" });
});

test("404 page works for an unknown URL", async ({ page }) => {
  const res = await page.goto(`${BASE}/api/unknown-path`);
  expect(res.status()).toBe(404);
  const json = await res.json();
  expect(json.ok).toBe(false);
  expect(json.error).toContain("یافت نشد");
});