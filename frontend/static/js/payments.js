/* ============================================================
   صفحه‌ی پرداخت‌ها — فقره‌های خرید با پیش‌پرداخت و مانده
   ============================================================ */

"use strict";

let paymentsData = { items: [], summary: {} };
let currentPayStatus = "";
let deletingPaymentId = null;
let addPayId = null;
let selectedProduct = null; // {id, name, sale_price}
let allProductsCache = [];
const selectedPayIds = new Set();

const money = (v) => faNum(Math.round(Number(v) || 0).toLocaleString("en-US")).replace(/,/g, "٬");

async function loadPayments() {
  try {
    const p = new URLSearchParams();
    if (currentPayStatus) p.set("status", currentPayStatus);
    const q = toEnDigits($("#search").value.trim());
    if (q) p.set("q", q);
    paymentsData = await api("/api/payments?" + p.toString());
    render();
  } catch (err) {
    toast(err.message, "error");
  }
}

function render() {
  const { items, summary } = paymentsData;
  const grid = $("#payments-grid");

  $$("#status-tabs .chip").forEach((c) =>
    c.classList.toggle("active", (c.dataset.status || "") === currentPayStatus));

  /* خلاصه */
  const fitClass = (v) => {
    const len = String(Math.round(Number(v) || 0)).length;
    if (len >= 13) return " fit-xs";
    if (len >= 11) return " fit-sm";
    if (len >= 9) return " fit-md";
    return "";
  };
  $("#pay-summary").innerHTML = `
    <div class="stat-card glass">
      <div class="stat-head"><span class="stat-label">تعداد فقره‌ها</span></div>
      <div class="stat-value stat-flex"><span class="stat-num">${faNum(summary.count || 0)}</span><span class="unit">فقره</span></div>
    </div>
    <div class="stat-card glass">
      <div class="stat-head"><span class="stat-label">مبلغ کل</span></div>
      <div class="stat-value stat-flex"><span class="stat-num${fitClass(summary.total)}">${money(summary.total)}</span><span class="unit">تومان</span></div>
    </div>
    <div class="stat-card glass">
      <div class="stat-head"><span class="stat-label">دریافت‌شده</span></div>
      <div class="stat-value stat-flex" style="color:var(--green)"><span class="stat-num${fitClass(summary.paid)}">${money(summary.paid)}</span><span class="unit">تومان</span></div>
    </div>
    <div class="stat-card glass">
      <div class="stat-head"><span class="stat-label">مانده</span></div>
      <div class="stat-value stat-flex" style="color:var(--red)"><span class="stat-num${fitClass(summary.remaining)}">${money(summary.remaining)}</span><span class="unit">تومان</span></div>
    </div>`;

  if (!items.length) {
    grid.innerHTML = "";
    $("#payments-empty").classList.remove("hidden");
    return;
  }
  $("#payments-empty").classList.add("hidden");

  grid.innerHTML = items.map((p) => {
    const settled = p.remaining <= 0.001;
    const pct = Math.min(100, p.paid_percent || 0);
    const checked = selectedPayIds.has(p.id) ? "checked" : "";
    return `
    <article class="entity-card glass ${checked ? 'row-selected' : ''}" data-id="${p.id}">
      <div class="ec-top">
        <label class="row" style="gap:10px;align-items:flex-start;cursor:pointer">
          <input type="checkbox" class="row-check" data-id="${p.id}" ${checked} style="accent-color:var(--accent);width:16px;height:16px;cursor:pointer;margin-top:3px">
          ${p.product_image
            ? `<img class="thumb" style="width:42px;height:42px;border-radius:11px" src="/data/images/${encodeURIComponent(p.product_image)}" alt="" loading="lazy">`
            : `<span class="thumb" style="width:42px;height:42px;border-radius:11px"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="6.4"/><path d="M12 9.2V12l2.1 1.5"/></svg></span>`}
          <div class="li-main">
            <div class="ec-title">${esc(p.product_name)}</div>
            <div class="ec-sub">${esc(p.customer_name) || "بدون نام"}${p.customer_phone ? " — " + p.customer_phone_fa : ""}</div>
            <div class="ec-badges">
              ${settled ? '<span class="badge green">تسویه‌شده</span>' : '<span class="badge amber">مانده دارد</span>'}
              <span class="badge gray plain">${p.pay_date_fa || "—"}</span>
            </div>
          </div>
        </label>
      </div>
      <div class="ec-body">
        <div class="ec-row"><span class="k">مبلغ کل</span><span class="v">${p.total_amount_display} تومان</span></div>
        <div class="ec-row"><span class="k">پرداخت‌شده</span><span class="v" style="color:var(--green)">${p.paid_amount_display} تومان</span></div>
        <div class="ec-row"><span class="k">مانده</span><span class="v" style="color:${settled ? "var(--green)" : "var(--red)"}">${p.remaining_display} تومان</span></div>
        ${p.purchase_price_display ? `<div class="ec-row"><span class="k">قیمت خرید ساعت</span><span class="v">${p.purchase_price_display} تومان</span></div>` : ""}
        ${p.purchase_date_fa ? `<div class="ec-row"><span class="k">تاریخ خرید ساعت</span><span class="v">${p.purchase_date_fa}</span></div>` : ""}
        ${p.reference ? `<div class="ec-row"><span class="k">رفرنس</span><span class="v"><span class="code-pill">${esc(p.reference)}</span></span></div>` : ""}
        ${p.website_code || p.office_code ? `<div class="ec-row"><span class="k">کد انبار / دفتر</span><span class="v">${p.website_code ? `<span class="code-pill">${esc(p.website_code)}</span>` : ""} ${p.office_code ? `<span class="code-pill" style="background:var(--accent-soft);color:var(--accent)">${esc(p.office_code)}</span>` : ""}</span></div>` : ""}
        ${p.settled_at_fa ? `<div class="ec-row"><span class="k">تاریخ تسویه</span><span class="v" style="color:var(--green)">${p.settled_at_fa}</span></div>` : ""}
        <div style="height:7px;border-radius:99px;background:var(--gray-soft);overflow:hidden;margin-top:6px">
          <div style="height:100%;width:${pct}%;border-radius:99px;background:linear-gradient(90deg,var(--accent),var(--accent-strong));transition:width .3s ease"></div>
        </div>
        ${p.notes ? `<div class="ec-row" style="align-items:flex-start"><span class="k">یادداشت</span><span class="v" style="font-weight:500;text-align:left;line-height:1.5">${esc(p.notes)}</span></div>` : ""}
      </div>
      <div class="ec-foot">
        ${!settled ? `<button class="btn btn-sm btn-primary grow" data-act="add-pay">ثبت پرداخت</button>
        <button class="btn btn-sm grow" data-act="settle-full" title="علامت‌گذاری به‌عنوان کاملاً تسویه‌شده بدون ورود مبلغ">تسویه‌ی کامل</button>` : `<span class="li-sub grow">✔ کامل پرداخت شده</span>`}
        <button class="btn btn-icon btn-sm" data-act="edit" title="ویرایش">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m14.5 5.5 4 4L8 20H4v-4z"/><path d="m12.5 7.5 4 4"/></svg>
        </button>
        <button class="btn btn-icon btn-sm btn-danger" data-act="delete" title="حذف">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 6.5h15M9.5 6V4.8A1.3 1.3 0 0 1 10.8 3.5h2.4a1.3 1.3 0 0 1 1.3 1.3V6M6.5 6.5l1 13h9l1-13"/></svg>
        </button>
      </div>
    </article>`;
  }).join("");
}

