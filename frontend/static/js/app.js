/* ============================================================
   TikoTime — اسکریپت مشترک (تم، API، مودال، توست، ابزار تاریخ)
   ============================================================ */

"use strict";

/* ------------------------------------------------ ابزارهای پایه */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const faNum = (v) => String(v).replace(/\d/g, (d) => FA_DIGITS[+d]);
/* هر دو نوع رقم فارسی: U+06F0–U+06F9 (۲) و U+0660–U+0669 (٢ — کیبورد عربی/برخی فارسی) */
const toEnDigits = (s) =>
  String(s ?? "")
    .replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x06F0))
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660));

function faMoney(v) {
  const n = Math.round(Number(v) || 0);
  return faNum(n.toLocaleString("en-US")).replace(/,/g, "٬");
}
const faMoneyUnit = (v) => `${faMoney(v)} تومان`;

/* تبدیل تاریخ میلادی ISO به شمسی — از JalaliJS (static/js/jalali.js) */
function jFromIso(iso) {
  return window.JalaliJS ? JalaliJS.isoToJalaliStr(iso) : iso;
}

async function api(url, options = {}) {
  const opts = { headers: {}, ...options };
  if (opts.body && !(opts.body instanceof FormData)) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  const res = await fetch(url, opts);
  let data = null;
  try { data = await res.json(); } catch { /* پاسخ غیر JSON */ }
  if (!res.ok) {
    const msg = (data && data.error) || `خطای سرور (${res.status})`;
    throw new Error(msg);
  }
  return data;
}

/* ------------------------------------------------ توست */

function toast(message, type = "success") {
  let zone = $("#toast-zone");
  if (!zone) {
    zone = document.createElement("div");
    zone.id = "toast-zone";
    document.body.appendChild(zone);
  }
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  const icons = {
    success: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m8.5 12.2 2.4 2.4 4.8-5"/></svg>',
    error: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.2M12 16.4h.01"/></svg>',
    info: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5.4M12 7.6h.01"/></svg>',
  };
  el.innerHTML = `<span class="t-ic">${icons[type] || icons.info}</span><span>${esc(message)}</span>`;
  zone.appendChild(el);
  setTimeout(() => {
    el.classList.add("out");
    setTimeout(() => el.remove(), 260);
  }, type === "error" ? 5200 : 3200);
}

window.addEventListener("unhandledrejection", (e) => {
  if (e.reason && e.reason.message && !e.reason.handled) {
    toast(e.reason.message, "error");
  }
});

/* ------------------------------------------------ تم روشن/تاریک */

const THEME_KEY = "satchour-theme";

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = theme === "dark" ? "#000000" : "#ffffff";
  $$(".theme-toggle").forEach((btn) => {
    btn.setAttribute("aria-checked", theme === "dark" ? "true" : "false");
  });
}

function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  const initial = saved || "light";
  applyTheme(initial);
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".theme-toggle");
    if (!btn) return;
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    applyTheme(next);
    localStorage.setItem(THEME_KEY, next);
  });
}

/* ------------------------------------------------ مودال */

function openModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.classList.add("open");
  document.body.style.overflow = "hidden";
  const first = m.querySelector("input, select, textarea, button");
  setTimeout(() => { if (first && first.focus) first.focus(); }, 60);
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.classList.remove("open");
  const anyOpen = $$(".modal-backdrop.open").length > 0;
  if (!anyOpen) document.body.style.overflow = "";
}

