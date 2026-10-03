/* ============================================================
   صفحه‌ی فروش‌ها — لیست، جستجو، فیلتر، مرتب‌سازی، حذف گروهی،
   جزئیات کامل و ویرایش
   ============================================================ */

"use strict";

const PAYMENT_BADGE = {
  cash: ["green", "نقدی"],
  deposit: ["amber", "بیعانه"],
};

let salesData = { items: [], summary: {} };
const selectedIds = new Set();
let editingSaleId = null;
let deletingSaleId = null;
let currentDetail = null;

function currentQuery() {
  const p = new URLSearchParams();
  const q = toEnDigits($("#search").value.trim());
  if (q) p.set("q", q);
  if ($("#filter-sale-type").value) p.set("sale_type", $("#filter-sale-type").value);
  if ($("#filter-payment").value) p.set("pay_method", $("#filter-payment").value);
  const from = toEnDigits($("#filter-date-from").value.trim());
  const to = toEnDigits($("#filter-date-to").value.trim());
  if (from) p.set("date_from", from);
  if (to) p.set("date_to", to);
  p.set("sort", $("#sort-by").value);
  p.set("dir", $("#sort-dir").value);
  return p.toString();
}

async function loadSales() {
  try {
    salesData = await api("/api/sales?" + currentQuery());
    render();
  } catch (err) {
    toast(err.message, "error");
  }
}

function render() {
  const { items, summary } = salesData;
  const body = $("#sales-body");

  $("#summary-chips").innerHTML =
    `<span class="chip active plain" style="cursor:default">${faNum(summary.count || 0)} فقره</span>` +
    `<span class="chip plain" style="cursor:default">جمع فروش: ${faMoney(summary.total_final)}</span>` +
    `<span class="chip plain" style="cursor:default">جمع سود: ${faMoney(summary.total_profit)}</span>`;

  updateBulkBar();

  if (!items.length) {
    body.innerHTML = "";
    $("#sold-empty").classList.remove("hidden");
    return;
  }
  $("#sold-empty").classList.add("hidden");

  body.innerHTML = items.map((s) => {
    const checked = selectedIds.has(s.id) ? "checked" : "";
    return `
    <tr data-id="${s.id}" class="ev-row ${checked ? 'row-selected' : ''}">
      <td><input type="checkbox" class="row-check" data-id="${s.id}" ${checked} style="accent-color:var(--accent);width:15px;height:15px;cursor:pointer"></td>
      <td>
        ${s.product_image
          ? `<img class="thumb" src="/data/images/${encodeURIComponent(s.product_image)}" alt="" loading="lazy">`
          : `<span class="thumb"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="6.4"/><path d="M12 9.2V12l2.1 1.5"/></svg></span>`}
      </td>
      <td>
        <div class="p-name">${esc(s.product_name || "محصول حذف‌شده")}</div>
      </td>
      <td>
        ${s.reference ? `<span class="code-pill" title="رفرنس">${esc(s.reference)}</span>` : '<span class="muted">—</span>'}
      </td>
      <td>
        ${s.website_code ? `<span class="code-pill" title="کد انبار سایت">${esc(s.website_code)}</span>` : '<span class="muted">—</span>'}
      </td>
      <td>
        ${s.office_code ? `<span class="code-pill" title="کد دفتر فروشگاه" style="background:var(--accent-soft);color:var(--accent)">${esc(s.office_code)}</span>` : '<span class="muted">—</span>'}
      </td>
      <td>${esc(s.customer) || '<span class="muted">—</span>'}</td>
      <td class="muted" dir="ltr" style="text-align:right">${s.customer_phone_fa || '—'}</td>
      <td class="num" style="color:var(--green);font-weight:600">${s.final_price_display}</td>
      <td class="muted">${s.sale_date_fa}</td>
      <td>
        <div class="row-actions">
          <button class="btn btn-icon btn-sm" data-act="edit" title="ویرایش">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m14.5 5.5 4 4L8 20H4v-4z"/><path d="m12.5 7.5 4 4"/></svg>
          </button>
          <button class="btn btn-icon btn-sm btn-danger" data-act="delete" title="حذف">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 6.5h15M9.5 6V4.8A1.3 1.3 0 0 1 10.8 3.5h2.4a1.3 1.3 0 0 1 1.3 1.3V6M6.5 6.5l1 13h9l1-13"/></svg>
          </button>
        </div>
      </td>
    </tr>`;
  }).join("");
  updateBulkBar();

  /* هایلایت فروش مشخص‌شده از تقویم */
  const highlightId = +new URLSearchParams(location.search).get("highlight") || 0;
  if (highlightId) {
    const row = body.querySelector(`tr[data-id="${highlightId}"]`);
    if (row) {
      row.classList.add("row-highlight");
      row.scrollIntoView({ behavior: "smooth", block: "center" });
      const s = salesData.items.find((x) => x.id === highlightId);
      if (s) setTimeout(() => showSaleDetail(s), 350);
    }
  }
}

/* ------------------------------------------------ انتخاب گروهی */

