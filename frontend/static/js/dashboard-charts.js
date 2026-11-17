/* ============================================================
   TikoTime — داشبورد: منطق sharedِ نمودارهای ماهانه
   (فعالیت ۱۲ ماه و تعداد فروش به تفکیک نوع)

   هر فراخوانی ``initChart`` یک نمودار مستقل با 상태ِ سال و
   صفحه‌بندی-jährیِ خودش می‌سازد. هر دو نمودار از همین کد رسم
   (SVG، 격، نشانگر،oltip، لودینگ، صفحه‌بندی سال) استفاده می‌کنند.
   ============================================================ */

"use strict";

/* runners: app.js قبل از این فایل لود شده است (faNum/faMoney) */
function initChart(cfg) {
  const box = document.getElementById(cfg.boxId);
  if (!box) return;
  const prevBtn = document.getElementById(cfg.prevId);
  const nextBtn = document.getElementById(cfg.nextId);
  const yearLabel = document.getElementById(cfg.labelId);
  const titleEl = document.getElementById(cfg.titleId);

  let data = [];
  try {
    data = JSON.parse(box.dataset[cfg.dataAttr] || "[]");
  } catch {
    data = [];
  }
  let curYear = data.length ? data[0].jy : null;
  let loading = false;

  /* سال جلالی جاری — دکمه‌ی «سال بعد» فقط تا همین سال فعال است */
  let currentJy = curYear;
  try {
    if (window.JalaliJS) {
      const now = new Date();
      currentJy = JalaliJS.g2j(now.getFullYear(), now.getMonth() + 1, now.getDate()).jy;
    }
  } catch (e) {
    /* JalaliJS در دسترس نیست */
  }

  const num = typeof faNum !== "undefined" ? faNum : String;
  const money =
    typeof faMoney !== "undefined"
      ? faMoney
      : ((v) => {
        const n = Math.round(Number(v) || 0);
        return num(n.toLocaleString("en-US")).replace(/,/g, "٬");
    });

  const updatePager = () => {
    if (yearLabel) yearLabel.textContent = curYear != null ? num(curYear) : "";
    if (titleEl)
      titleEl.textContent = curYear != null ? cfg.title(curYear) : cfg.emptyTitle;
    const disabled = loading || curYear == null;
    if (prevBtn) prevBtn.disabled = disabled;
    if (nextBtn) nextBtn.disabled = disabled || curYear >= currentJy;
  };

  async function loadYear(jy) {
    if (loading || jy == null) return;
    loading = true;
    updatePager();
    box.classList.add("chart-loading");
    try {
      const resp = await fetch(`${cfg.endpoint}?year=${jy}`);
      const result = await resp.json();
      if (!result.ok) throw new Error(result.error || "خطا در دریافت داده");
      data = result.months || [];
      curYear = result.year;
      renderChart();
    } catch (err) {
      console.warn(cfg.endpoint + ":", err);
    }
    box.classList.remove("chart-loading");
    loading = false;
    updatePager();
  }

  if (prevBtn) prevBtn.addEventListener("click", () => loadYear(curYear - 1));
  if (nextBtn) nextBtn.addEventListener("click", () => loadYear(curYear + 1));

  function resolve(varName, fallback) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(varName);
    return v ? v.trim() : fallback;
  }

  function renderChart() {
    if (!data.length) {
      box.innerHTML = `<div class="empty" style="padding:34px 16px"><div class="e-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="${cfg.emptyIcon || "M4 17.5 9.5 12l3.5 3.5L20 8.5"}" /></svg></div><h4>${cfg.emptyTitle}</h4><p>${cfg.emptyBody}</p></div>`;
      return;
    }

    /* بوم بزرگ‌تر — نمودار تمام‌عرض است */
    const W = 1200, H = 340, PAD_R = 18, PAD_L = 18, PAD_T = 26, PAD_B = 34;
    const plotW = W - PAD_R - PAD_L, plotH = H - PAD_T - PAD_B;
    const n = data.length;
    const actual = data.filter((m) => !m.future); /* فقط تا ماه جاری */
    const curIdx = Math.max(actual.length - 1, 0);
    const stepX = plotW / (n - 1 || 1);

    const maxVal = Math.max(
      ...actual.map((m) =>
        Math.max(...cfg.series.map((s) => Number(m[s.key] || 0)))
      ),
      1
    );
    const mag = Math.pow(10, Math.floor(Math.log10(maxVal)));
    const top = Math.ceil(maxVal / mag) * mag;

    const styles = getComputedStyle(document.documentElement);
    const colors = cfg.series.map((s) => resolve(s.colorVar, s.fallback || "#000"));
    const cRing = resolve("--surface-strong", "#ffffff");
    const cMuted = resolve("--text-3", "#8a8d98");
    const cBlue = resolve("--accent", "#0071e3");

    const xAt = (i) => PAD_L + stepX * i;
    const yAt = (v) => H - PAD_B - (top ? (v / top) * plotH : 0);

    /* منحنی نرم: تبدیل Catmull-Rom به Bézier مکعبی — بدون شکستگی تیز */
    const smoothPath = (pts) => {
      if (!pts.length) return "";
      if (pts.length === 1) return `M${pts[0].x},${pts[0].y}`;
      let d = `M${pts[0].x},${pts[0].y}`;
      for (let i = 0; i < pts.length - 1; i++) {
        const p0 = pts[i - 1] || pts[i];
        const p1 = pts[i];
        const p2 = pts[i + 1];
        const p3 = pts[i + 2] || p2;
        const c1x = p1.x + (p2.x - p0.x) / 6;
        const c1y = p1.y + (p2.y - p0.y) / 6;
        const c2x = p2.x - (p3.x - p1.x) / 6;
        const c2y = p2.y - (p3.x - p1.y) / 6;
        d += ` C${c1x.toFixed(2)},${c1y.toFixed(2)} ${c2x.toFixed(2)},${c2y.toFixed(2)} ${p2.x.toFixed(2)},${p2.y.toFixed(2)}`;
      }
      return d;
    };

    const ptsOf = (key) =>
      actual.map((m, i) => ({ x: xAt(i), y: yAt(m[key] || 0) }));
    const linePath = (key) => smoothPath(ptsOf(key));
    const areaPath = (key) => {
      const pts = ptsOf(key);
      if (!pts.length) return "";
      return (
        smoothPath(pts) +
        ` L${pts[pts.length - 1].x.toFixed(2)},${H - PAD_B} L${pts[0].x.toFixed(2)},${H - PAD_B} Z`
      );
    };

    /* گرادیان محو زیر هر خط (فقط برای 시리즈‌های area) */
    const defs = `<defs>${cfg.series
      .map((s, si) => {
        if (!s.gid || s.areaOp == null) return "";
        const c = colors[si];
        return `\n<linearGradient id="${s.gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c}" stop-opacity="${s.areaOp}"/><stop offset="1" stop-color="${c}" stop-opacity="0"/></linearGradient>`;
      })
      .join("")}
    </defs>`;

    const gridLines = [0.25, 0.5, 0.75, 1]
      .map((f) => {
        const y = H - PAD_B - plotH * f;
        return `<line x1="${PAD_L}" x2="${W - PAD_R}" y1="${y}" y2="${y}" stroke="currentColor" opacity="0.07" stroke-dasharray="3 5"/>`;
      })
      .join("");
    const baseline = `<line x1="${PAD_L}" x2="${W - PAD_R}" y1="${H - PAD_B}" y2="${H - PAD_B}" stroke="currentColor" opacity="0.16"/>`;

    /* نشانگر عمودی ماه جاری — مرز داده‌ی حقيقية و ماه‌های آینده */
    const lastX = xAt(curIdx);
    const curLine = `<line x1="${lastX}" x2="${lastX}" y1="${PAD_T}" y2="${H - PAD_B}" stroke="${cBlue}" opacity="0.25" stroke-dasharray="4 5"/>`;
    const hoverLine = `<line id="chart-cursor" x1="0" x2="0" y1="${PAD_T}" y2="${H - PAD_B}" stroke="currentColor" opacity="0.25" visibility="hidden"/>`;

    let points = "",
      labels = "",
      hits = "";
    data.forEach((m, i) => {
      const x = xAt(i);
      if (i <= curIdx) {
        cfg.series.forEach((s, si) => {
          const c = colors[si];
          points += `<circle cx="${x}" cy="${yAt(m[s.key] || 0)}" r="${s.pointRadius || 3.2}" fill="${c}" stroke="${cRing}" stroke-width="1"/>`;
        });
      }
      const isCur = i === curIdx;
      labels += `<text x="${x}" y="${H - 9}" text-anchor="middle" font-size="11" font-weight="${isCur ? 800 : 600}" fill="${isCur ? cBlue : cMuted}" opacity="${m.future ? 0.45 : 1}">${m.label}</text>`;
      if (!m.future) {
        hits += `<rect class="hit" data-i="${i}" x="${x - stepX / 2}" y="0" width="${stepX}" height="${H}" fill="transparent"/>`;
      }
    });

    /* نقطه‌ی پایانی (ماه جاری) برجسته‌تر */
    cfg.series.forEach((s, si) => {
      const c = colors[si];
      points += `<circle cx="${lastX}" cy="${yAt(actual[curIdx][s.key] || 0)}" r="${s.highlightRadius || 4.8}" fill="${c}" stroke="${cRing}" stroke-width="1.6"/>`;
    });

    box.innerHTML = `
      <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto;display:block;color:${cMuted}" role="img" aria-label="${cfg.ariaLabel(curYear)}">
        ${defs}${gridLines}${baseline}
        ${cfg.series
          .map((s, si) => {
            const c = colors[si];
            let out = "";
            if (s.gid && s.areaOp != null)
              out += `<path d="${areaPath(s.key)}" fill="url(#${s.gid})"/>`;
            out += `<path d="${linePath(s.key)}" fill="none" stroke="${c}" stroke-width="${s.width}" stroke-linecap="round" stroke-linejoin="round"/>`;
            return out;
          })
          .join("")}
        ${curLine}${hoverLine}${points}${labels}${hits}
      </svg>
      <div class="bar-tooltip"></div>`;

    const tooltip = box.querySelector(".bar-tooltip");
    const svg = box.querySelector("svg");
    const cursor = svg.querySelector("#chart-cursor");
    svg.addEventListener("mousemove", (e) => {
      const hit = e.target.closest(".hit");
      if (!hit) {
        tooltip.classList.remove("show");
        cursor.setAttribute("visibility", "hidden");
        return;
      }
      const i = +hit.dataset.i;
      const m = data[i];
      cursor.setAttribute("x1", xAt(i));
      cursor.setAttribute("x2", xAt(i));
      cursor.setAttribute("visibility", "visible");
      const rows = [
        `<div class="bt-title">${m.label} ${num(m.jy)}</div>`,
        ...cfg.tooltipRows(m, i, { num, money, colors }),
      ];
      tooltip.innerHTML = rows.join("");
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
}