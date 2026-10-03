/* ============================================================
   صفحه‌ی تقویم — ماه شمسی، رویدادهای خرید/فروش/تعمیر،
   جزئیات با کلیک روی هر رویداد
   ============================================================ */

"use strict";

const MONTH_NAMES_FA = ["فروردین","اردیبهشت","خرداد","تیر","مرداد","شهریور","مهر","آبان","آذر","دی","بهمن","اسفند"];

let currentJy = null;
let currentJm = null;
let selectedIso = null;
let lastDayData = null;

async function loadMonth(jy, jm) {
  currentJy = jy; currentJm = jm;
  $("#cal-month-name").textContent = MONTH_NAMES_FA[jm - 1];
  $("#cal-year").textContent = faNum(jy);

  const data = await api(`/api/calendar?jy=${jy}&jm=${jm}`);
  const cellsEl = $("#cal-cells");
  cellsEl.innerHTML = "";

  data.cells.forEach((cell) => {
    if (!cell) {
      const empty = document.createElement("div");
      empty.className = "day-cell";
      empty.disabled = true;
      empty.style.visibility = "hidden";
      cellsEl.appendChild(empty);
      return;
    }
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "day-cell" + (cell.is_today ? " today" : "") +
      (cell.iso === selectedIso ? " selected" : "");
    btn.dataset.iso = cell.iso;

    const hasP = cell.purchases.length > 0;
    const hasS = cell.sales.length > 0;
    const hasRI = cell.repairs_in.length > 0;
    const hasRO = cell.repairs_out.length > 0;
    let badges = "";
    if (hasP) badges += `<span class="d-badge buy">خرید<span class="cnt">${faNum(cell.purchases.length)}</span></span>`;
    if (hasS) badges += `<span class="d-badge sell">فروش<span class="cnt">${faNum(cell.sales.length)}</span></span>`;
    if (hasRI) badges += `<span class="d-badge rep-in">تعمیر<span class="cnt">${faNum(cell.repairs_in.length)}</span></span>`;
    if (hasRO) badges += `<span class="d-badge rep-out">بازگشت<span class="cnt">${faNum(cell.repairs_out.length)}</span></span>`;

    btn.innerHTML = `
      <span class="day-num">${faNum(cell.day)}</span>
      <div class="d-badges">${badges}</div>`;

    btn.addEventListener("click", () => selectDay(cell.iso, btn));
    cellsEl.appendChild(btn);
  });

  if (selectedIso) {
    const btn = cellsEl.querySelector(`[data-iso="${selectedIso}"]`);
    if (btn) btn.classList.add("selected");
  }
}

function switchMonth(delta) {
  let jm = currentJm + delta;
  let jy = currentJy;
  if (jm < 1) { jm = 12; jy -= 1; }
  if (jm > 12) { jm = 1; jy += 1; }
  selectedIso = null;
  lastDayData = null;
  loadMonth(jy, jm);
  renderEmptyPanel();
}

async function selectDay(iso, btn) {
  selectedIso = iso;
  $$("#cal-cells .day-cell").forEach((c) => c.classList.remove("selected"));
  if (btn) btn.classList.add("selected");

  $("#panel-title").textContent = "در حال بارگذاری…";
  $("#panel-sub").textContent = "";
  try {
    const day = await api(`/api/calendar/day?date=${encodeURIComponent(iso)}`);
    lastDayData = day;
    renderDayPanel(day);
  } catch (err) {
    $("#panel-title").textContent = "خطا";
    $("#panel-sub").textContent = err.message;
  }
}

/* ------------------------------------------------ کارت رویداد قابل کلیک */