function updateBulkBar() {
  const bar = $("#bulk-bar");
  if (!selectedIds.size) {
    bar.classList.add("hidden");
    const all = $("#check-all");
    if (all) { all.checked = false; all.indeterminate = false; }
    return;
  }
  bar.classList.remove("hidden");
  $("#bulk-count").textContent = `${faNum(selectedIds.size)} مورد انتخاب شده`;
  const visible = salesData.items.filter((s) => selectedIds.has(s.id)).length;
  const all = $("#check-all");
  all.checked = salesData.items.length > 0 && visible === salesData.items.length;
  all.indeterminate = visible > 0 && visible < salesData.items.length;
}

$("#sales-body").addEventListener("change", (e) => {
  const check = e.target.closest(".row-check");
  if (!check) return;
  const id = +check.dataset.id;
  if (check.checked) selectedIds.add(id);
  else selectedIds.delete(id);
  check.closest("tr").classList.toggle("row-selected", check.checked);
  updateBulkBar();
});

$("#check-all").addEventListener("change", (e) => {
  if (e.target.checked) salesData.items.forEach((s) => selectedIds.add(s.id));
  else selectedIds.clear();
  render();
});

$("#btn-bulk-clear").addEventListener("click", () => {
  selectedIds.clear();
  render();
});

$("#btn-bulk-delete").addEventListener("click", () => {
  if (!selectedIds.size) return;
  $("#delete-bulk-count").textContent = faNum(selectedIds.size) + " فروش";
  openModal("modal-delete-bulk");
});

