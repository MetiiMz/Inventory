/* ============================================================
   صفحه‌ی فروش‌ها — لیست، جستجو، فیلتر، مرتب‌سازی، حذف گروهی،
   جزئیات کامل و ویرایش
   ============================================================ */

"use strict";

const PAYMENT_BADGE = {
  cash: ["green", "تسویه کامل"],
  deposit: ["amber", "بیعانه"],
  credit: ["blue", "اعتباری"],
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
  if ($("#filter-credit-service").value) p.set("credit_provider", $("#filter-credit-service").value);
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
    `<span class="chip plain" style="cursor:default">جمع فروش: ${faMoney(summary.total_sale)}</span>` +
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
      <td class="num" style="color:var(--green);font-weight:600">${s.sale_price_display}</td>
      <td class="muted">${s.sale_date_fa}</td>
      <td class="pay-cell">
        ${s.payment_type === "credit"
          ? `<span class="badge blue plain">اعتباری</span> <span class="pay-svc">${esc(s.credit_provider_fa || "")}</span>${s.credit_tracking_code ? `<span class="code-pill" style="font-size:11px;margin-left:4px">${esc(s.credit_tracking_code)}</span>` : ""}`
          : s.payment_type === "deposit"
            ? `<span class="badge amber plain">بیعانه</span>`
            : `<span class="badge green plain">تسویه کامل</span>`}
      </td>
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


  function updateCreditPreview(formId) {
    const form = $(`#${formId}`);
    if (!form) return;
    const providerInput = form.querySelector("[name='credit_provider']");
    const codeInput = form.querySelector("[name='credit_tracking_code']");
    const preview = form.querySelector(".code-preview");
    const previewCode = form.querySelector(".preview-code");
    if (!providerInput || !codeInput || !preview) return;
    const provider = providerInput.value;
    const raw = codeInput.value.trim();
    if (!provider || !raw) {
      preview.style.display = "none";
      return;
    }
    const prefix = { digipay: "D", snappay: "S", torob: "T" }[provider] || "";
    let code = raw.toUpperCase();
    if (code.startsWith(prefix + "-")) code = code.slice(prefix.length + 1);
    const full = prefix ? `${prefix}-${code}` : code;
    previewCode.textContent = full;
    preview.style.display = "";
  }

/* ------------------------------------------------ جزئیات فروش */

/* کاشی‌های مودال جزئیات — همه‌ی مقادیر پیش از رسیدن به این توابع با esc()
   امن شده‌اند؛ مقدار خالی به «—» تبدیل می‌شود تا شبکه‌ی کارت جابه‌جا نشود. */
const SD_DASH = '<span class="sd-dash">—</span>';

const sdMoney = (v) => (v === null || v === undefined || String(v).trim() === "" ? "" : `${esc(v)} تومان`);

function sdCode(v, extraClass) {
  if (!v) return "";
  return `<span class="code-pill${extraClass ? " " + extraClass : ""}">${esc(v)}</span>`;
}

function sdTile([label, value, cls, span]) {
  const empty = value === null || value === undefined || String(value).trim() === "";
  return `<div class="sd-tile${span ? " span-2" : ""}">` +
    `<span class="sd-k">${esc(label)}</span>` +
    `<span class="sd-v${cls ? " " + cls : ""}">${empty ? SD_DASH : value}</span>` +
    `</div>`;
}

function sdCard(title, tiles) {
  // تعداد فرد کاشی یک خانه‌ی خالی در شبکه‌ی دوستونه می‌گذاشت؛
  // کاشی آخر در این حالت تمام‌عرض می‌شود تا شبکه همیشه پر به نظر برسد
  const rows = tiles.map((t) => t.slice());
  if (rows.length % 2 === 1) rows[rows.length - 1][3] = true;
  return `<section class="sd-card">` +
    `<h4 class="sd-card-title">${esc(title)}</h4>` +
    `<div class="sd-grid">${rows.map(sdTile).join("")}</div>` +
    `</section>`;
}

/* کارت ۱ — «اطلاعات ساعت»: ترتیب ثابت، مقادیر خالی همیشه با «—» */
const SD_INFO_TILES = (s) => [
  ["برند", esc(s.brand)],
  ["کد رفرانس", sdCode(s.reference)],
  ["کد دفتر فروشگاه", sdCode(s.office_code, "is-accent")],
  ["کد انبار سایت", sdCode(s.website_code)],
  ["قیمت خرید", sdMoney(s.purchase_price_display)],
  ["تاریخ خرید", esc(s.purchase_date_fa)],
  ["تأمین‌کننده", esc(s.supplier)],
];

/* کارت ۲ — «اطلاعات فروش»: سرِ مشترک (خریدار → نوع پرداخت) */
const SD_SALE_MAIN_TILES = (s, pColor, pLabel) => {
  const tiles = [];
  // خریدار و تلفن فقط وقتی اصلاً وجود دارند نمایش داده می‌شوند
  if (s.customer) tiles.push(["خریدار", esc(s.customer)]);
  if (s.customer_phone_fa) tiles.push(["شماره تماس خریدار", esc(s.customer_phone_fa)]);
  tiles.push(
    ["قیمت فروش", sdMoney(s.sale_price_display)],
    ["سود این فروش", sdMoney(s.profit_display), "sd-profit"],
    ["کد فاکتور", sdCode(s.invoice_code)],
    ["تاریخ فروش", esc(s.sale_date_fa)],
    ["نوع فروش", esc(s.sale_type_fa)],
    ["نوع پرداخت", `<span class="badge ${pColor} plain">${esc(pLabel)}</span>`],
  );
  return tiles;
};

/* یک فهرست جدا برای هر نوع پرداخت — دنباله‌ی کارت ۲ */
const SD_SALE_TILES = {
  cash: (s, pColor, pLabel) => [
    ...SD_SALE_MAIN_TILES(s, pColor, pLabel),
  ],
  credit: (s, pColor, pLabel) => [
    ...SD_SALE_MAIN_TILES(s, pColor, pLabel),
    ["سرویس", esc(s.credit_provider_fa)],
    ["کد رهگیری", s.credit_tracking_code
      ? `<span class="code-pill" dir="ltr">${esc(s.credit_tracking_code)}</span>` : ""],
  ],
  deposit: (s, pColor, pLabel) => [
    ...SD_SALE_MAIN_TILES(s, pColor, pLabel),
    ["پرداخت‌شده تاکنون", sdMoney(s.deposit_paid_amount_display)],
    ...(Number(s.deposit_remaining) > 0
      ? [["مانده", sdMoney(s.deposit_remaining_display)]]
      : []),
    ["وضعیت تسویه", s.is_settled
      ? `<span class="badge green plain">تسویه شده${s.settled_at_fa ? " — " + esc(s.settled_at_fa) : ""}</span>`
      : '<span class="badge amber plain">در انتظار تسویه</span>'],
  ],
};

function showSaleDetail(s) {
  currentDetail = s;
  const [pColor, pLabel] = PAYMENT_BADGE[s.payment_type] || ["gray", s.payment_type];
  const name = s.product_name || "محصول حذف‌شده";

  // تصویر ساعت (کلیک روی آن لایت‌باکس سراسری را باز می‌کند) + نام
  const head = `
    <div class="sd-header">
      ${s.product_image
        ? `<img class="thumb sd-thumb" src="/data/images/${encodeURIComponent(s.product_image)}" alt="" loading="lazy">`
        : `<span class="thumb sd-thumb"><svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="6.4"/><path d="M12 9.2V12l2.1 1.5"/></svg></span>`}
      <div class="sd-head-text">
        <h4 class="sd-name">${esc(name)}</h4>
      </div>
    </div>`;

  const saleTiles = (SD_SALE_TILES[s.payment_type] || SD_SALE_TILES.cash)(s, pColor, pLabel);
  if (s.notes && String(s.notes).trim()) {
    saleTiles.push(["یادداشت", esc(s.notes), "sd-notes", true]);
  }

  $("#sale-detail-body").innerHTML =
    head +
    sdCard("اطلاعات ساعت", SD_INFO_TILES(s)) +
    sdCard("اطلاعات فروش", saleTiles);
  openModal("modal-sale-detail");
}

/* ------------------------------------------------ ویرایش فروش */

function openEditModal(s) {
  editingSaleId = s.id;
  const form = $("#sale-edit-form");
  form.reset();
  form.querySelector('[name="sale_price"]').value = s.sale_price ? faNum(Number(s.sale_price).toLocaleString("en-US")) : "";
  form.querySelector('[name="paid_amount"]').value = s.paid_amount ? faNum(Number(s.paid_amount).toLocaleString("en-US")) : "";
  form.querySelector('[name="customer"]').value = s.customer || "";
  form.querySelector('[name="customer_phone"]').value = s.customer_phone || "";
  form.querySelector('[name="sale_date"]').value = jFromIso(s.sale_date);
  form.querySelector('[name="sale_type"]').value = s.sale_type || "person";
  form.querySelector('[name="notes"]').value = s.notes || "";
  form.querySelector('[name="payment_type"]').value = s.payment_type || "cash";
  $$("#edit-payment-chips .chip").forEach((c) =>
    c.classList.toggle("active", c.dataset.pay === (s.payment_type || "cash")));
  // مبلغ پرداخت فقط برای بیعانه نمایش داده شود
  const paidField = $("#edit-paid-amount-field");
  if (s.payment_type === "deposit") {
    paidField.classList.remove("hidden");
  } else {
    paidField.classList.add("hidden");
  }
  // اعتباری: نمایش فیلدهای سرویس و کد رهگیری
  const creditField = $("#edit-credit-fields");
  if (s.payment_type === "credit") {
    creditField.classList.remove("hidden");
    const provider = s.credit_provider || "";
    form.querySelector("[name='credit_provider']").value = provider;
    $$("#edit-credit-provider-chips .chip").forEach((c) =>
      c.classList.toggle("active", c.dataset.provider === provider));
    $("#edit-credit-fields [name='credit_tracking_code']").value = s.credit_tracking_code_raw || s.credit_tracking_code || "";
  } else {
    creditField.classList.add("hidden");
    form.querySelector("[name='credit_provider']").value = "";
  }
  // Disable cross-switching between deposit and credit
  const editDepositChip = $('#edit-payment-chips [data-pay="deposit"]');
  const editCreditChip = $('#edit-payment-chips [data-pay="credit"]');
  if (s.payment_type === "credit") {
    editDepositChip.disabled = true;
    editDepositChip.title = "تغییر مستقیم بین بیعانه و اعتباری ممکن نیست";
  } else {
    editDepositChip.disabled = false;
    editDepositChip.title = "";
  }
  if (s.payment_type === "deposit") {
    editCreditChip.disabled = true;
    editCreditChip.title = "تغییر مستقیم بین بیعانه و اعتباری ممکن نیست";
  } else {
    editCreditChip.disabled = false;
    editCreditChip.title = "";
  }
  updateSaleEditHints();
  openModal("modal-sale-edit");
}

$("#edit-payment-chips").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  $$("#edit-payment-chips .chip").forEach((c) => c.classList.toggle("active", c === chip));
  $("#sale-edit-form [name='payment_type']").value = chip.dataset.pay;
  const paidField = $("#edit-paid-amount-field");
  if (chip.dataset.pay === "deposit") {
    paidField.classList.remove("hidden");
  } else {
    paidField.classList.add("hidden");
  }
  // reset credit chips when switching away from credit
  if (chip.dataset.pay !== "credit") {
    $$("#edit-credit-provider-chips .chip").forEach((c) => c.classList.remove("active"));
    $("#edit-credit-provider-chips").removeAttribute("role");
    $("#sale-edit-form [name='credit_provider']").value = "";
    const ep = $("#sale-edit-form .code-preview");
    if (ep) ep.style.display = "none";
  }
  const creditField = $("#edit-credit-fields");
  if (chip.dataset.pay === "credit") {
    creditField.classList.remove("hidden");
  } else {
    creditField.classList.add("hidden");
  }
  updateSaleEditHints();
});