/* ------------------------------------------------ کلیک‌ها */

$("#payments-grid").addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-act]");
  if (!btn) return;
  const id = +btn.closest("[data-id]").dataset.id;
  const p = paymentsData.items.find((x) => x.id === id);
  if (!p) return;

  if (btn.dataset.act === "settle-full") {
    btn.disabled = true;
    try {
      await api(`/api/payments/${p.id}/settle-full`, { method: "POST", body: {} });
      toast("فقره به‌صورت کامل تسویه شد");
      loadPayments();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      btn.disabled = false;
    }
    return;
  }
  if (btn.dataset.act === "add-pay") {
    addPayId = p.id;
    $("#add-pay-info").innerHTML =
      `${esc(p.product_name)} — مانده: <b>${p.remaining_display} تومان</b>`;
    $("#add-pay-amount").value = "";
    openModal("modal-add-pay");
    return;
  }
  if (btn.dataset.act === "edit") {
    openPaymentModal(p);
    return;
  }
  if (btn.dataset.act === "delete") {
    deletingPaymentId = p.id;
    $("#delete-payment-name").textContent = `«${p.product_name}» — ${p.customer_name || "بدون نام"}`;
    openModal("modal-delete-payment");
  }
});

$("#btn-confirm-add-pay").addEventListener("click", async () => {
  const amount = +toEnDigits($("#add-pay-amount").value).replace(/[^\d]/g, "");
  if (!amount || amount <= 0) { toast("مبلغ را وارد کنید", "error"); return; }
  const btn = $("#btn-confirm-add-pay");
  btn.disabled = true;
  try {
    await api(`/api/payments/${addPayId}/add`, { method: "POST", body: { amount } });
    toast("پرداخت ثبت شد");
    closeModal("modal-add-pay");
    loadPayments();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

$("#btn-confirm-delete").addEventListener("click", async () => {
  if (!deletingPaymentId) return;
  try {
    await api(`/api/payments/${deletingPaymentId}`, { method: "DELETE" });
    toast("فقره حذف شد");
    closeModal("modal-delete-payment");
    loadPayments();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    deletingPaymentId = null;
  }
});

/* ------------------------------------------------ انتخاب گروهی */

function updatePayBulkBar() {
  const bar = $("#pay-bulk-bar");
  if (!selectedPayIds.size) {
    bar.classList.add("hidden");
    return;
  }
  bar.classList.remove("hidden");
  $("#pay-bulk-count").textContent = `${faNum(selectedPayIds.size)} مورد انتخاب شده`;
}

$("#payments-grid").addEventListener("change", (e) => {
  const check = e.target.closest(".row-check");
  if (!check) return;
  const id = +check.dataset.id;
  if (check.checked) selectedPayIds.add(id);
  else selectedPayIds.delete(id);
  check.closest(".entity-card").classList.toggle("row-selected", check.checked);
  updatePayBulkBar();
});

$("#btn-pay-bulk-clear").addEventListener("click", () => {
  selectedPayIds.clear();
  $$("#payments-grid .row-check").forEach((c) => { c.checked = false; });
  $$("#payments-grid .entity-card").forEach((c) => c.classList.remove("row-selected"));
  updatePayBulkBar();
});

$("#btn-pay-bulk-delete").addEventListener("click", () => {
  if (!selectedPayIds.size) return;
  $("#delete-bulk-pay-count").textContent = faNum(selectedPayIds.size) + " فقره";
  openModal("modal-delete-pay-bulk");
});

$("#btn-confirm-pay-bulk-delete").addEventListener("click", async () => {
  const btn = $("#btn-confirm-pay-bulk-delete");
  btn.disabled = true;
  try {
    const res = await api("/api/payments/bulk-delete", { method: "POST", body: { ids: [...selectedPayIds] } });
    toast(`${faNum(res.deleted)} فقره حذف شد`);
    selectedPayIds.clear();
    closeModal("modal-delete-pay-bulk");
    loadPayments();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

/* ------------------------------------------------ فرم فقره + جستجوی محصول */

function openPaymentModal(p = null) {
  const form = $("#payment-form");
  form.reset();
  selectedProduct = null;
  $("#payment-modal-title").textContent = p ? "ویرایش فقره" : "فقره‌ی جدید";
  $("#payment-product-search").value = "";
  $("#payment-product-hint").textContent = "";
  $("#payment-product-results").classList.add("hidden");

  /* در ویرایش، انتخاب محصول از انبار فقط در ثبتِ جدید معنی دارد */
  $("#payment-product-field").classList.toggle("hidden", !!p);
  const info = $("#payment-product-info");
  if (p && (p.product_image || p.reference || p.office_code || p.purchase_date_fa)) {
    info.innerHTML = `
      ${p.product_image
        ? `<img class="thumb" style="width:52px;height:52px;border-radius:12px" src="/data/images/${encodeURIComponent(p.product_image)}" alt="">`
        : `<span class="thumb" style="width:52px;height:52px;border-radius:12px"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="6.4"/><path d="M12 9.2V12l2.1 1.5"/></svg></span>`}
      <div>
        <div class="p-name">${esc(p.product_name)}</div>
        <div class="p-ref">${p.reference ? `<span class="code-pill">${esc(p.reference)}</span> ` : ""}${p.website_code ? `<span class="code-pill">${esc(p.website_code)}</span> ` : ""}${p.office_code ? `<span class="code-pill" style="background:var(--accent-soft);color:var(--accent)">${esc(p.office_code)}</span>` : ""}</div>
        <div class="li-sub">${p.purchase_price_display ? "خرید: " + p.purchase_price_display + " تومان — " : ""}${p.purchase_date_fa ? "تاریخ خرید: " + p.purchase_date_fa : ""}</div>
      </div>`;
    info.classList.remove("hidden");
  } else {
    info.classList.add("hidden");
    info.innerHTML = "";
  }

  form.querySelector('[name="product_name"]').value = p?.product_name || "";
  form.querySelector('[name="customer_name"]').value = p?.customer_name || "";
  form.querySelector('[name="customer_phone"]').value = p?.customer_phone || "";
  form.querySelector('[name="total_amount"]').value = p?.total_amount ? money(p.total_amount) : "";
  form.querySelector('[name="paid_amount"]').value = p?.paid_amount ? money(p.paid_amount) : "";
  form.querySelector('[name="pay_date"]').value = p?.pay_date ? jFromIso(p.pay_date) : todayJalaliStr();
  form.querySelector('[name="notes"]').value = p?.notes || "";
  form.dataset.editId = p ? p.id : "";

  updateRemainingBadge();
  openModal("modal-payment");
  setTimeout(() => $("#payment-product-search").focus(), 80);
}

function updateRemainingBadge() {
  const form = $("#payment-form");
  const total = +toEnDigits(form.querySelector('[name="total_amount"]').value).replace(/[^\d]/g, "") || 0;
  const paid = +toEnDigits(form.querySelector('[name="paid_amount"]').value).replace(/[^\d]/g, "") || 0;
  const rem = total - paid;
  const badge = $("#payment-remaining-badge");
  badge.className = `badge ${rem > 0 ? "amber" : "green"} plain`;
  badge.textContent = rem > 0 ? `مانده: ${money(rem)} تومان` : (total ? "تسویه‌شده ✔" : "مانده: ۰ تومان");
}

$("#payment-form").addEventListener("input", (e) => {
  if (["total_amount", "paid_amount"].includes(e.target.name)) updateRemainingBadge();
});

/* جستجوی زنده‌ی محصول از انبار */
let prodSearchTimer;
$("#payment-product-search").addEventListener("input", (e) => {
  clearTimeout(prodSearchTimer);
  prodSearchTimer = setTimeout(async () => {
    const q = toEnDigits(e.target.value.trim());
    const box = $("#payment-product-results");
    if (!q) { box.classList.add("hidden"); return; }
    try {
      const results = await api(`/api/products?q=${encodeURIComponent(q)}`);
      const top = results.slice(0, 8);
      if (!top.length) {
        box.innerHTML = '<div class="li-sub" style="padding:10px">موردی پیدا نشد — نام را دستی وارد کنید</div>';
        box.classList.remove("hidden");
        return;
      }
      box.innerHTML = top.map((p) => `
        <button type="button" class="menu-item prod-pick" data-id="${p.id}"
                data-name="${esc(p.name)}" data-price="${p.sale_price}">
          <span class="p-name">${esc(p.name)}</span>
          <span class="li-sub" style="margin-inline-start:auto">${esc(p.office_code)}${p.sale_price ? " — " + p.sale_price_display : ""}</span>
        </button>`).join("");
      box.classList.remove("hidden");
    } catch { /* بی‌اهمیت */ }
  }, 200);
});

$("#payment-product-results").addEventListener("click", (e) => {
  const pick = e.target.closest(".prod-pick");
  if (!pick) return;
  selectedProduct = {
    id: +pick.dataset.id,
    name: pick.dataset.name,
    price: +pick.dataset.price || 0,
  };
  const form = $("#payment-form");
  form.querySelector('[name="product_name"]').value = selectedProduct.name;
  if (selectedProduct.price && !form.querySelector('[name="total_amount"]').value) {
    form.querySelector('[name="total_amount"]').value = money(selectedProduct.price);
  }
  $("#payment-product-hint").textContent = `انتخاب شد: ${selectedProduct.name}`;
  $("#payment-product-results").classList.add("hidden");
  $("#payment-product-search").value = selectedProduct.name;
  updateRemainingBadge();
});

$("#btn-save-payment").addEventListener("click", async () => {
  const form = $("#payment-form");
  if (!form.reportValidity()) return;
  const payload = {};
  new FormData(form).forEach((v, k) => { payload[k] = v; });
  payload.total_amount = toEnDigits(payload.total_amount || "0").replace(/[^\d]/g, "") || "0";
  payload.paid_amount = toEnDigits(payload.paid_amount || "0").replace(/[^\d]/g, "") || "0";
  payload.customer_phone = toEnDigits(payload.customer_phone || "").trim();
  if (selectedProduct) payload.product_id = selectedProduct.id;

  const editId = form.dataset.editId;
  const btn = $("#btn-save-payment");
  btn.disabled = true;
  try {
    if (editId) {
      await api(`/api/payments/${editId}`, { method: "PUT", body: payload });
      toast("فقره به‌روزرسانی شد");
    } else {
      await api("/api/payments", { method: "POST", body: payload });
      toast("فقره‌ی پرداخت ثبت شد");
    }
    closeModal("modal-payment");
    loadPayments();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

$("#btn-new").addEventListener("click", () => openPaymentModal());

/* ------------------------------------------------ فیلتر و جستجو */

let searchTimer;
$("#search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadPayments, 200);
});

$("#status-tabs").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  currentPayStatus = chip.dataset.status || "";
  loadPayments();
});

$("#btn-export").addEventListener("click", () => {
  const a = document.createElement("a");
  a.href = "/export/payments.xlsx";
  document.body.appendChild(a);
  a.click();
  a.remove();
});

document.addEventListener("DOMContentLoaded", loadPayments);
