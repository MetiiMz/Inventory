/* ============================================================
   TikoTime — نمودارهای خطی داشبورد (موتور مشترک)

   یک تابع ساخت‌کننده‌ی کوچک که هر دو نمودار ۱۲ ماهه‌ی نمایه را
   رسم می‌کند: «فعالیت ماهانه» (خرید/فروش/سود) و «تعداد فروش به
   تفکیک نوع» (حضوری/آنلاین/اعتباری). رفتارها یکی است: SVG، گرید،
   برچسب فارسی ماه‌ها، نشانگر hover + tooltip، حالت بارگذاری، تم
   روشن/تاریک و صفحه‌بندی سال با state مستقل برای هر نمودار.

   پارامترهای initChart(cfg):
     boxId / prevBtnId / nextBtnId / yearLabelId / titleId — شناسه‌ها
     dataKey       — نام کلید داده‌ی رندر اولیه در dataset جعبه (data-*)
                     بدون پیشوند data-؛ مثلاً \"monthly\" برای data-monthly
     endpoint      — مسیر API برای تغییر سال
     gidPrefix     — پیشوند یکتای id گرادیان‌ها (دو نمودار در یک صفحه)
     series        — [{ key, colorVar, fallbackColor, width, gid, areaOp }]
     tooltip(m, s) — ردیف‌های tooltip؛ m ماه، s سری‌های رنگ‌حل‌شده
     title(y)      — متن عنوان با سال جاری
     aria(yFa)     — aria-label نمودار
     fallbackTitle / emptyTitle / emptyText — عنوان و حالت خالی
   ============================================================ */

"use strict";

/* منحنی نرم: مکعبی-مونوتون (PCHIP / فریتش-کارلسون) — منحنی از هر نقطه عبور می‌کند،
   هرگز سرریز نمی‌کند (نقاط کنترل در بازه‌ی [minY, maxY] قید می‌شوند، بنابراین هرگز
   زیر خط پایه یا بالای ناحیه‌ی رسم نمی‌رود) و در نقاطِ ekstremum مماس مسطح است. */
function smoothChartPath(pts, minY, maxY) {
  if (!pts.length) return "";
  if (pts.length === 1) return `M${pts[0].x},${pts[0].y}`;
  const n = pts.length;
  const clampY = (y) => Math.min(maxY, Math.max(minY, y));
  const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
  /* شیب‌های بین نقاط متوالی */
  const d = new Array(n - 1);
  for (let i = 0; i < n - 1; i++) d[i] = (ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]);
  /* مماس‌های هر نقطه (مونوتون) */
  const m = new Array(n);
  m[0] = d[0];
  m[n - 1] = d[n - 2];
  for (let i = 1; i < n - 1; i++) {
    if (d[i - 1] * d[i] <= 0) {
      m[i] = 0; // extremum — flat tangent
    } else {
      const h0 = xs[i] - xs[i - 1], h1 = xs[i + 1] - xs[i];
      m[i] = (h0 + h1) / (h0 / d[i] + h1 / d[i - 1]); // harmonic-ish mean
      const lim = 3 * Math.min(Math.abs(d[i - 1]), Math.abs(d[i]));
      if (Math.abs(m[i]) > lim) m[i] = Math.sign(m[i]) * lim;
    }
  }
  let out = `M${xs[0].toFixed(2)},${clampY(ys[0]).toFixed(2)}`;
  for (let i = 0; i < n - 1; i++) {
    const h = xs[i + 1] - xs[i];
    const c1x = xs[i] + h / 3, c1y = clampY(ys[i] + (m[i] * h) / 3);
    const c2x = xs[i + 1] - h / 3, c2y = clampY(ys[i + 1] - (m[i + 1] * h) / 3);
    out += ` C${c1x.toFixed(2)},${c1y.toFixed(2)} ${c2x.toFixed(2)},${c2y.toFixed(2)} ${xs[i + 1].toFixed(2)},${clampY(ys[i + 1]).toFixed(2)}`;
  }
  return out;
}

/* «خوب»‌ترین سقف برای ارتفاع نمودار: کوچک‌ترین مقدار ازible گام‌ها ≥ maxCount
  تا تبلدهای کم‌حجم انگشت‌نشده، و رأس‌ها به لبه‌ی نمودارChalk نمی‌نشیند. */
function niceMax(v) {
  const steps = [4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200, 300, 400, 500];
  for (const s of steps) if (s >= v) return s;
  const mag = Math.pow(10, Math.floor(Math.log10(v)));
  return Math.ceil(v / mag) * mag;
}

