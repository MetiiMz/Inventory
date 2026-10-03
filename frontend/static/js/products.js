/* ============================================================
   صفحه‌ی انبار ساعت‌ها — لیست، جستجو، فیلتر، مرتب‌سازی،
   انتخاب گروهی، فروش، ورود/خروجی
   ============================================================ */

"use strict";

let allProducts = [];
let editingId = null;
let deletingId = null;
let saleProductId = null;
const selectedIds = new Set();

const body = $("#products-body");
const emptyBox = $("#products-empty");

/* ------------------------------------------------ بارگذاری لیست */

function currentQuery() {
  const p = new URLSearchParams();
  const q = toEnDigits($("#search").value.trim());
  if (q) p.set("q", q);
  if ($("#filter-brand").value) p.set("brand", $("#filter-brand").value);
  if ($("#filter-status").value) p.set("status", $("#filter-status").value);
  const from = toEnDigits($("#filter-date-from").value.trim());
  const to = toEnDigits($("#filter-date-to").value.trim());
  if (from) p.set("date_from", from);
  if (to) p.set("date_to", to);
  p.set("sort", $("#sort-by").value);
  p.set("dir", $("#sort-dir").value);
  return p.toString();
}

async function loadProducts() {
  try {
    allProducts = await api("/api/products?" + currentQuery());
    render();
  } catch (err) {
    toast(err.message, "error");
  }
}

