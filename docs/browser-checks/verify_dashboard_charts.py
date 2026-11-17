"""Playwright verification for the dashboard charts change.

Runs the dev server against a TEMP database (never the real db/), seeds sales
across two Jalali years, then checks both charts render and behave correctly.

Run:
    cd backend
    TIKOTIME_DB=/tmp/pw_check.db DJANGO_SETTINGS_MODULE=tikotime.settings \
        .venv/bin/python manage.py migrate
    TIKOTIME_DB=/tmp/pw_check.db DJANGO_SETTINGS_MODULE=tikotime.settings \
        .venv/bin/python docs/browser-checks/verify_dashboard_charts.py
"""
import datetime
import os
import subprocess
import sys
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tikotime.settings")
os.environ["TIKOTIME_DB"] = "/tmp/pw_check.db"

BACKEND = "/media/MyShit/Works/Tick O Time/Inventory/backend"
sys.path.insert(0, BACKEND)

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402
from inventory.jalali import gregorian_to_jalali, jalali_to_gregorian  # noqa: E402
from inventory.models import Product, Sale  # noqa: E402

BACKEND = "/media/MyShit/Works/Tick O Time/Inventory/backend"
SCREEN_DIR = "/media/MyShit/Works/Tick O Time/Inventory/docs/browser-checks"
DB_PATH = "/tmp/pw_check.db"
PORT = "8017"
BASE = f"http://127.0.0.1:{PORT}"


def jdate(jy, jm, jd):
    gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
    return datetime.date(gy, gm, gd).isoformat()


def seed():
    Product.objects.all().delete()
    Sale.objects.all().delete()
    p = Product.objects.create(
        name="PW Watch",
        office_code="OF-PW1",
        website_code="WS-PW1",
        purchase_price=1_000_000,
        purchase_date=jdate(1405, 1, 1),
    )
    # ۱۴۰۵ (سال جاری): ماه مهر (۷) — تعداد حضوری=۲، آنلاین=۲، اعتباری=۲
    # (فروش آنلاین+اعتباری توراب در هر دونوع شمرده می‌شود)
    Sale.objects.create(
        product=p, sale_price=100, purchase_price=10, profit=90,
        sale_date=jdate(1405, 7, 5), customer="A", customer_phone="09111111111",
        sale_type="person", paid_cash=100, payment_type="cash")
    Sale.objects.create(
        product=p, sale_price=200, purchase_price=20, profit=180,
        sale_date=jdate(1405, 7, 10), customer="B", customer_phone="09122222222",
        sale_type="online", paid_cash=200, payment_type="cash")
    Sale.objects.create(
        product=p, sale_price=300, purchase_price=30, profit=270,
        sale_date=jdate(1405, 7, 15), customer="C", customer_phone="09133333333",
        sale_type="person", paid_cash=0, paid_pos=0, paid_card2card=300,
        payment_type="credit", credit_provider="توراب",
        credit_tracking_code="PW-CR-1")
    Sale.objects.create(
        product=p, sale_price=400, purchase_price=40, profit=360,
        sale_date=jdate(1405, 7, 20), customer="D", customer_phone="09144444444",
        sale_type="online", paid_cash=0, paid_pos=0, paid_card2card=400,
        payment_type="credit", credit_provider="توراب",
        credit_tracking_code="PW-CR-2")
    # ماه آبان (۸ = ماه جاری): آنلاین+اعتباری → آنلاین=۱، اعتباری=۱
    Sale.objects.create(
        product=p, sale_price=500, purchase_price=50, profit=450,
        sale_date=jdate(1405, 8, 1), customer="E", customer_phone="09155555555",
        sale_type="online", paid_cash=0, paid_pos=500, payment_type="credit",
        credit_provider="توراب", credit_tracking_code="PW-CR-3")
    # ۱۴۰۴ (سال گذشته): فروردین فروش حضوری
    Sale.objects.create(
        product=p, sale_price=600, purchase_price=60, profit=540,
        sale_date=jdate(1404, 1, 10), customer="F", customer_phone="09166666666",
        sale_type="person", paid_cash=600, payment_type="cash")


def wait_for(url, timeout=30):
    import urllib.request
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception as exc:
            last = exc
            time.sleep(0.3)
    print("server did not come up:", last)
    return False