/* credit provider chips (edit form) — registered once, not inside the payment-chip listener */
$("#edit-credit-provider-chips").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  $$("#edit-credit-provider-chips .chip").forEach((c) => {
    const active = c === chip;
    c.classList.toggle("active", active);
    c.setAttribute("role", "radio");
    c.setAttribute("aria-checked", String(active));
  });
  $("#edit-credit-provider-chips").setAttribute("role", "radiogroup");
  $("#sale-edit-form [name='credit_provider']").value = chip.dataset.provider;
  updateCreditPreview("sale-edit-form");
});

$("#sale-edit-form [name='credit_tracking_code']").addEventListener("input", (e) => {
  updateCreditPreview("sale-edit-form");
});

/* A4: warn when a cash sale would be saved with a partial breakdown */
function updateSaleEditHints() {
  const form = $("#sale-edit-form");
  const paidHint = $("#sale-edit-paid-hint");
  const creditHint = $("#sale-edit-credit-hint");
  if (!paidHint || !creditHint) return;
  const type = form.querySelector('[name="payment_type"]').value;
  const num = (v) => +toEnDigits(v || "").replace(/[^\d]/g, "") || 0;
  const total = num(form.querySelector('[name="sale_price"]').value);
  const paid = num(form.querySelector('[name="paid_amount"]').value);
  // #sale-edit-paid-hint lives inside #edit-paid-amount-field, which is hidden
  // for credit sales, so the credit hint goes to the visible credit block.
  if (type === "credit") {
    creditHint.textContent = "مثل تسویه کامل ثبت می‌شود؛ سرویس انتخاب‌شده مبلغ را به فروشگاه پرداخت می‌کند و مشتری اقساط را با خود سرویس تسویه می‌کند. این فروش در صفحه‌ی پرداخت‌ها نمی‌آید.";
    creditHint.style.color = "";
    paidHint.textContent = "";
    paidHint.style.color = "";
  } else {
    creditHint.textContent = "";
    creditHint.style.color = "";
    if (type === "cash" && paid > 0 && paid < total - 0.001) {
      paidHint.textContent = "برای فروش نقدی جمع پرداخت‌ها باید برابر قیمت فروش باشد؛ برای پرداخت ناقص «بیعانه» را انتخاب کنید";
      paidHint.style.color = "var(--red)";
    } else if (paid > 0) {
      paidHint.textContent = `جمع پرداخت‌ها: ${faMoney(paid)} تومان${type === "deposit" ? ` — مانده: ${faMoney(Math.max(0, total - paid))} تومان` : ""}`;
      paidHint.style.color = "";
    } else {
      paidHint.textContent = "";
      paidHint.style.color = "";
    }
  }
}