function render() {
  const list = allProducts;

  /* چیپ‌های خلاصه */
  const availableCount = allProducts.filter((p) => p.is_available).length;
  const totalVal = allProducts.reduce((s, p) => s + p.total_value, 0);
  const totalSaleVal = allProducts.reduce((s, p) => s + p.total_sale_value, 0);
  $("#summary-chips").innerHTML =
    `<span class="chip active plain" style="cursor:default">${faNum(allProducts.length)} مدل</span>` +
    `<span class="chip plain" style="cursor:default">${faNum(availableCount)} موجود</span>` +
    `<span class="chip plain" style="cursor:default">${faNum(allProducts.length - availableCount)} ناموجود</span>` +
    `<span class="chip plain" style="cursor:default">خرید: ${faMoney(totalVal)}</span>` +
    `<span class="chip plain" style="cursor:default">فروش: ${faMoney(totalSaleVal)}</span>` +
    `<span class="chip plain" style="cursor:default">سود بالقوه: ${faMoney(totalSaleVal - totalVal)}</span>`;

  if (!list.length) {
    body.innerHTML = "";
    emptyBox.classList.remove("hidden");
    updateBulkBar();
    return;
  }
  emptyBox.classList.add("hidden");

  body.innerHTML = list.map((p) => {
    const checked = selectedIds.has(p.id) ? "checked" : "";
    return `
    <tr data-id="${p.id}" class="${checked ? 'row-selected' : ''}">
      <td><input type="checkbox" class="row-check" data-id="${p.id}" ${checked} style="accent-color:var(--accent);width:15px;height:15px;cursor:pointer"></td>
      <td>
        <div class="prod-cell">
          ${p.image
            ? `<img class="thumb" src="/data/images/${encodeURIComponent(p.image)}" alt="" loading="lazy">`
            : `<span class="thumb"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="6.4"/><path d="M12 9.2V12l2.1 1.5"/></svg></span>`}
          <div>
            <div class="p-name">${esc(p.name)}</div>
            ${p.reference ? `<div class="p-ref">رفرنس ${esc(p.reference)}</div>` : ""}
          </div>
        </div>
      </td>
      <td><span class="code-pill" title="کد انبار سایت">${esc(p.website_code)}</span></td>
      <td><span class="code-pill" title="کد دفتر فروشگاه" style="background:var(--accent-soft);color:var(--accent)">${esc(p.office_code)}</span></td>
      <td>${p.brand ? `<span class="badge gray plain">${esc(p.brand)}</span>` : '<span class="muted">—</span>'}</td>
      <td class="num">${p.purchase_price ? p.purchase_price_display : '<span class="muted">—</span>'}</td>
      <td class="num">${p.sale_price_display}</td>
      <td class="num" style="color:${p.profit_per_unit >= 0 ? "var(--green)" : "var(--red)"}">${p.profit_per_unit_display}</td>
      <td>${p.is_available
        ? '<span class="badge green">موجود</span>'
        : '<span class="badge red">ناموجود</span>'}</td>
      <td class="muted">${p.purchase_date_fa || "—"}</td>
      <td class="muted">${esc(p.supplier) || "—"}</td>
      <td>
        <div class="row-actions">
          <button class="btn btn-sm" data-act="sale" title="ثبت فروش" ${p.is_available ? "" : "disabled"}>
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 6.5h11l1.5 12.5h-14z"/><path d="M9 9.5a3 3 0 0 1 6 0"/></svg>
            فروش
          </button>
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
}

/* ------------------------------------------------ انتخاب گروهی */

function updateBulkBar() {
  const bar = $("#bulk-bar");
  if (!selectedIds.size) {
    bar.classList.add("hidden");
    $("#check-all").checked = false;
    $("#check-all").indeterminate = false;
    return;
  }
  bar.classList.remove("hidden");
  $("#bulk-count").textContent = `${faNum(selectedIds.size)} مورد انتخاب شده`;
  const visible = allProducts.filter((p) => selectedIds.has(p.id)).length;
  const all = $("#check-all");
  all.checked = allProducts.length > 0 && visible === allProducts.length;
  all.indeterminate = visible > 0 && visible < allProducts.length;
}

body.addEventListener("change", (e) => {
  const check = e.target.closest(".row-check");
  if (check) {
    const id = +check.dataset.id;
    if (check.checked) selectedIds.add(id);
    else selectedIds.delete(id);
    check.closest("tr").classList.toggle("row-selected", check.checked);
    updateBulkBar();
    return;
  }
});

$("#check-all").addEventListener("change", (e) => {
  if (e.target.checked) allProducts.forEach((p) => selectedIds.add(p.id));
  else allProducts.forEach((p) => selectedIds.delete(p.id));
  render();
});

$("#btn-bulk-clear").addEventListener("click", () => {
  selectedIds.clear();
  render();
});

$("#btn-bulk-delete").addEventListener("click", () => {
  if (!selectedIds.size) return;
  $("#delete-bulk-count").textContent = faNum(selectedIds.size) + " ساعت";
  openModal("modal-delete-bulk");
});

$("#btn-confirm-bulk-delete").addEventListener("click", async () => {
  const btn = $("#btn-confirm-bulk-delete");
  btn.disabled = true;
  try {
    const res = await api("/api/products/bulk-delete", {
      method: "POST",
      body: { ids: [...selectedIds] },
    });
    toast(`${faNum(res.deleted)} ساعت حذف شد`);
    selectedIds.clear();
    closeModal("modal-delete-bulk");
    loadProducts();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

$("#btn-export-selected").addEventListener("click", () => {
  if (!selectedIds.size) return;
  const rows = allProducts.filter((p) => selectedIds.has(p.id));
  downloadCsv(rows, "tiko-selected-products");
});

function downloadCsv(list, name) {
  const headers = ["نام ساعت", "رفرنس", "کد انبار سایت", "کد دفتر فروشگاه", "برند",
    "قیمت خرید", "قیمت فروش", "وضعیت", "تأمین‌کننده", "تاریخ خرید", "یادداشت"];
  const rows = list.map((p) => [
    p.name, p.reference || "", p.website_code, p.office_code, p.brand || "",
    p.purchase_price || 0, p.sale_price || 0, p.is_available ? "موجود" : "ناموجود",
    p.supplier || "", jFromIso(p.purchase_date), p.notes || "",
  ]);
  const csv = [headers, ...rows].map((r) =>
    r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")
  ).join("\r\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name + ".csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

/* ------------------------------------------------ فرم محصول */

function formToPayload(form) {
  const fd = new FormData(form);
  const o = {};
  for (const [k, v] of fd.entries()) o[k] = v;
  ["purchase_price", "sale_price", "paid_cash", "paid_pos", "paid_card2card", "discount_price"].forEach((k) => {
    o[k] = toEnDigits(o[k] || "0").replace(/[^\d-]/g, "") || "0";
  });
  return o;
}

function openProductModal(p = null) {
  editingId = p ? p.id : null;
  const form = $("#product-form");
  form.reset();
  $("#product-modal-title").textContent = p ? "ویرایش ساعت" : "افزودن ساعت";
  fillBrandDatalist($("#brands-dl"));

  const wrap = $("#modal-product .img-upload");
  wrap.dataset.ready = "";
  wrap.querySelector('input[type="hidden"]').value = p ? p.image || "" : "";

  form.querySelector('[name="name"]').value = p?.name || "";
  form.querySelector('[name="reference"]').value = p?.reference || "";
  form.querySelector('[name="brand"]').value = p?.brand || "";
  form.querySelector('[name="website_code"]').value = p?.website_code || "";
  form.querySelector('[name="office_code"]').value = p?.office_code || "";
  form.querySelector('[name="purchase_price"]').value = p?.purchase_price ? moneyIn(p.purchase_price) : "";
  form.querySelector('[name="sale_price"]').value = p?.sale_price ? moneyIn(p.sale_price) : "";
  form.querySelector('[name="supplier"]').value = p?.supplier || "";
  form.querySelector('[name="purchase_date"]').value = p?.purchase_date
    ? jFromIso(p.purchase_date) : "";
  form.querySelector('[name="notes"]').value = p?.notes || "";

  document.dispatchEvent(new CustomEvent("modal:opened", { detail: { root: $("#modal-product") } }));
  updateProfitPreview();
  openModal("modal-product");
}

function updateProfitPreview() {
  const form = $("#product-form");
  const buy = +toEnDigits(form.querySelector('[name="purchase_price"]').value).replace(/[^\d]/g, "") || 0;
  const sell = +toEnDigits(form.querySelector('[name="sale_price"]').value).replace(/[^\d]/g, "") || 0;
  const badge = $("#profit-badge");
  if (!buy && !sell) {
    badge.textContent = "با وارد کردن قیمت‌ها، سود اینجا نمایش داده می‌شود";
    badge.className = "badge gray plain";
    return;
  }
  const unit = sell - buy;
  const color = unit >= 0 ? "green" : "red";
  badge.className = `badge ${color} plain`;
  badge.textContent = `سود این ساعت: ${faMoney(unit)} تومان`;
}

$("#product-form").addEventListener("moneychange", updateProfitPreview);

$("#btn-save-product").addEventListener("click", async () => {
  const form = $("#product-form");
  if (!form.reportValidity()) return;
  const payload = formToPayload(form);
  const btn = $("#btn-save-product");
  btn.disabled = true;
  try {
    if (editingId) {
      await api(`/api/products/${editingId}`, { method: "PUT", body: payload });
      toast("تغییرات ساعت ذخیره شد");
    } else {
      await api("/api/products", { method: "POST", body: payload });
      toast("ساعت جدید به انبار اضافه شد");
    }
    closeModal("modal-product");
    loadProducts();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

$("#btn-new").addEventListener("click", () => openProductModal());

/* ------------------------------------------------ فروش */

let saleProductData = null;

function openSaleModal(p) {
  saleProductId = p.id;
  saleProductData = p;
  const form = $("#sale-form");
  form.reset();
  $("#sale-prod-cell").innerHTML = `
    ${p.image
      ? `<img class="thumb" src="/data/images/${encodeURIComponent(p.image)}" alt="">`
      : `<span class="thumb"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="6.4"/><path d="M12 9.2V12l2.1 1.5"/></svg></span>`}
    <div><div class="p-name">${esc(p.name)}</div><div class="p-ref">کد دفتر: ${esc(p.office_code)}</div></div>`;
  form.querySelector('[name="sale_price"]').value = moneyIn(p.sale_price);
  form.querySelector('[name="sale_date"]').value = todayJalaliStr();
  form.querySelector('[name="customer_phone"]').value = "";
  form.querySelector('[name="sale_type"]').value = "person";
  form.querySelector('[name="discount_price"]').value = "";
  form.querySelector('[name="paid_cash"]').value = "";
  form.querySelector('[name="paid_pos"]').value = "";
  form.querySelector('[name="paid_card2card"]').value = "";
  form.querySelector('[name="payment_type"]').value = "cash";
  $$("#sale-payment-chips .chip").forEach((c) =>
    c.classList.toggle("active", c.dataset.pay === "cash"));
  $("#pay-basis-hint").textContent = "فروش کامل — تسویه‌شده ثبت می‌شود";
  $("#invoice-code-hint").textContent = "";
  updateSalePaymentFields();
  fetchInvoiceCode();
  openModal("modal-sale");
}

/* فیلدهای شرطی بر اساس نوع پرداخت */
function updateSalePaymentFields() {
  const form = $("#sale-form");
  const type = form.querySelector('[name="payment_type"]').value;
  $("#deposit-fields").classList.toggle("hidden", type !== "deposit");
  updateSaleHints();
}

/* پیش‌نمایش کد فاکتور زیر فیلد نوع فروش */
async function fetchInvoiceCode() {
  const hint = $("#invoice-code-hint");
  if (!hint) return;
  try {
    const res = await api("/api/sales?next_code=1");
    hint.textContent = res.next_invoice_code ? `اگر خالی بگذارید، خودکار صادر می‌شود: ${res.next_invoice_code}` : "";
  } catch { /* پیش‌نمایش کد فاکتور بحرانی نیست */ }
}

function parseMoneyInput(el) {
  return el ? (+toEnDigits(el.value).replace(/[^\d]/g, "") || 0) : 0;
}

function updateSaleHints() {
  const form = $("#sale-form");
  const type = form.querySelector('[name="payment_type"]').value;
  const base = saleProductData ? (saleProductData.sale_price || 0) : 0;
  const total = parseMoneyInput(form.querySelector('[name="sale_price"]')) || base;

  const dHint = $("#discount-hint");
  const bdHint = $("#paid-breakdown-hint");
  const paid = parseMoneyInput(form.querySelector('[name="paid_cash"]')) +
    parseMoneyInput(form.querySelector('[name="paid_pos"]')) +
    parseMoneyInput(form.querySelector('[name="paid_card2card"]'));

  const finalPrice = type === "deposit" ? total
    : (parseMoneyInput(form.querySelector('[name="discount_price"]')) || total);

  if (bdHint) {
    if (paid > 0) {
      bdHint.textContent = paid > finalPrice + 0.001
        ? `جمع پرداخت‌ها نمی‌تواند از قیمت نهایی (${faMoney(finalPrice)}) بیشتر باشد`
        : `جمع پرداخت‌ها: ${faMoney(paid)} تومان${type === "deposit" ? ` — مانده: ${faMoney(Math.max(0, finalPrice - paid))} تومان` : ""}`;
    } else if (type === "deposit") {
      bdHint.textContent = "برای بیعانه، دست‌کم یکی از مبالغ را وارد کنید";
    } else {
      bdHint.textContent = "اگر خالی بماند، کل مبلغ نقدی ثبت می‌شود";
    }
  }
  if (dHint) {
    const disc = parseMoneyInput(form.querySelector('[name="discount_price"]'));
    dHint.textContent = disc > 0
      ? (disc < total
          ? `تخفیف: ${faMoney(total - disc)} تومان — قیمت نهایی: ${faMoney(disc)} تومان`
          : "قیمت نهایی باید کمتر یا مساوی قیمت فروش باشد")
      : `قیمت نهایی: ${faMoney(total)} تومان`;
  }
}

$("#sale-payment-chips").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  $$("#sale-payment-chips .chip").forEach((c) => c.classList.toggle("active", c === chip));
  $("#sale-form [name='payment_type']").value = chip.dataset.pay;
  $("#pay-basis-hint").textContent = chip.dataset.pay === "deposit"
    ? "فروش بیعانه — مانده در «پرداخت‌ها» پیگیری می‌شود"
    : "فروش کامل — تسویه‌شده ثبت می‌شود";
  updateSalePaymentFields();
});
$("#sale-form").addEventListener("input", (e) => {
  if (["discount_price", "paid_cash", "paid_pos", "paid_card2card", "sale_price"].includes(e.target.name)) {
    updateSaleHints();
  }
});

$("#btn-save-sale").addEventListener("click", async () => {
  const form = $("#sale-form");
  if (!form.reportValidity()) return;
  const paymentType = form.querySelector('[name="payment_type"]').value;
  const paidCash = parseMoneyInput(form.querySelector('[name="paid_cash"]'));
  const paidPos = parseMoneyInput(form.querySelector('[name="paid_pos"]'));
  const paidCard2card = parseMoneyInput(form.querySelector('[name="paid_card2card"]'));
  const paidNow = paidCash + paidPos + paidCard2card;
  if (paymentType === "deposit" && paidNow < 1) {
    toast("برای فروش بیعانه، مبلغ بیعانه را در روش‌های پرداخت وارد کنید", "error");
    return;
  }
  const payload = {
    product_id: saleProductId,
    sale_price: toEnDigits(form.querySelector('[name="sale_price"]').value).replace(/[^\d]/g, "") || "0",
    sale_date: form.querySelector('[name="sale_date"]').value,
    customer: form.querySelector('[name="customer"]').value,
    customer_phone: toEnDigits(form.querySelector('[name="customer_phone"]').value).trim(),
    sale_type: form.querySelector('[name="sale_type"]').value,
    payment_type: paymentType,
    discount_price: toEnDigits(form.querySelector('[name="discount_price"]').value).replace(/[^\d]/g, "") || "0",
    paid_cash: String(paidCash),
    paid_pos: String(paidPos),
    paid_card2card: String(paidCard2card),
    notes: form.querySelector('[name="notes"]').value,
    invoice_code: form.querySelector('[name="invoice_code"]').value.trim(),
  };
  const btn = $("#btn-save-sale");
  btn.disabled = true;
  try {
    const res = await api("/api/sales", { method: "POST", body: payload });
    const code = res?.sale?.invoice_code || "";
    toast((payload.payment_type === "deposit"
      ? "فروش بیعانه ثبت شد — مانده در «پرداخت‌ها» ثبت شد"
      : "فروش ثبت شد و ساعت ناموجود شد") + (code ? ` — کد فاکتور: ${code}` : ""));
    closeModal("modal-sale");
    loadProducts();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

/* ------------------------------------------------ حذف تکی */

function openDeleteModal(p) {
  deletingId = p.id;
  $("#delete-name").textContent = `«${p.name}» (کد ${p.office_code})`;
  openModal("modal-delete");
}

$("#btn-confirm-delete").addEventListener("click", async () => {
  if (!deletingId) return;
  const btn = $("#btn-confirm-delete");
  btn.disabled = true;
  try {
    await api(`/api/products/${deletingId}`, { method: "DELETE" });
    toast("ساعت حذف شد");
    closeModal("modal-delete");
    loadProducts();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
    deletingId = null;
  }
});

/* ------------------------------------------------ کلیک روی اکشن‌ها */

body.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-act]");
  if (!btn || btn.disabled) return;
  const id = +btn.closest("tr").dataset.id;
  const p = allProducts.find((x) => x.id === id);
  if (!p) return;
  if (btn.dataset.act === "edit") openProductModal(p);
  if (btn.dataset.act === "sale") openSaleModal(p);
  if (btn.dataset.act === "delete") openDeleteModal(p);
});

/* ------------------------------------------------ جستجو و فیلتر */

let searchTimer;
$("#search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadProducts, 200);
});
["#filter-brand", "#filter-status", "#sort-by", "#sort-dir"].forEach((sel) => {
  $(sel).addEventListener("change", loadProducts);
});
["#filter-date-from", "#filter-date-to"].forEach((sel) => {
  $(sel).addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadProducts, 400);
  });
});

$("#btn-clear-filters").addEventListener("click", () => {
  $("#search").value = "";
  $("#filter-brand").value = "";
  $("#filter-status").value = "";
  $("#filter-date-from").value = "";
  $("#filter-date-to").value = "";
  $("#sort-by").value = "office_code";
  $("#sort-dir").value = "asc";
  loadProducts();
});

async function loadBrandFilter() {
  try {
    const data = await api("/api/brands");
    const sel = $("#filter-brand");
    data.brands.forEach((b) => {
      const opt = document.createElement("option");
      opt.value = b; opt.textContent = b;
      sel.appendChild(opt);
    });
  } catch { /* بی‌اهمیت */ }
}

/* ------------------------------------------------ خروجی و ورودی */

function downloadUrl(url) {
  const a = document.createElement("a");
  a.href = url;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

$("#btn-export-xlsx").addEventListener("click", () => downloadUrl("/export/products.xlsx"));
$("#btn-export-csv").addEventListener("click", () => downloadUrl("/export/products.csv"));
$("#btn-template").addEventListener("click", () => downloadUrl("/api/import/template"));

$("#btn-import").addEventListener("click", () => {
  $("#import-result").classList.add("hidden");
  openModal("modal-import");
});

$("#btn-run-import").addEventListener("click", async () => {
  const fileInput = $("#import-file");
  if (!fileInput.files[0]) { toast("ابتدا فایل را انتخاب کنید", "error"); return; }
  const fd = new FormData();
  fd.append("file", fileInput.files[0]);
  fd.append("update_existing", $("#import-update").checked ? "1" : "0");
  const btn = $("#btn-run-import");
  btn.disabled = true;
  try {
    const res = await api("/api/import/products", { method: "POST", body: fd });
    const box = $("#import-result");
    box.classList.remove("hidden");
    const st = res.stats;
    let html = `<div class="badge green plain">افزوده‌شده: ${faNum(st.added)} — به‌روزرسانی: ${faNum(st.updated)} — رد‌شده: ${faNum(st.skipped)}</div>`;
    if (res.errors && res.errors.length) {
      html += `<div class="mt-8" style="font-size:11.5px;color:var(--amber)">${res.errors.map(esc).join("<br>")}</div>`;
    }
    box.innerHTML = html;
    toast("ورود اطلاعات انجام شد");
    loadProducts();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

/* ------------------------------------------------ شروع */

document.addEventListener("DOMContentLoaded", () => {
  $$("#product-form [name='purchase_price'], #product-form [name='sale_price'], "
    + "#sale-form [name='sale_price'], #sale-form [name='discount_price'], "
    + "#sale-form [name='paid_cash'], #sale-form [name='paid_pos'], "
    + "#sale-form [name='paid_card2card']")
    .forEach(bindMoneyInput);
  loadBrandFilter();
  loadProducts();
});
