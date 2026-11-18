# -*- coding: utf-8 -*-
"""Browser checks for the two dashboard charts (Playwright / Chromium).

Not part of the Django suite — it drives the real frontend.

Usage (from the repo root, server already running on 8791):
    backend/.venv/bin/python docs/browser-checks/dashboard-charts-check.py

Setup used for the screenshots committed next to this file:
    TIKOTIME_DB=/tmp/tiko_dash.sqlite3 backend/.venv/bin/python backend/manage.py migrate --noinput
    TIKOTIME_DB=/tmp/tiko_dash.sqlite3 backend/.venv/bin/python /tmp/opencode/seed_dashboard.py
    TIKOTIME_DB=/tmp/tiko_dash.sqlite3 backend/.venv/bin/python backend/manage.py \
        runserver 127.0.0.1:8791 --noreload

Seeded expectations (today = 1405/08/27):
    channels 1405:  فروردین 2/0/1 · اردیبهشت 0/2/1 · خرداد 2/1/1 · آبان 1/0/0
    (person/online/credit; the اردیبهشت online credit sale counts in online AND credit)
"""
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("TIKO_BASE", "http://127.0.0.1:8791")
SHOTS = Path(__file__).resolve().parent
PAD_T, BASE_Y = 26.0, 306.0  # viewBox 1200x340, PAD_T=26, PAD_B=34
CURRENT_YEAR_FA = "۱۴۰۵"
PREV_YEAR_FA = "۱۴۰۴"

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name} {detail}")
        failures.append(name)


# Sample every stroke path of a chart and return the vertical extremes.
SAMPLE_JS = """
(id) => {
  const box = document.getElementById(id);
  const svg = box.querySelector('svg');
  if (!svg) return null;
  const paths = [...svg.querySelectorAll('path[fill="none"]')];
  let minY = Infinity, maxY = -Infinity;
  for (const p of paths) {
    const len = p.getTotalLength();
    for (let l = 0; l <= len; l += 0.5) {
      const y = p.getPointAtLength(l).y;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
  }
  const circles = [...svg.querySelectorAll('circle')].map(c => +c.getAttribute('cy'));
  return {
    paths: paths.length,
    minY, maxY,
    circlesMin: Math.min(...circles), circlesMax: Math.max(...circles),
    vw: svg.viewBox.baseVal.width, vh: svg.viewBox.baseVal.height,
    hits: svg.querySelectorAll('.hit').length,
    labels: [...svg.querySelectorAll('text')].map(t => t.textContent),
    futureLabels: svg.querySelectorAll('text[opacity="0.45"]').length,
    hasSvg: true,
  };
}
"""

TOOLTIP_JS = """
(id) => [...document.querySelectorAll(`#${id} .bar-tooltip.show .bt-row`)]
  .map(r => [r.querySelector('span').textContent, r.querySelector('b').textContent])
"""


def hover_month(page, box_id, index):
    page.locator(f"#{box_id}").scroll_into_view_if_needed()
    x, y = page.evaluate(
        """([id, i]) => {
            const r = document.querySelectorAll(`#${id} .hit`)[i].getBoundingClientRect();
            return [r.x + r.width / 2, r.y + r.height / 2];
        }""",
        [box_id, index],
    )
    page.mouse.move(x, y)
    page.wait_for_timeout(150)
    return page.evaluate(TOOLTIP_JS, box_id)