function initChart(cfg) {
  const box = document.getElementById(cfg.boxId);
  if (!box) return null;
  const prevBtn = document.getElementById(cfg.prevBtnId);
  const nextBtn = document.getElementById(cfg.nextBtnId);
  const yearLabel = document.getElementById(cfg.yearLabelId);
  const titleEl = document.getElementById(cfg.titleId);

  let monthsData = [];
  try { monthsData = JSON.parse(box.dataset[cfg.dataKey] || "[]"); } catch { monthsData = []; }
  let curYear = monthsData.length ? monthsData[0].jy : null;
  let loading = false;

  /* سال جلالی جاری — فلش «سال بعد» فقط تا این سال فعال است */
  let currentJy = curYear;
  try {
    if (window.JalaliJS) {
      const now = new Date();
      currentJy = JalaliJS.g2j(now.getFullYear(), now.getMonth() + 1, now.getDate()).jy;
    }
  } catch (e) { /* JalaliJS در دسترس نیست */ }

  const updatePager = () => {
    if (yearLabel) yearLabel.textContent = curYear != null ? faNum(curYear) : "";
    if (titleEl) titleEl.textContent = curYear != null ? cfg.title(curYear) : cfg.fallbackTitle;
    if (prevBtn) prevBtn.disabled = loading || curYear == null;
    if (nextBtn) nextBtn.disabled = loading || curYear == null || curYear >= currentJy;
  };

  async function loadYear(jy) {
    if (loading || jy == null) return;
    loading = true;
    updatePager();
    box.classList.add("chart-loading");
    try {
      const resp = await fetch(`${cfg.endpoint}?year=${jy}`);
      const data = await resp.json();
      if (!data.ok) throw new Error(data.error || "خطا در دریافت داده");
      monthsData = data.months || [];
      curYear = data.year;
      renderChart();
    } catch (err) {
      console.warn(`${cfg.endpoint}:`, err);
    }
    box.classList.remove("chart-loading");
    loading = false;
    updatePager();
  }

  if (prevBtn) prevBtn.addEventListener("click", () => loadYear(curYear - 1));
  if (nextBtn) nextBtn.addEventListener("click", () => loadYear(curYear + 1));

  function renderChart() {
    if (!monthsData.length) {
      box.innerHTML = `<div class="empty" style="padding:34px 16px"><div class="e-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M4 17.5 9.5 12l3.5 3.5L20 8.5"/></svg></div><h4>${cfg.emptyTitle}</h4><p>${cfg.emptyText}</p></div>`;
      return;
    }

    /* بوم بزرگ‌تر — نمودار تمام‌عرض است */
    const W = 1200, H = 340, PAD_R = 18, PAD_L = 18, PAD_T = 26, PAD_B = 34;
    const plotW = W - PAD_R - PAD_L, plotH = H - PAD_T - PAD_B;
    const n = monthsData.length;
    const actual = monthsData.filter(m => !m.future); /* فقط تا ماه جاری */
    const curIdx = Math.max(actual.length - 1, 0);
    const lastActual = actual[curIdx] || {};
    const stepX = plotW / (n - 1 || 1);
    const maxVal = Math.max(
      ...actual.map(m => Math.max(...cfg.series.map(s => m[s.key] || 0))), 1);
    const mag = Math.pow(10, Math.floor(Math.log10(maxVal)));
    const top = cfg.niceMax ? niceMax(maxVal) : Math.ceil(maxVal / mag) * mag;

    const styles = getComputedStyle(document.documentElement);
    const cssVar = (name, fallback) =>
      (styles.getPropertyValue(name).trim() || fallback);
    const cMuted = cssVar("--text-3", "#86868b");
    const cRing = cssVar("--surface-strong", "#ffffff");
    const cAccent = cssVar("--accent", "#0070e2");
    const resolved = cfg.series.map(s => ({
      ...s, color: cssVar(s.colorVar, s.fallbackColor),
    }));

    const xAt = (i) => PAD_L + stepX * i;
    const yAt = (v) => H - PAD_B - (top ? (v / top) * plotH : 0);

    const ptsOf = (key) => actual.map((m, i) => ({ x: xAt(i), y: yAt(m[key] || 0) }));
    const linePath = (key) => smoothChartPath(ptsOf(key), PAD_T, H - PAD_B);
    const areaPath = (key) => {
      const pts = ptsOf(key);
      if (!pts.length) return "";
      return smoothChartPath(pts, PAD_T, H - PAD_B) +
        ` L${pts[pts.length - 1].x.toFixed(2)},${H - PAD_B} L${pts[0].x.toFixed(2)},${H - PAD_B} Z`;
    };

    /* گرادیان محو زیر هر خط */
    const defs = `<defs>${resolved.map(s => `\n      <linearGradient id="${cfg.gidPrefix}-${s.gid}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="${s.color}" stop-opacity="${s.areaOp}"/>
        <stop offset="1" stop-color="${s.color}" stop-opacity="0"/>
      </linearGradient>`).join("")}
    </defs>`;

    let points = "", labels = "", hits = "";
    monthsData.forEach((m, i) => {
      const x = xAt(i);
      if (i <= curIdx) {
        resolved.forEach(s => {
          points += `<circle cx="${x}" cy="${yAt(m[s.key] || 0)}" r="3.2" fill="${s.color}" stroke="${cRing}" stroke-width="1"/>`;
        });
      }
      const isCur = i === curIdx;
      labels += `<text x="${x}" y="${H - 9}" text-anchor="middle" font-size="11" font-weight="${isCur ? 800 : 600}" fill="${isCur ? cAccent : cMuted}" opacity="${m.future ? 0.45 : 1}">${m.label}</text>`;
      if (!m.future) {
        hits += `<rect class="hit" data-i="${i}" x="${x - stepX / 2}" y="0" width="${stepX}" height="${H}" fill="transparent"/>`;
      }
    });

    /* نقطه‌ی پایانی (ماه جاری) برجسته‌تر */
    const lastX = xAt(curIdx);
    resolved.forEach(s => {
      points += `<circle cx="${lastX}" cy="${yAt(lastActual[s.key] || 0)}" r="4.8" fill="${s.color}" stroke="${cRing}" stroke-width="1.6"/>`;
    });

    const gridLines = [0.25, 0.5, 0.75, 1].map(f => {
      const y = H - PAD_B - plotH * f;
      return `<line x1="${PAD_L}" x2="${W - PAD_R}" y1="${y}" y2="${y}" stroke="currentColor" opacity="0.07" stroke-dasharray="3 5"/>`;
    }).join("");
    const baseline = `<line x1="${PAD_L}" x2="${W - PAD_R}" y1="${H - PAD_B}" y2="${H - PAD_B}" stroke="currentColor" opacity="0.16"/>`;

    /* نشانگر عمودی ماه جاری — مرز داده‌ی واقعی و ماه‌های آینده */
    const curLine = `<line x1="${lastX}" x2="${lastX}" y1="${PAD_T}" y2="${H - PAD_B}" stroke="${cAccent}" opacity="0.25" stroke-dasharray="4 5"/>`;
    const cursorId = `${cfg.boxId}-cursor`;
    const hoverLine = `<line id="${cursorId}" x1="0" x2="0" y1="${PAD_T}" y2="${H - PAD_B}" stroke="currentColor" opacity="0.25" visibility="hidden"/>`;

    box.innerHTML = `
      <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto;display:block;color:${cMuted}" role="img" aria-label="${cfg.aria(faNum(curYear))}">
        ${defs}${gridLines}${baseline}
        ${resolved.map(s => `<path d="${areaPath(s.key)}" fill="url(#${cfg.gidPrefix}-${s.gid})"/>`).join("")}
        ${resolved.map(s => `<path d="${linePath(s.key)}" fill="none" stroke="${s.color}" stroke-width="${s.width}" stroke-linecap="round" stroke-linejoin="round"/>`).join("")}
        ${curLine}${hoverLine}${points}${labels}${hits}
      </svg>
      <div class="bar-tooltip"></div>`;

    const tooltip = box.querySelector(".bar-tooltip");
    const svg = box.querySelector("svg");
    const cursor = svg.querySelector(`#${cursorId}`);
    svg.addEventListener("mousemove", (e) => {
      const hit = e.target.closest(".hit");
      if (!hit) { tooltip.classList.remove("show"); cursor.setAttribute("visibility", "hidden"); return; }
      const i = +hit.dataset.i;
      const m = monthsData[i];
      cursor.setAttribute("x1", xAt(i));
      cursor.setAttribute("x2", xAt(i));
      cursor.setAttribute("visibility", "visible");
      tooltip.innerHTML = cfg.tooltip(m, resolved).join("");
      const rect = box.getBoundingClientRect();
      let x = e.clientX - rect.left;
      x = Math.max(90, Math.min(rect.width - 90, x));
      const y = e.clientY - rect.top;
      tooltip.style.left = x + "px";
      tooltip.style.top = Math.max(80, y) + "px";
      tooltip.classList.add("show");
    });
    svg.addEventListener("mouseleave", () => {
      tooltip.classList.remove("show");
      cursor.setAttribute("visibility", "hidden");
    });
  }

  renderChart();
  updatePager();
  return { loadYear, renderChart };
}
