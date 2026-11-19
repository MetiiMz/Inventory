// Positive-only baseline check: layout must be pixel-identical to before
// (bottom = 0, no zero line, no clamping side-effects).
// Run against http://127.0.0.1:8018 (TIKOTIME_DB=/tmp/browser_check_positive.db)
import { test, expect } from "@playwright/test";

const BASE = "http://127.0.0.1:8018";
const PAD_T = 26;
const BOTTOM = 306;

test("positive-only chart: no zero line, everything inside plot, no console errors", async ({ page }) => {
  const errors = [];
  page.on("console", (m) => {
    if (m.type() === "error" || m.type() === "critical") errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto(`${BASE}/dashboard`);
  await page.waitForLoadState("networkidle");
  expect(errors).toEqual([]);

  const check = (boxId) => {
    const svg = page.locator(`#${boxId} svg`);
    return svg.evaluate((el) => {
      const out = [];
      const padT = 26, bottom = 306;
      el.querySelectorAll("path, circle").forEach((n) => {
        const b = n.getBBox();
        if (n.tagName === "circle") {
          const cy = +n.getAttribute("cy");
          if (cy < padT || cy > bottom) out.push("circle");
        } else if (b.y < padT - 4 || b.y + b.height > bottom + 4) out.push("path");
      });
      return out;
    });
  };

  await expect(check("sales-chart")).resolves.toEqual([]);
  await expect(check("channels-chart")).resolves.toEqual([]);

  // no zero line when no negative value exists
  const zeroLines = await page.locator("#sales-chart line[opacity=\"0.5\"]").count();
  expect(zeroLines).toBe(0);
});