function eventItem(e, kind) {
  const cfg = {
    buy:    { color: "blue",  tag: "خرید",  price: e.purchase_price_display || e.total_value_display || e.price_display || "" },
    sell:   { color: "green", tag: "فروش",  price: e.final_price_display || e.sale_price_display || e.price_display || "" },
    rep_in: { color: "amber", tag: "دریافت برای تعمیر", price: "" },
    rep_out:{ color: "gray",  tag: "بازگشت به مشتری",   price: "" },
  }[kind];

  const payload = esc(JSON.stringify({ kind, id: e.id }));
  const name = e.name || e.product_name || e.watch_name || "";
  const isRep = kind === "rep_in" || kind === "rep_out";
  const sub = isRep
    ? [e.customer_name || e.customer || "", e.watch_code ? "کد: " + e.watch_code : ""].filter(Boolean).join(" — ")
    : (e.reference ? "رفرنس: " + e.reference : "");

  return `
    <button type="button" class="event-item ev-click" data-payload="${payload}" style="width:100%;text-align:right;border:1px solid var(--hairline);cursor:pointer;font-family:inherit">
      ${(e.image || e.product_image)
        ? `<img class="thumb" style="width:38px;height:38px;border-radius:10px" src="/data/images/${encodeURIComponent(e.image || e.product_image)}" alt="">`
        : `<span class="thumb" style="width:38px;height:38px;border-radius:10px"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="6.4"/><path d="M12 9.2V12l2.1 1.5"/></svg></span>`}
      <div class="li-main">
        <div class="e-name">${esc(name)}</div>
        ${sub ? `<div class="e-meta">${esc(sub)}</div>` : ""}
      </div>
      ${cfg.price ? `<div class="e-price ${cfg.color === "gray" ? "" : cfg.color}">${cfg.price}</div>` : ""}
    </button>`;
}

/* ------------------------------------------------ مودال جزئیات رویداد */

function showEventDetail(kind, id) {
  if (!lastDayData) return;
  let d = null;
  if (kind === "buy") d = lastDayData.purchases.find((x) => x.id === id);
  if (kind === "sell") d = lastDayData.sales.find((x) => x.id === id);
  if (kind === "rep_in") d = lastDayData.repairs_in.find((x) => x.id === id);
  if (kind === "rep_out") d = lastDayData.repairs_out.find((x) => x.id === id);
  if (!d) { toast("جزئیات یافت نشد", "error"); return; }

  const title = {
    buy: "جزئیات خرید",
    sell: "جزئیات فروش",
    rep_in: "ساعت تعمیری — دریافت",
    rep_out: "ساعت تعمیری — بازگشت",
  }[kind];

  let rows = "";
  const add = (k, v) => { if (v && String(v).trim()) rows += `<div class="kv"><span class="k">${k}</span><span class="v">${v}</span></div>`; };

  /* تصویر و نام ساعت بالای جزئیات */
  const img = d.product_image || d.image || "";
  const imgName = kind === "sell" ? (d.product_name || "محصول حذف‌شده")
    : kind === "buy" ? d.name : d.watch_name;
  rows += `<div class="prod-cell" style="margin-bottom:12px">
    ${img
      ? `<img class="thumb" style="width:52px;height:52px;border-radius:12px" src="/data/images/${encodeURIComponent(img)}" alt="">`
      : `<span class="thumb" style="width:52px;height:52px;border-radius:12px"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="6.4"/><path d="M12 9.2V12l2.1 1.5"/></svg></span>`}
    <div><div class="p-name">${esc(imgName)}</div></div>
  </div>`;

  if (kind === "buy") {
    add("نام ساعت", esc(d.name));
    add("کد دفتر فروشگاه", `<span class="code-pill">${esc(d.office_code)}</span>`);
    add("کد انبار سایت", `<span class="code-pill">${esc(d.website_code)}</span>`);
    add("برند", esc(d.brand));
    add("رفرنس", esc(d.reference));
    add("قیمت خرید", d.purchase_price_display ? d.purchase_price_display + " تومان" : "");
    add("نوع خرید", d.purchase_type_fa);
    add("تأمین‌کننده", esc(d.supplier));
    add("وضعیت", d.is_available ? '<span class="badge green plain">موجود</span>' : '<span class="badge red plain">ناموجود</span>');
    add("یادداشت", esc(d.notes));
  } else if (kind === "sell") {
    add("کد فاکتور", d.invoice_code ? `<span class="code-pill">${esc(d.invoice_code)}</span>` : "");
    add("کد دفتر فروشگاه", d.office_code ? `<span class="code-pill">${esc(d.office_code)}</span>` : "");
    add("کد انبار سایت", d.website_code ? `<span class="code-pill">${esc(d.website_code)}</span>` : "");
    add("برند", esc(d.brand));
    add("رفرنس", esc(d.reference));
    add("قیمت فروش ساعت", d.sale_price_display + " تومان");
    add("قیمت نهایی فروش", d.final_price_display + " تومان");
    add("سود این فروش", `<span style="color:var(--green)">${d.profit_display} تومان</span>`);
    add("خریدار", esc(d.customer));
    add("شماره تماس خریدار", d.customer_phone_fa || "");
    add("نوع فروش", d.sale_type_fa || "");
    add("روش پرداخت", d.payment_type_fa || "");
    if (d.payment_type === "deposit") {
      add("وضعیت تسویه", d.is_settled
        ? '<span class="badge green plain">تسویه شده</span>'
        : '<span class="badge amber plain">در انتظار تسویه</span>');
      add("مبلغ پرداخت‌شده", d.paid_total_display + " تومان");
    } else {
      add("ریز پرداخت", d.paid_breakdown_fa || "");
    }
    add("تاریخ فروش", d.sale_date_fa);
    add("یادداشت", esc(d.notes));
  } else {
    add("نام ساعت", esc(d.watch_name));
    add("کد ساعت", esc(d.watch_code));
    add("ایراد", esc(d.issue));
    add("مشتری", `${esc(d.customer_name)}${d.customer_phone ? " — " + faNum(d.customer_phone) : ""}`);
    add("تاریخ دریافت", d.delivery_date_fa);
    add("تاریخ بازگشت", d.return_date_fa);
    add("گارانتی", d.is_warranty_fa);
    add("وضعیت", d.status_fa);
    add("هزینه تعمیر", d.repair_price ? d.repair_price_display + " تومان" : "");
    add("یادداشت", esc(d.notes));
  }

  $("#event-detail-title").textContent = title;
  $("#event-detail-body").innerHTML = rows ||
    '<p class="li-sub" style="margin:0">جزئیاتی ثبت نشده است</p>';
  const link = $("#event-detail-link");
  if (kind === "buy") { link.href = "/products"; link.classList.remove("hidden"); link.textContent = "مشاهده در انبار"; }
  else if (kind === "sell") { link.href = `/sold?highlight=${d.id}`; link.classList.remove("hidden"); link.textContent = "مشاهده در فروش‌ها"; }
  else { link.href = "/repairs"; link.classList.remove("hidden"); link.textContent = "مشاهده در تعمیرات"; }
  openModal("modal-event-detail");
}

