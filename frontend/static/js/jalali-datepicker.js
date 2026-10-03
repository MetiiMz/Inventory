/* ============================================================
   TikoTime — تقویم شمسی پاپ‌آپ (jalali datepicker)
   انتخاب تاریخ با موس + فیلتر سال و ماه.
   هر input با اتریبوت data-datepicker به‌طور خودکار متصل می‌شود.
   ============================================================ */

"use strict";

(function () {
  if (!window.JalaliJS) return;

  const MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
  ];
  const WD = ["ش", "ی", "د", "س", "چ", "پ", "ج"]; /* شنبه تا جمعه */
  const pad = (n) => String(n).padStart(2, "0");
  const faDigits = (s) => String(s).replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[+d]);

  let pop = null;
  let activeInput = null;

  function ensurePop() {
    if (pop) return pop;
    pop = document.createElement("div");
    pop.className = "jdp";
    pop.innerHTML = `
      <div class="jdp-head">
        <select class="jdp-year" aria-label="سال"></select>
        <select class="jdp-month" aria-label="ماه"></select>
      </div>
      <div class="jdp-grid jdp-wd">${WD.map((w) => `<span>${w}</span>`).join("")}</div>
      <div class="jdp-grid jdp-days"></div>
      <div class="jdp-foot">
        <button type="button" class="jdp-today">امروز</button>
        <button type="button" class="jdp-clear">پاک کردن</button>
      </div>`;
    document.body.appendChild(pop);

    pop.querySelector(".jdp-year").addEventListener("change", renderDays);
    pop.querySelector(".jdp-month").addEventListener("change", renderDays);
    pop.querySelector(".jdp-days").addEventListener("click", (e) => {
      const day = e.target.closest("[data-d]");
      if (!day) return;
      const jy = +pop.querySelector(".jdp-year").value;
      const jm = +pop.querySelector(".jdp-month").value;
      setValue(`${jy}/${pad(jm)}/${pad(+day.dataset.d)}`);
    });
    pop.querySelector(".jdp-today").addEventListener("click", () => {
      const n = new Date();
      const { jy, jm, jd } = JalaliJS.g2j(n.getFullYear(), n.getMonth() + 1, n.getDate());
      setValue(`${jy}/${pad(jm)}/${pad(jd)}`);
    });
    pop.querySelector(".jdp-clear").addEventListener("click", () => setValue(""));

    document.addEventListener("mousedown", (e) => {
      if (!pop || !activeInput) return;
      if (pop.contains(e.target) || e.target === activeInput) return;
      close();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") close();
    });
    window.addEventListener("resize", close);
    return pop;
  }

  function setValue(v) {
    if (activeInput) {
      activeInput.value = v;
      activeInput.dispatchEvent(new Event("input", { bubbles: true }));
      activeInput.dispatchEvent(new Event("change", { bubbles: true }));
    }
    close();
  }

  function renderDays() {
    const jy = +pop.querySelector(".jdp-year").value;
    const jm = +pop.querySelector(".jdp-month").value;
    const len = JalaliJS.jMonthLength(jy, jm);
    const { gy, gm, gd } = JalaliJS.j2g(jy, jm, 1);
    const firstDow = (new Date(Date.UTC(gy, gm - 1, gd)).getUTCDay() + 1) % 7; /* شنبه = 0 */

    const n = new Date();
    const now = JalaliJS.g2j(n.getFullYear(), n.getMonth() + 1, n.getDate());

    let selD = 0;
    if (activeInput && activeInput.value) {
      const iso = JalaliJS.parseDateInput(activeInput.value);
      if (iso) {
        const p = JalaliJS.g2j(+iso.slice(0, 4), +iso.slice(5, 7), +iso.slice(8, 10));
        if (p.jy === jy && p.jm === jm) selD = p.jd;
      }
    }

    let html = "<span></span>".repeat(firstDow);
    for (let d = 1; d <= len; d++) {
      const nowCls = (jy === now[0] && jm === now[1] && d === now[2]) ? " jdp-now" : "";
      const selCls = d === selD ? " jdp-sel" : "";
      html += `<button type="button" data-d="${d}" class="jdp-day${nowCls}${selCls}">${faDigits(d)}</button>`;
    }
    pop.querySelector(".jdp-days").innerHTML = html;
  }

  function open(input) {
    ensurePop();
    activeInput = input;

    let jy, jm;
    const iso = input.value ? JalaliJS.parseDateInput(input.value) : null;
    if (iso) {
      const p = JalaliJS.g2j(+iso.slice(0, 4), +iso.slice(5, 7), +iso.slice(8, 10));
      jy = p.jy; jm = p.jm;
    } else {
      const n = new Date();
      const p = JalaliJS.g2j(n.getFullYear(), n.getMonth() + 1, n.getDate());
      jy = p.jy; jm = p.jm;
    }

    const y0 = jy - 40, y1 = jy + 5;
    const ySel = pop.querySelector(".jdp-year");
    ySel.innerHTML = Array.from({ length: y1 - y0 + 1 }, (_, i) => {
      const y = y0 + i;
      return `<option value="${y}">${faDigits(y)}</option>`;
    }).join("");
    ySel.value = String(jy);

    pop.querySelector(".jdp-month").innerHTML = MONTHS
      .map((m, i) => `<option value="${i + 1}">${m}</option>`).join("");
    pop.querySelector(".jdp-month").value = String(jm);

    renderDays();

    pop.classList.add("show");
    const r = input.getBoundingClientRect();
    pop.style.top = (r.bottom + window.scrollY + 6) + "px";
    let left = r.right + window.scrollX - pop.offsetWidth;
    if (left < 8) left = Math.max(8, r.left + window.scrollX);
    pop.style.left = left + "px";
  }

  function close() {
    if (pop) pop.classList.remove("show");
    activeInput = null;
  }

  window.initJalaliDatepickers = function (root = document) {
    root.querySelectorAll("input[data-datepicker]").forEach((inp) => {
      if (inp.dataset.jdpReady) return;
      inp.dataset.jdpReady = "1";
      inp.setAttribute("readonly", "");
      inp.style.cursor = "pointer";
      inp.addEventListener("click", () => open(inp));
    });
  };

  document.addEventListener("DOMContentLoaded", () => window.initJalaliDatepickers());
})();