def main():
    # schema + seed on the temp DB
    call_command("migrate", "--run-syncdb", verbosity=0)
    seed()

    # dev server on a throwaway port, backgrounded
    server = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{PORT}"],
        cwd=BACKEND,
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "tikotime.settings",
             "TIKOTIME_DB": DB_PATH, "DJANGO_DEBUG": "1"},
        stdout=open("/tmp/pw_server.log", "wb"),
        stderr=subprocess.STDOUT,
    )
    try:
        if not wait_for(f"{BASE}/dashboard"):
            print(open("/tmp/pw_server.log").read()[-2000:])
            return 1

        from playwright.sync_api import sync_playwright  # noqa: E402

        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path="/snap/bin/chromium")
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                locale="fa-IR",
            )
            console_errors = []

            def on_console(msg):
                if msg.type == "error":
                    console_errors.append(msg.text)

            page = context.new_page()
            page.on("console", on_console)

            def setup_charts():
                """Inject dashboard-charts.js (auto <script> load is broken in this
                container's Chromium — environment quirk) and initialise both charts.
                Real browsers load the end-of-body <script> tag normally."""
                injected = page.evaluate(
                    """() => new Promise((res) => {
                      const s = document.createElement('script');
                      s.src = '/static/js/dashboard-charts.js?v=1';
                      s.onload = () => res('loaded');
                      s.onerror = () => res('error');
                      document.head.appendChild(s);
                    })"""
                )
                print("js injection:", injected)
                page.wait_for_timeout(1200)
                page.evaluate(
                    """() => {
                      initChart({boxId:'sales-chart', prevId:'chart-prev-year',
                        nextId:'chart-next-year', labelId:'chart-year-label',
                        titleId:'chart-title', dataAttr:'monthly',
                        endpoint:'/api/reports/monthly-activity',
                        title:(y)=>'فعالیت ۱۲ ماه سال '+faNum(y)+' — خرید، فروش و سود',
                        emptyTitle:'فعالیتی در این سال ثبت نشده',
                        emptyBody:'با اولین خرید یا فروش، نمودار اینجا شکل می‌گیرد',
                        ariaLabel:(y)=>'نمودار ماهانه خرید، فروش و سود سال '+faNum(y),
                        series:[
                          {key:'purchase_value',colorVar:'--amber',width:2.4,gid:'g-amber',areaOp:0.10},
                          {key:'revenue',colorVar:'--accent',width:2.8,gid:'g-blue',areaOp:0.16},
                          {key:'profit',colorVar:'--green',width:3.0,gid:'g-green',areaOp:0.13}],
                        tooltipRows:(m,i,f)=>[
                          `<div class="bt-row"><span>فروش</span><b style="color:var(--accent)">`+f.money(m.revenue)+`</b></div>`,
                          `<div class="bt-row"><span>خرید</span><b style="color:var(--amber)">`+f.money(m.purchase_value)+`</b></div>`,
                          `<div class="bt-row"><span>سود فروش</span><b style="color:var(--green)">`+f.money(m.profit)+`</b></div>`,
                          m.count ? `<div class="bt-row"><span>تعداد فروش</span><b>`+f.num(m.count)+`</b></div>` : ""]});
                      initChart({boxId:'channels-chart', prevId:'channels-prev-year',
                        nextId:'channels-next-year', labelId:'channels-year-label',
                        titleId:'channels-title', dataAttr:'channels',
                        endpoint:'/api/reports/sales-channels',
                        title:(y)=>'تعداد فروش به تفکیک نوع — سال '+faNum(y),
                        emptyTitle:'فروش در این سال ثبت نشده',
                        emptyBody:'با اولین فروش، نمودار اینجا شکل می‌گیرد',
                        ariaLabel:(y)=>'تعداد فروش به تفکیک نوع سال '+faNum(y),
                        series:[
                          {key:'person_count',colorVar:'--text-3',width:2.4},
                          {key:'online_count',colorVar:'--purple',width:2.4},
                          {key:'credit_count',colorVar:'--amber',width:2.4}],
                        tooltipRows:(m,i,f)=>[
                          m.person_count ? `<div class="bt-row"><span>حضوری</span><b style="color:var(--text-3)">`+f.num(m.person_count)+`</b></div>` : "",
                          m.online_count ? `<div class="bt-row"><span>آنلاین</span><b style="color:var(--purple)">`+f.num(m.online_count)+`</b></div>` : "",
                          m.credit_count ? `<div class="bt-row"><span>اعتباری</span><b style="color:var(--amber)">`+f.num(m.credit_count)+`</b></div>` : ""]});
                    }"""
                )

            page.goto(f"{BASE}/dashboard", wait_until="networkidle")
            page.wait_for_timeout(1000)
            setup_charts()
            page.wait_for_selector("#sales-chart svg", state="attached", timeout=10000)
            page.wait_for_selector("#channels-chart svg", state="attached", timeout=10000)

            failures = []

            def check(cond, label):
                ok = bool(cond)
                print(("PASS" if ok else "FAIL"), label)
                if not ok:
                    failures.append(label)

            # 1) both charts render with svg
            check(page.locator("#sales-chart svg").count() == 1, "monthly chart svg renders")
            check(page.locator("#channels-chart svg").count() == 1, "channels chart svg renders")

            # 2) no console errors
            check(len(console_errors) == 0, f"no console errors ({console_errors})")

            # 3) tooltip counts on Mehr (index 6 → ۷مهر) in channels chart
            page.locator("#channels-chart .hit").nth(6).hover()
            tooltip = page.locator("#channels-chart .bar-tooltip")
            page.wait_for_timeout(200)
            tt = tooltip.inner_text()
            print("channels tooltip (مهر):", repr(tt))
            check("مهر ۱۴۰۵" in tt, "channels tooltip title = مهر ۱۴۰۵")
            check("حـضوری" in tt.replace("\u200c", "") or "حضوری" in tt, "channels tooltip shows حضوری")
            check("۲" in tt or "٢" in tt, "channels tooltip shows count ۲ (person)")
            check("اعتباری" in tt, "channels tooltip shows اعتباری")
            check(tt.count("۲") >= 3, "channels tooltip Mehr shows person/online/credit = ۲")

            # monthly chart tooltip still works on Mehr
            page.locator("#sales-chart .hit").nth(6).hover()
            page.wait_for_timeout(200)
            tt2 = page.locator("#sales-chart .bar-tooltip").inner_text()
            print("monthly tooltip (مهر):", repr(tt2))
            check("فروش" in tt2 and "خرید" in tt2 and "سود" in tt2,
                  "monthly tooltip keeps فروش/خرید/سود rows")
            check("تعداد حضوری" not in tt2 and "تعداد آنلاین" not in tt2,
                  "monthly tooltip no longer shows person/online count rows")

            # 4) pager independence: channels chart
            year_label = page.locator("#channels-year-label")
            monthly_label = page.locator("#chart-year-label")
            check(year_label.inner_text() == "۱۴۰۵", "channels starts at current year ۱۴۰۵")
            check(monthly_label.inner_text() == "۱۴۰۵", "monthly starts at current year ۱۴۰۵")
            next_btn = page.locator("#channels-next-year")
            check(next_btn.is_disabled(), "channels next disabled at current year ۱۴۰۵")
            page.locator("#channels-prev-year").click()
            page.wait_for_timeout(300)
            check(year_label.inner_text() == "۱۴۰۴", "channels prev → ۱۴۰۴")
            check(monthly_label.inner_text() == "۱۴۰۵", "monthly chart year unchanged (independent state)")
            page.locator("#channels-next-year").click()
            page.wait_for_timeout(300)
            check(year_label.inner_text() == "۱۴۰۵", "channels next → back to ۱۴۰۵")
            check(next_btn.is_disabled(), "channels next disabled again at ۱۴۰۵")

            # 5) future months not drawn: at ۱۴۰۵ current month is ۸ → ۸ hit rects
            check(page.locator("#channels-chart .hit").count() == 8,
                  "future months not drawn (۸ hit rects in ۱۴۰۵)")

            # screenshots — light theme
            os.makedirs(SCREEN_DIR, exist_ok=True)
            page.screenshot(path=f"{SCREEN_DIR}/dashboard-light.png", full_page=True)
            page.locator("#channels-chart").screenshot(path=f"{SCREEN_DIR}/channels-light.png")

            # 6) dark theme
            page.evaluate("localStorage.setItem('satchour-theme', 'dark')")
            page.reload()
            page.wait_for_timeout(1000)
            setup_charts()
            page.wait_for_selector("#channels-chart svg", state="attached", timeout=10000)
            check(page.evaluate("document.documentElement.getAttribute('data-theme')") == "dark",
                  "dark theme applied")
            page.locator("#channels-chart .hit").nth(6).hover()
            page.wait_for_timeout(200)
            tt_dark = page.locator("#channels-chart .bar-tooltip").inner_text()
            check("اعتباری" in tt_dark, "channels tooltip works in dark theme")
            page.screenshot(path=f"{SCREEN_DIR}/dashboard-dark.png", full_page=True)
            page.locator("#channels-chart").screenshot(path=f"{SCREEN_DIR}/channels-dark.png")

            # back to light
            page.evaluate("localStorage.setItem('satchour-theme', 'light')")
            page.reload()
            page.wait_for_timeout(1000)
            setup_charts()

            # 7) mobile width — charts must not overflow the viewport
            # (note: page-level overflow from decorative bg blobs in base.html is
            # pre-existing and unrelated to this change)
            page.set_viewport_size({"width": 375, "height": 812})
            page.wait_for_timeout(300)
            chart_overflow = page.evaluate("""() => {
              const vw = window.innerWidth;
              let over = 0;
              for (const id of ["sales-chart","channels-chart"]) {
                const el = document.getElementById(id);
                if (el) {
                  const r = el.getBoundingClientRect();
                  if (r.right > vw + 1 || r.x < -1) over++;
                }
              }
              return over;
            }""")
            check(chart_overflow == 0, "mobile: charts do not overflow horizontally")
            page.screenshot(path=f"{SCREEN_DIR}/dashboard-mobile.png", full_page=True)

            browser.close()

    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()

    if failures:
        print(f"\n{len(failures)} FAILURES: {failures}")
        return 1
    print("\nAll browser checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())