/* ------------------------------------------------ پنل روز */

function renderDayPanel(day) {
  lastDayData = day;
  $("#panel-title").textContent = day.date_fa;
  const pc = day.purchases.length, sc = day.sales.length;
  const ric = day.repairs_in.length, roc = day.repairs_out.length;
  const total = pc + sc + ric + roc;
  $("#panel-count").classList.remove("hidden");
  $("#panel-count").textContent = `${faNum(total)} رخداد`;
  $("#panel-sub").textContent = total
    ? "روی هر مورد کلیک کنید تا جزئیات کامل را ببینید"
    : "در این روز فعالیتی ثبت نشده است";

  let html = "";

  if (pc) {
    const buyTotal = day.purchases.reduce((s, p) => s + (Number(p.purchase_price) || Number(p.total_value) || 0), 0);
    html += `<div class="event-group">
      <div class="event-group-title"><span class="g-dot" style="background:var(--accent)"></span>خریدها (${faNum(pc)})</div>
      ${day.purchases.map((p) => eventItem(p, "buy")).join("")}
      <div class="kv mt-8"><span class="k">جمع مبلغ خرید</span><span class="v" style="color:var(--accent)">${faMoney(buyTotal)} تومان</span></div>
    </div>`;
  }
  if (sc) {
    const sellTotal = day.sales.reduce((s, x) => s + (Number(x.final_price) || Number(x.sale_price) || 0), 0);
    html += `<div class="event-group">
      <div class="event-group-title"><span class="g-dot" style="background:var(--green)"></span>فروش‌ها (${faNum(sc)})</div>
      ${day.sales.map((x) => eventItem(x, "sell")).join("")}
      <div class="kv mt-8"><span class="k">جمع مبلغ فروش</span><span class="v" style="color:var(--green)">${faMoney(sellTotal)} تومان</span></div>
    </div>`;
  }
  if (ric) {
    html += `<div class="event-group">
      <div class="event-group-title"><span class="g-dot" style="background:var(--amber)"></span>دریافت برای تعمیر (${faNum(ric)})</div>
      ${day.repairs_in.map((r) => eventItem(r, "rep_in")).join("")}
    </div>`;
  }
  if (roc) {
    html += `<div class="event-group">
      <div class="event-group-title"><span class="g-dot" style="background:var(--text-3)"></span>بازگشت به مشتری (${faNum(roc)})</div>
      ${day.repairs_out.map((r) => eventItem(r, "rep_out")).join("")}
    </div>`;
  }

  $("#panel-content").innerHTML = html || `
    <div class="empty" style="padding:34px 12px">
      <div class="e-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="8.6"/></svg></div>
      <h4>رخدادی ثبت نشده</h4>
      <p>این روز آرام بوده است</p>
    </div>`;
}