["sale_price", "paid_amount"].forEach((name) => {
  $("#sale-edit-form").querySelector(`[name="${name}"]`)
    .addEventListener("input", updateSaleEditHints);
});

$("#btn-save-edit").addEventListener("click", async () => {
  const form = $("#sale-edit-form");
  const btn = $("#btn-save-edit");
  if (!form.reportValidity()) return;
  const payload = {};
  new FormData(form).forEach((v, k) => { payload[k] = v; });
  ["sale_price", "paid_amount"].forEach((k) => {
    payload[k] = toEnDigits(payload[k] || "0").replace(/[^\d]/g, "") || "0";
  });
  payload.customer_phone = toEnDigits(payload.customer_phone || "").trim();
  const type = form.querySelector('[name="payment_type"]').value;
  if (type === "deposit") {
    const paidNow = +payload.paid_amount || 0;
    const salePrice = +payload.sale_price || 0;
    if (paidNow < 1) {
      toast("برای فروش بیعانه، دست‌کم مبلغ بیعانه را وارد کنید", "error");
      btn.disabled = false;
      return;
    }
    if (salePrice > 0 && paidNow >= salePrice - 0.001) {
      toast("مبلغ بیعانه نمی‌تواند برابر یا بیشتر از قیمت فروش باشد؛ برای تسویه کامل «نقدی» را انتخاب کنید", "error");
      btn.disabled = false;
      return;
    }
    payload.deposit_amount = payload.paid_amount;
    delete payload.paid_amount;
  } else if (type === "credit") {
    const cp = form.querySelector("[name='credit_provider']").value;
    const ct = form.querySelector("[name='credit_tracking_code']").value.trim();
    if (!cp) { toast("سرویس اعتباری را انتخاب کنید", "error"); btn.disabled = false; return; }
    if (!ct) { toast("کد رهگیری پرداخت را وارد کنید", "error"); btn.disabled = false; return; }
    payload.credit_provider = cp;
    payload.credit_tracking_code = ct;
    delete payload.paid_amount;
  } else {
    delete payload.paid_amount;
  }
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
["#filter-sale-type", "#filter-payment", "#filter-credit-service", "#sort-by", "#sort-dir"].forEach((sel) => {
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
  $("#filter-credit-service").value = "";
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