def main():
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}")
                if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

        page.goto(f"{BASE}/dashboard", wait_until="networkidle")
        page.wait_for_selector("#channels-chart svg")

        # ---------------------------------------------------------- structure
        check("typeof initChart === 'function'",
              page.evaluate("() => typeof initChart") == "function",
              page.evaluate("() => typeof initChart"))
        check("#sales-chart has an <svg>",
              page.evaluate("() => !!document.querySelector('#sales-chart svg')"))
        check("#channels-chart has an <svg>",
              page.evaluate("() => !!document.querySelector('#channels-chart svg')"))
        check("old title unchanged",
              page.inner_text("#chart-title") == f"فعالیت ۱۲ ماه سال {CURRENT_YEAR_FA} — خرید، فروش و سود",
              page.inner_text("#chart-title"))
        check("new title",
              page.inner_text("#channels-title") == f"تعداد فروش به تفکیک نوع — سال {CURRENT_YEAR_FA}",
              page.inner_text("#channels-title"))
        check("note under the legend",
              page.evaluate("() => document.body.innerText.includes('خودش هم شمرده می‌شود')"))
        legends = page.evaluate(
            "() => [...document.querySelectorAll('.chart-legend')].map(l => l.innerText.replace(/\\s+/g, ''))")
        check("legend: old chart keeps فروش/خرید/سود فروش",
              legends[0] == "فروشخریدسودفروش", legends[0])
        check("legend: new chart حضوری/آنلاین/اعتباری",
              legends[1] == "حضوریآنلایناعتباری", legends[1])
        check("legend: no count series in the old chart",
              "تعداد حضوری" not in page.content() and "تعداد آنلاین" not in page.content())

        # ------------------------------------------------------------ geometry
        sales = page.evaluate(SAMPLE_JS, "sales-chart")
        chan = page.evaluate(SAMPLE_JS, "channels-chart")
        for name, g in (("sales-chart", sales), ("channels-chart", chan)):
            check(f"{name}: 3 line paths", g["paths"] == 3, g["paths"])
            check(f"{name}: viewBox 1200x340", (g["vw"], g["vh"]) == (1200, 340), (g["vw"], g["vh"]))
            check(f"{name}: curve stays inside the plot area",
                  g["minY"] >= PAD_T - 0.05 and g["maxY"] <= BASE_Y + 0.05,
                  f"minY={g['minY']:.2f} maxY={g['maxY']:.2f}")
            check(f"{name}: dots stay inside the plot area",
                  g["circlesMin"] >= PAD_T - 0.05 and g["circlesMax"] <= BASE_Y + 0.05,
                  f"{g['circlesMin']}..{g['circlesMax']}")
            check(f"{name}: 12 month labels", len(g["labels"]) == 12, len(g["labels"]))
            check(f"{name}: future months not drawn (8 hit areas)", g["hits"] == 8, g["hits"])
            check(f"{name}: 4 dimmed future labels", g["futureLabels"] == 4, g["futureLabels"])
            check(f"{name}: Persian month labels",
                  g["labels"][:3] == ["فروردین", "اردیبهشت", "خرداد"], g["labels"][:3])

        # ------------------------------------------------------------- tooltip
        rows = hover_month(page, "channels-chart", 2)  # خرداد
        check("channels tooltip: خرداد = حضوری ۲ / آنلاین ۱ / اعتباری ۱",
              rows == [["حضوری", "۲"], ["آنلاین", "۱"], ["اعتباری", "۱"]], rows)
        rows = hover_month(page, "channels-chart", 1)  # اردیبهشت: online credit
        check("channels tooltip: online credit counted in both",
              rows == [["آنلاین", "۲"], ["اعتباری", "۱"]], rows)
        rows = hover_month(page, "channels-chart", 3)  # تیر: all zero → title only
        check("channels tooltip: zero rows hidden", rows == [], rows)
        rows = hover_month(page, "sales-chart", 2)  # خرداد
        labels = [r[0] for r in rows]
        check("sales tooltip keeps فروش/خرید/سود فروش/تعداد فروش",
              labels == ["فروش", "خرید", "سود فروش", "تعداد فروش"], labels)

        # --------------------------------------------------------------- pager
        page.click("#channels-prev-year")
        page.wait_for_function(
            "() => document.getElementById('channels-year-label').textContent === '۱۴۰۴'")
        check("channels pager: prev → 1404",
              page.inner_text("#channels-year-label") == PREV_YEAR_FA)
        check("channels pager: independent of the old chart",
              page.inner_text("#chart-year-label") == CURRENT_YEAR_FA,
              page.inner_text("#chart-year-label"))
        check("channels pager: old title untouched",
              page.inner_text("#chart-title") == f"فعالیت ۱۲ ماه سال {CURRENT_YEAR_FA} — خرید، فروش و سود")
        check("channels pager: 1404 title + label",
              page.inner_text("#channels-title") == "تعداد فروش به تفکیک نوع — سال ۱۴۰۴")
        prev = page.evaluate(SAMPLE_JS, "channels-chart")
        check("channels 1404: all 12 months drawn", prev["hits"] == 12, prev["hits"])
        check("channels 1404: inside the plot area",
              prev["minY"] >= PAD_T - 0.05 and prev["maxY"] <= BASE_Y + 0.05,
              f"{prev['minY']:.2f}..{prev['maxY']:.2f}")
        page.click("#channels-next-year")
        page.wait_for_function(
            "() => document.getElementById('channels-year-label').textContent === '۱۴۰۵'")
        check("channels pager: next back to 1405",
              page.inner_text("#channels-year-label") == CURRENT_YEAR_FA)
        check("channels pager: next disabled at the current year",
              page.is_disabled("#channels-next-year"))

        page.click("#chart-prev-year")
        page.wait_for_function(
            "() => document.getElementById('chart-year-label').textContent === '۱۴۰۴'")
        check("sales pager: prev → 1404", page.inner_text("#chart-year-label") == PREV_YEAR_FA)
        check("sales pager: independent of the channels chart",
              page.inner_text("#channels-year-label") == CURRENT_YEAR_FA)
        page.click("#chart-next-year")
        page.wait_for_function(
            "() => document.getElementById('chart-year-label').textContent === '۱۴۰۵'")
        check("sales pager: next disabled at the current year",
              page.is_disabled("#chart-next-year"))

        # --------------------------------------------------------- screenshots
        page.mouse.move(5, 5)
        page.screenshot(path=str(SHOTS / "dashboard-light.png"), full_page=True)
        print("shot:", SHOTS / "dashboard-light.png")

        page.evaluate("() => localStorage.setItem('satchour-theme', 'dark')")
        page.reload(wait_until="networkidle")
        page.wait_for_selector("#channels-chart svg")
        check("dark theme applied",
              page.evaluate("() => document.documentElement.dataset.theme") == "dark")
        dark = page.evaluate(SAMPLE_JS, "channels-chart")
        check("dark: curve stays inside the plot area",
              dark["minY"] >= PAD_T - 0.05 and dark["maxY"] <= BASE_Y + 0.05,
              f"{dark['minY']:.2f}..{dark['maxY']:.2f}")
        page.screenshot(path=str(SHOTS / "dashboard-dark.png"), full_page=True)
        print("shot:", SHOTS / "dashboard-dark.png")

        page.evaluate("() => localStorage.setItem('satchour-theme', 'light')")
        page.set_viewport_size({"width": 390, "height": 844})
        page.reload(wait_until="networkidle")
        page.wait_for_selector("#channels-chart svg")
        # NOTE: the dashboard page as a whole still scrolls horizontally at 390px
        # because of the pre-existing brand / recent-sales tables (identical at
        # HEAD) — this feature only owns the two chart cards, so assert those.
        for sel in ("#sales-chart", "#channels-chart"):
            card = page.evaluate(
                """(sel) => {
                    const el = document.querySelector(sel).closest('section');
                    const r = el.getBoundingClientRect();
                    const svg = el.querySelector('svg').getBoundingClientRect();
                    const pager = el.querySelector('.chart-pager').getBoundingClientRect();
                    return {left: Math.round(r.left), right: Math.round(r.right),
                            w: Math.round(r.width), svgW: Math.round(svg.width),
                            svgH: Math.round(svg.height),
                            pagerLeft: Math.round(pager.left), pagerRight: Math.round(pager.right),
                            vw: window.innerWidth};
                }""",
                sel,
            )
            check(f"mobile: {sel} card fits the viewport",
                  card["left"] >= -1 and card["right"] <= card["vw"] + 1, card)
            check(f"mobile: {sel} svg scales to the card",
                  card["svgW"] <= card["w"] and card["svgH"] > 40, card)
            check(f"mobile: {sel} pager fits",
                  card["pagerLeft"] >= -1 and card["pagerRight"] <= card["vw"] + 1, card)
            spill = page.evaluate(
                """(sel) => {
                    const section = document.querySelector(sel).closest('section');
                    const c = section.getBoundingClientRect();
                    const bad = [];
                    section.querySelectorAll('*').forEach(el => {
                        const r = el.getBoundingClientRect();
                        if (r.width && (r.right > c.right + 2 || r.left < c.left - 2))
                            bad.push(`${el.tagName}.${el.getAttribute('class') || ''}`);
                    });
                    return bad.slice(0, 6);
                }""",
                sel,
            )
            check(f"mobile: {sel} nothing inside the card spills out", not spill, spill)
        check("mobile: charts still rendered",
              page.evaluate("() => document.querySelectorAll('#sales-chart svg, #channels-chart svg').length") == 2)
        page.locator("#channels-chart").scroll_into_view_if_needed()
        page.screenshot(path=str(SHOTS / "dashboard-mobile.png"), full_page=True)
        print("shot:", SHOTS / "dashboard-mobile.png")
        print("mobile page scrollWidth:", page.evaluate("() => document.documentElement.scrollWidth"))

        check("zero console errors / pageerrors", not errors, errors)
        browser.close()

    print("\nfailures:", json.dumps(failures, ensure_ascii=False) if failures else "none")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