function renderEmptyPanel() {
  $("#panel-title").textContent = "یک روز را انتخاب کنید";
  $("#panel-count").classList.add("hidden");
  $("#panel-sub").textContent = "برای نمایش جزئیات، از تقویم روز مورد نظر را بزنید";
  $("#panel-content").innerHTML = `
    <div class="empty" style="padding:34px 12px">
      <div class="e-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3.5" y="5" width="17" height="16" rx="3"/><path d="M8 3v4M16 3v4M3.5 10.2h17"/></svg></div>
      <h4>هنوز روزی انتخاب نشده</h4>
      <p>خرید آبی، فروش سبز، تعمیر نارنجی و بازگشت خاکستری است</p>
    </div>`;
}

document.addEventListener("click", (e) => {
  const ev = e.target.closest(".ev-click");
  if (!ev) return;
  try {
    const { kind, id } = JSON.parse(ev.dataset.payload);
    showEventDetail(kind, id);
  } catch { /* نادیده */ }
});

document.addEventListener("DOMContentLoaded", () => {
  const now = new Date();
  const { jy, jm } = JalaliJS.g2j(now.getFullYear(), now.getMonth() + 1, now.getDate());
  loadMonth(jy, jm);

  $("#cal-prev").addEventListener("click", () => switchMonth(-1));
  $("#cal-next").addEventListener("click", () => switchMonth(1));
  $("#cal-today").addEventListener("click", () => {
    const n = new Date();
    const t = JalaliJS.g2j(n.getFullYear(), n.getMonth() + 1, n.getDate());
    selectedIso = null;
    lastDayData = null;
    renderEmptyPanel();
    loadMonth(t.jy, t.jm);
  });
});

/* ------------------------------------------------ نوسازی خودکار داده‌ها
   حذفِ فروش (یا هر تغییر دیگر) ممکن است در صفحه/تب/کامپیوتر دیگری اتفاق
   افتاده باشد. تقویم نباید داده‌ی کهنه نشان دهد؛ پس هر بار که صفحه دوباره
   دیده می‌شود (بازگشت از bfcache مرورگر یا فعال‌شدن تب)، ماه و روز انتخابی
   دوباره از سرور خوانده می‌شوند. */

async function refreshCalendar() {
  if (!currentJy || !currentJm) return;
  try {
    await loadMonth(currentJy, currentJm);
    if (selectedIso) {
      const day = await api(`/api/calendar/day?date=${encodeURIComponent(selectedIso)}`);
      lastDayData = day;
      renderDayPanel(day);
    }
  } catch { /* خطای شبکه را بی‌صدا رد می‌کنیم؛ داده‌ی فعلی دست‌نخورده می‌ماند */ }
}

// بازگشت به صفحه با دکمه‌ی Back/Forward مرورگر — داده‌ی کش‌شده کهنه است
window.addEventListener("pageshow", (e) => {
  if (e.persisted) refreshCalendar();
});

// فعال‌شدن دوباره‌ی تب — همگام‌سازی با تغییرات تب‌ها و کامپیوترهای دیگر
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") refreshCalendar();
});