document.addEventListener("click", (e) => {
  const closer = e.target.closest("[data-close-modal]");
  if (closer) {
    closeModal(closer.dataset.closeModal);
    return;
  }
  if (e.target.classList && e.target.classList.contains("modal-backdrop")) {
    closeModal(e.target.id);
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") $$(".modal-backdrop.open").forEach((m) => closeModal(m.id));
});

/* ------------------------------------------------ منوی کشویی */

document.addEventListener("click", (e) => {
  const trigger = e.target.closest(".menu > .btn, .menu > button");
  const menu = trigger ? trigger.closest(".menu") : null;
  $$(".menu.open").forEach((m) => { if (m !== menu) m.classList.remove("open"); });
  if (menu) {
    e.stopPropagation();
    menu.classList.toggle("open");
    return;
  }
  if (!e.target.closest(".menu-list")) {
    $$(".menu.open").forEach((m) => m.classList.remove("open"));
  }
});

/* ------------------------------------------------ سوییچها */

document.addEventListener("click", (e) => {
  const sw = e.target.closest(".switch");
  if (!sw) return;
  sw.classList.toggle("on");
  sw.dispatchEvent(new CustomEvent("switchchange", {
    bubbles: true,
    detail: { on: sw.classList.contains("on") },
  }));
});

/* ------------------------------------------------ آپلود تصویر */

function setupImageUpload(wrapEl) {
  const input = wrapEl.querySelector('input[type="file"]');
  const hidden = wrapEl.querySelector('input[type="hidden"]');
  const preview = wrapEl.querySelector(".img-preview");
  const removeBtn = wrapEl.querySelector(".iu-remove");
  const pickBtn = wrapEl.querySelector(".iu-pick");
  let currentPath = hidden.value || "";

  function render() {
    if (currentPath) {
      preview.innerHTML = "";
      preview.classList.remove("placeholder");
      preview.src = `/data/images/${encodeURIComponent(currentPath)}`;
    } else {
      preview.removeAttribute("src");
      preview.classList.add("placeholder");
      preview.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="1.8"/><path d="m5 19 5.2-5.4a1.6 1.6 0 0 1 2.3 0L19 19"/></svg>';
    }
    if (removeBtn) removeBtn.classList.toggle("hidden", !currentPath);
  }

  async function uploadFile(file) {
    if (!file.type.startsWith("image/")) {
      toast("فقط فایل تصویری پذیرفته می‌شود", "error");
      return;
    }
    if (file.size > 12 * 1024 * 1024) {
      toast("حجم تصویر باید کمتر از ۱۲ مگابایت باشد", "error");
      return;
    }
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await api("/api/upload", { method: "POST", body: fd });
      currentPath = res.path;
      hidden.value = currentPath;
      render();
      toast("تصویر بارگذاری شد");
    } catch (err) {
      toast(err.message, "error");
    }
  }

  if (pickBtn) pickBtn.addEventListener("click", (e) => { e.preventDefault(); input.click(); });
  preview.addEventListener("click", () => input.click());
  input.addEventListener("change", () => {
    if (input.files[0]) uploadFile(input.files[0]);
    input.value = "";
  });
  wrapEl.addEventListener("dragover", (e) => { e.preventDefault(); wrapEl.classList.add("dragover"); });
  wrapEl.addEventListener("dragleave", () => wrapEl.classList.remove("dragover"));
  wrapEl.addEventListener("drop", (e) => {
    e.preventDefault();
    wrapEl.classList.remove("dragover");
    if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
  });
  if (removeBtn) {
    removeBtn.addEventListener("click", (e) => {
      e.preventDefault();
      currentPath = "";
      hidden.value = "";
      render();
    });
  }
  render();
}

/* .img-upload با data-manual از اتصال خودکار مستثناست (مثل آیکون سایت که هندلر اختصاصی دارد) */
$$(".img-upload:not([data-manual])").forEach(setupImageUpload);
document.addEventListener("modal:opened", (e) => {
  $$(".img-upload:not([data-manual]):not([data-ready])", e.detail?.root || document).forEach((el) => {
    el.dataset.ready = "1";
    setupImageUpload(el);
  });
});

/* ------------------------------------------------ انتخاب برند (datalist) */

async function fillBrandDatalist(selectEl) {
  try {
    const data = await api("/api/brands");
    selectEl.innerHTML = "";
    data.brands.forEach((b) => {
      const opt = document.createElement("option");
      opt.value = b;
      selectEl.appendChild(opt);
    });
  } catch { /* بی‌خیال */ }
}

/* ------------------------------------------------ تاریخ پیش‌فرض فرم‌ها */

/* ------------------------------------------------ ورودی‌های مبلغ با جداکننده‌ی هزارگان
   در تایپ زنده سه‌رقمی جدا می‌شود؛ هنگام ارسال فرم فقط ارقام انگلیسی می‌ماند. */

function moneyIn(value) {
  return value ? faNum(Number(value).toLocaleString("en-US")).replace(/,/g, "٬") : "";
}

function bindMoneyInput(input) {
  input.addEventListener("input", () => {
    const digits = toEnDigits(input.value).replace(/[^\d]/g, "");
    input.value = digits ? faNum(Number(digits).toLocaleString("en-US")).replace(/,/g, "٬") : "";
    input.dispatchEvent(new Event("moneychange"));
  });
}

function todayJalaliStr() {
  const n = new Date();
  if (!window.JalaliJS) return "";
  const { jy, jm, jd } = JalaliJS.g2j(n.getFullYear(), n.getMonth() + 1, n.getDate());
  const p = (x) => String(x).padStart(2, "0");
  return `${jy}/${p(jm)}/${p(jd)}`;
}

function setDefaultJalaliDates() {
  const today = todayJalaliStr();
  $$("[data-jalali-today]").forEach((inp) => {
    if (!inp.value) inp.value = today;
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  setDefaultJalaliDates();
});