$("#btn-confirm-bulk-delete").addEventListener("click", async () => {
  const btn = $("#btn-confirm-bulk-delete");
  btn.disabled = true;
  try {
    const res = await api("/api/sales/bulk-delete", { method: "POST", body: { ids: [...selectedIds] } });
    toast(`${faNum(res.deleted)} فروش حذف شد`);
    selectedIds.clear();
    closeModal("modal-delete-bulk");
    loadSales();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

/* ------------------------------------------------ جزئیات فروش */

function showSaleDetail(s) {
  currentDetail = s;
  const [pColor, pLabel] = PAYMENT_BADGE[s.payment_type] || ["gray", s.payment_type];
  const rows = [];
  const add = (k, v) => { if (v && String(v).trim()) rows.push(`<div class="kv"><span class="k">${k}</span><span class="v">${v}</span></div>`); };

  let head = `
    <div class="prod-cell mb-14">
      ${s.product_image
        ? `<img class="thumb" style="width:56px;height:56px;border-radius:14px" src="/data/images/${encodeURIComponent(s.product_image)}" alt="">`
        : `<span class="thumb" style="width:56px;height:56px;border-radius:14px"><svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="6.4"/><path d="M12 9.2V12l2.1 1.5"/></svg></span>`}
      <div>
        <div class="p-name" style="font-size:15px">${esc(s.product_name || "محصول حذف‌شده")}</div>
        <div class="p-ref">${s.website_code ? `<span class="code-pill">${esc(s.website_code)}</span> ` : ""}${s.office_code ? `<span class="code-pill" style="background:var(--accent-soft);color:var(--accent)">${esc(s.office_code)}</span>` : ""}${s.reference ? `<span class="code-pill" title="رفرنس">${esc(s.reference)}</span>` : ""}</div>
      </div>
    </div>`;

  add("کد فاکتور", s.invoice_code ? `<span class="code-pill">${esc(s.invoice_code)}</span>` : "");
  add("تاریخ فروش", s.sale_date_fa);
  add("قیمت فروش", `${s.sale_price_display} تومان`);
  if (s.final_price && s.final_price !== s.sale_price) {
    add("قیمت نهایی (با تخفیف)", `${s.final_price_display} تومان`);
    add("میزان تخفیف", `${faMoney(s.sale_price - s.final_price)} تومان`);
  }
  add("قیمت پرداخت‌شده توسط خریدار", `${s.final_price_display} تومان`);
  add("سود این فروش", `${s.profit_display} تومان`);
  add("قیمت خرید ساعت", `${s.purchase_price_display} تومان`);
  add("برند", esc(s.brand));
  add("تأمین‌کننده", esc(s.supplier));
  add("نوع فروش", s.sale_type_fa);
  add("روش پرداخت", `<span class="badge ${pColor} plain">${pLabel}</span>`);
  if (s.paid_breakdown_fa) add("ریز پرداخت", s.paid_breakdown_fa);
  if (s.payment_type === "deposit") {
    add("وضعیت تسویه", s.is_settled
      ? `<span class="badge green plain">تسویه شده${s.settled_at_fa ? " — " + s.settled_at_fa : ""}</span>`
      : '<span class="badge amber plain">در انتظار تسویه</span>');
  }
  add("خریدار", esc(s.customer));
  add("شماره تماس خریدار", s.customer_phone_fa);
  add("یادداشت", esc(s.notes));

  $("#sale-detail-body").innerHTML = head + rows.join("");
  openModal("modal-sale-detail");
}

/* ------------------------------------------------ ویرایش فروش */

function openEditModal(s) {
  editingSaleId = s.id;
  const form = $("#sale-edit-form");
  form.reset();
  form.querySelector('[name="sale_price"]').value = s.sale_price ? faNum(Number(s.sale_price).toLocaleString("en-US")) : "";
  form.querySelector('[name="discount_price"]').value =
    (s.final_price && s.final_price !== s.sale_price) ? faNum(Number(s.final_price).toLocaleString("en-US")) : "";
  form.querySelector('[name="paid_cash"]').value = s.paid_cash ? faNum(Number(s.paid_cash).toLocaleString("en-US")) : "";
  form.querySelector('[name="paid_pos"]').value = s.paid_pos ? faNum(Number(s.paid_pos).toLocaleString("en-US")) : "";
  form.querySelector('[name="paid_card2card"]').value = s.paid_card2card ? faNum(Number(s.paid_card2card).toLocaleString("en-US")) : "";
  form.querySelector('[name="customer"]').value = s.customer || "";
  form.querySelector('[name="customer_phone"]').value = s.customer_phone || "";
  form.querySelector('[name="sale_date"]').value = jFromIso(s.sale_date);
  form.querySelector('[name="sale_type"]').value = s.sale_type || "person";
  form.querySelector('[name="notes"]').value = s.notes || "";
  form.querySelector('[name="payment_type"]').value = s.payment_type || "cash";
  $$("#edit-payment-chips .chip").forEach((c) =>
    c.classList.toggle("active", c.dataset.pay === (s.payment_type || "cash")));
  openModal("modal-sale-edit");
}

$("#edit-payment-chips").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  $$("#edit-payment-chips .chip").forEach((c) => c.classList.toggle("active", c === chip));
  $("#sale-edit-form [name='payment_type']").value = chip.dataset.pay;
});

$("#btn-save-edit").addEventListener("click", async () => {
  const form = $("#sale-edit-form");
  if (!form.reportValidity()) return;
  const payload = {};
  new FormData(form).forEach((v, k) => { payload[k] = v; });
  ["sale_price", "discount_price", "paid_cash", "paid_pos", "paid_card2card"].forEach((k) => {
    payload[k] = toEnDigits(payload[k] || "0").replace(/[^\d]/g, "") || "0";
  });
  payload.customer_phone = toEnDigits(payload.customer_phone || "").trim();
  const btn = $("#btn-save-edit");
  btn.disabled = true;
  try {
    await api(`/api/sales/${editingSaleId}`, { method: "PUT", body: payload });
    toast("تغییرات فروش ذخیره شد");
    closeModal("modal-sale-edit");
    loadSales();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

/* ------------------------------------------------ حذف تکی */

$("#btn-confirm-delete-sale").addEventListener("click", async () => {
  if (!deletingSaleId) return;
  const btn = $("#btn-confirm-delete-sale");
  btn.disabled = true;
  try {
    await api(`/api/sales/${deletingSaleId}`, { method: "DELETE" });
    toast("فروش حذف شد و ساعت دوباره موجود شد");
    closeModal("modal-delete-sale");
    loadSales();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
    deletingSaleId = null;
  }
});

/* ------------------------------------------------ کلیک روی ردیف‌ها */

$("#sales-body").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-act]");
  const row = e.target.closest("tr[data-id]");
  if (!row) return;
  const s = salesData.items.find((x) => x.id === +row.dataset.id);
  if (!s) return;
  if (btn && btn.dataset.act === "edit") { openEditModal(s); return; }
  if (btn && btn.dataset.act === "delete") {
    deletingSaleId = s.id;
    $("#delete-sale-name").textContent = `«${s.product_name || "محصول حذف‌شده"}» — ${s.sale_date_fa}`;
    openModal("modal-delete-sale");
    return;
  }
  if (!btn && !e.target.closest(".row-check")) showSaleDetail(s);
});

$("#btn-detail-edit").addEventListener("click", () => {
  if (!currentDetail) return;
  closeModal("modal-sale-detail");
  openEditModal(currentDetail);
});

/* ------------------------------------------------ فیلتر و جستجو */

let searchTimer;
$("#search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadSales, 200);
});
["#filter-sale-type", "#filter-payment", "#sort-by", "#sort-dir"].forEach((sel) => {
  $(sel).addEventListener("change", loadSales);
});
["#filter-date-from", "#filter-date-to"].forEach((sel) => {
  $(sel).addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadSales, 400);
  });
});

$("#btn-clear-filters").addEventListener("click", () => {
  $("#search").value = "";
  $("#filter-sale-type").value = "";
  $("#filter-payment").value = "";
  $("#filter-date-from").value = "";
  $("#filter-date-to").value = "";
  $("#sort-by").value = "date";
  $("#sort-dir").value = "desc";
  loadSales();
});

$("#btn-export").addEventListener("click", () => {
  const a = document.createElement("a");
  a.href = "/export/sales.xlsx";
  document.body.appendChild(a);
  a.click();
  a.remove();
});

document.addEventListener("DOMContentLoaded", loadSales);
