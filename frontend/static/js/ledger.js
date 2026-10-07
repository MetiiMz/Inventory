/* ============================================================
   صفحه‌ی حساب معین — بایگانی فاکتورهای خرید از تأمین‌کننده‌ها
   ============================================================ */

"use strict";

let ledgerSuppliers = [];    // {id, name, invoice_count}
let openSupplierId = null;   // تأمین‌کننده‌ی باز در آکاردئون (فقط یکی)
let invoiceCache = {};       // supplierId -> سطرهای خلاصه‌ی فاکتور
let detailData = null;       // فاکتورِ باز در مودال جزئیات (شکل کامل)
let detailPhotos = [];       // ترتیب عکس‌ها در مودال جزئیات
let detailDateChanged = false;
let newInvoicePhotos = [];   // ترتیب عکس‌ها در فرم فاکتور جدید
let editingSupplierId = null;
let deletingInvoiceId = null;
let deletingInvoiceSupplierId = null;
let deletingSupplierId = null;
let supplierQuery = "";  // جستجوی نام تأمین‌کننده
let dateFrom = "";       // فیلتر تاریخ فاکتور — از (شمسی/میلادی)
let dateTo = "";         // فیلتر تاریخ فاکتور — تا
let detailViewMode = true; // true = view mode, false = edit mode

const IMG_SVG = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="1.8"/><path d="m5 19 5.2-5.4a1.6 1.6 0 0 1 2.3 0L19 19"/></svg>';
const PEN_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m14.5 5.5 4 4L8 20H4v-4z"/><path d="m12.5 7.5 4 4"/></svg>';
const TRASH_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 6.5h15M9.5 6V4.8A1.3 1.3 0 0 1 10.8 3.5h2.4a1.3 1.3 0 0 1 1.3 1.3V6M6.5 6.5l1 13h9l1-13"/></svg>';

const digitsOnly = (s) => toEnDigits(s).replace(/\D/g, "");

/* Format number with thousand separators (Persian digits) */
function formatNumberWithSeparators(numStr) {
  const digits = toEnDigits(numStr).replace(/\D/g, "");
  if (!digits) return "";
  return faNum(Number(digits).toLocaleString());
}

/* Parse formatted number back to plain digits */
function parseFormattedNumber(formatted) {
  return toEnDigits(formatted).replace(/[,\u066C]/g, "").replace(/\D/g, "");
}

/* فرمت زنده‌ی عدد با جداکننده‌ی هزارگان هنگام تایپ (حفظ موقعیت کرسر) */
function formatPriceLive(input) {
  const raw = toEnDigits(input.value).replace(/\D/g, "");
  if (!raw) { input.value = ""; return; }
  const sel = input.selectionStart ?? input.value.length;
  const digitsBefore = toEnDigits(input.value.slice(0, sel)).replace(/\D/g, "").length;
  const grouped = faNum(raw.replace(/\B(?=(\d{3})+(?!\d))/g, ","));
  input.value = grouped;
  /* کرسر را بعد از همان تعداد رقمِ قبل از ویرایش برگردان */
  let pos = 0, count = 0;
  while (pos < grouped.length && count < digitsBefore) {
    if (/\d/.test(toEnDigits(grouped[pos]))) count++;
    pos++;
  }
  try { input.setSelectionRange(pos, pos); } catch { /* noop */ }
}

/* اتصال فرمت‌کننده‌ی زنده به ورودی قیمت */
function bindPriceFormatter(input) {
  if (!input || input.dataset.priceFormatted) return;
  input.dataset.priceFormatted = "1";
  input.addEventListener("input", () => formatPriceLive(input));
  input.addEventListener("blur", () => {
    input.value = formatNumberWithSeparators(input.value);
  });
}

/* ------------------------------------- بارگذاری تأمین‌کننده‌ها و فاکتورها */

async function loadSuppliers() {
  try {
    ledgerSuppliers = (await api("/api/ledger/suppliers")).items;
    if (openSupplierId !== null) {
      if (supplierById(openSupplierId)) {
        try {
          await ensureInvoices(openSupplierId);   // ensureInvoices is a no-op if cached
        } catch (err) {
          toast(err.message, "error");
          openSupplierId = null;
        }
      } else {
        openSupplierId = null;                   // supplier no longer exists
      }
    }
    renderSuppliers();
  } catch (err) {
    toast(err.message, "error");
  }
}

function supplierById(id) {
  return ledgerSuppliers.find((s) => s.id === id);
}

async function ensureInvoices(supplierId) {
  if (invoiceCache[supplierId]) return;
  let url = `/api/ledger/invoices?supplier_id=${supplierId}`;
  if (dateFrom) url += `&date_from=${encodeURIComponent(dateFrom)}`;
  if (dateTo) url += `&date_to=${encodeURIComponent(dateTo)}`;
  const data = await api(url);
  invoiceCache[supplierId] = data.items;
}

function invoiceRowHtml(inv) {
  const imgs = inv.images || [];
  const rest = imgs.length - 1;
  const thumb = imgs.length
    ? `<span class="ledger-invoice-thumb" data-thumb="${inv.id}"><img src="/data/images/${encodeURIComponent(imgs[0])}" alt="" loading="lazy">${rest > 0 ? `<span class="thumb-plus">+${faNum(rest)}</span>` : ""}</span>`
    : `<span class="ledger-invoice-thumb" data-thumb="${inv.id}">${IMG_SVG}</span>`;
  return `
  <div class="ledger-invoice" data-invoice="${inv.id}" data-supplier="${inv.supplier_id}">
    ${thumb}
    <div class="ledger-invoice-main">
      <div class="ledger-invoice-date">${esc(inv.purchase_date_fa || "—")}</div>
      <div class="ledger-invoice-total">${esc(inv.total_amount_display)} تومان — ${faNum(inv.total_quantity || 0)} عدد</div>
    </div>
    <div class="ledger-invoice-actions">
      <button class="btn btn-icon btn-sm" data-row-act="edit" data-id="${inv.id}" title="ویرایش">${PEN_SVG}</button>
      <button class="btn btn-icon btn-sm btn-danger" data-row-act="delete" data-id="${inv.id}" title="حذف">${TRASH_SVG}</button>
    </div>
  </div>`;
}

function renderSuppliers() {
  const list = $("#ledger-list");
  const empty = $("#ledger-empty");
  if (!ledgerSuppliers.length) {
    list.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");
  const q = supplierQuery.trim().toLowerCase();
  const visible = ledgerSuppliers.filter(
    (s) => !q || s.name.trim().toLowerCase().includes(q));
  if (!visible.length) {
    list.innerHTML = '<div class="li-sub ledger-no-match">تأمین‌کننده‌ای با این نام پیدا نشد</div>';
    return;
  }
  list.innerHTML = visible.map((s) => {
    const open = s.id === openSupplierId;
    const rows = invoiceCache[s.id] || [];
    return `
    <div class="ledger-supplier ${open ? "open" : ""}" data-supplier="${s.id}">
      <div class="ledger-supplier-head" data-supplier-head="${s.id}">
        <svg class="ledger-supplier-caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m9.5 6 6 6-6 6"/></svg>
        <span class="ledger-supplier-name">${esc(s.name)}</span>
        <span class="badge blue plain ledger-supplier-count">${faNum(s.invoice_count)} فاکتور</span>
        <span class="ledger-actions">
          <button class="btn btn-icon btn-sm" data-act="rename-supplier" data-id="${s.id}" title="تغییر نام">${PEN_SVG}</button>
          <button class="btn btn-icon btn-sm btn-danger" data-act="delete-supplier" data-id="${s.id}" title="حذف">${TRASH_SVG}</button>
        </span>
      </div>
      ${open ? `
      <div class="ledger-invoices" data-invoices="${s.id}">
        <button class="btn btn-sm" style="margin:6px 0" data-act="new-invoice" data-id="${s.id}">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5.5v13M5.5 12h13"/></svg>
          فاکتور جدید
        </button>
        ${rows.map(invoiceRowHtml).join("")
          || (dateFrom || dateTo
              ? '<div class="li-sub" style="padding:8px 4px">فاکتوری در بازه‌ی تاریخ انتخابی ثبت نشده</div>'
              : '<div class="li-sub" style="padding:8px 4px">فاکتوری برای این تأمین‌کننده ثبت نشده</div>')}
      </div>` : ""}
    </div>`;
  }).join("");
}


/* --------------------------------------------- آکاردئون (فقط یکی باز) */

async function toggleSupplier(id) {
  if (openSupplierId === id) {
    openSupplierId = null;
    renderSuppliers();
    return;
  }
  openSupplierId = id;
  try {
    await ensureInvoices(id);
  } catch (err) {
    openSupplierId = null;
    toast(err.message, "error");
  }
  renderSuppliers();
}


/* --------------------------------------------- آکاردئون (فقط یکی باز) */

$("#ledger-list").addEventListener("click", (e) => {
  /* دکمه‌های داخل سطر فاکتور */
  const rowBtn = e.target.closest("[data-row-act]");
  if (rowBtn) {
    const id = +rowBtn.dataset.id;
    if (rowBtn.dataset.rowAct === "edit") openInvoiceDetail(id);
    else if (rowBtn.dataset.rowAct === "delete") {
      const supplierId = +rowBtn.closest(".ledger-invoice").dataset.supplier;
      openDeleteInvoice(id, supplierId);
    }
    return;
  }
  /* کلیدهای سرتیتر تأمین‌کننده */
  const act = e.target.closest("[data-act]");
  if (act) {
    e.stopPropagation();
    const id = +act.dataset.id;
    if (act.dataset.act === "new-invoice") openInvoiceModal(id);
    else if (act.dataset.act === "rename-supplier") openSupplierModal(supplierById(id));
    else if (act.dataset.act === "delete-supplier") openDeleteSupplier(supplierById(id));
    return;
  }
  /* کلیک روی عکس سطر → نمایش تمام‌قد اولین عکس */
  const thumb = e.target.closest("[data-thumb]");
  if (thumb) {
    const invEl = thumb.closest(".ledger-invoice");
    const supplierId = invEl ? +invEl.dataset.supplier : null;
    const inv = supplierId
      ? (invoiceCache[supplierId] || []).find((x) => x.id === +thumb.dataset.thumb)
      : null;
    if (inv && inv.images && inv.images.length) showImageFull(inv.images[0], inv.images);
    return;
  }
  /* کلیک روی بدنه‌ی سطر → مودال جزئیات/ویرایش */
  const row = e.target.closest(".ledger-invoice");
  if (row) { openInvoiceDetail(+row.dataset.invoice); return; }
  /* کلیک روی سرتیتر → باز/بسته‌کردن آکاردئون */
  const head = e.target.closest("[data-supplier-head]");
  if (head) toggleSupplier(+head.dataset.supplierHead);
});

/* ------------------------------------------------ مودال تأمین‌کننده */

function openSupplierModal(s = null) {
  editingSupplierId = s ? s.id : null;
  $("#supplier-modal-title").textContent = s ? "تغییر نام تأمین‌کننده" : "تأمین‌کننده‌ی جدید";
  $("#supplier-name").value = s ? s.name : "";
  openModal("modal-supplier");
  setTimeout(() => $("#supplier-name").focus(), 80);
}

$("#supplier-name").addEventListener("keydown", (e) => {
  if (e.key === "Enter") saveSupplier();
});

$("#btn-save-supplier").addEventListener("click", saveSupplier);

async function saveSupplier() {
  const name = $("#supplier-name").value.trim();
  if (!name) { toast("نام تأمین‌کننده را وارد کنید", "error"); return; }
  const btn = $("#btn-save-supplier");
  btn.disabled = true;
  try {
    if (editingSupplierId) {
      await api(`/api/ledger/suppliers/${editingSupplierId}`, {
        method: "PUT", body: { name },
      });
      toast("نام تأمین‌کننده تغییر کرد");
      delete invoiceCache[editingSupplierId];
    } else {
      await api("/api/ledger/suppliers", { method: "POST", body: { name } });
      toast("تأمین‌کننده ثبت شد");
    }
    closeModal("modal-supplier");
    await loadSuppliers();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
}

/* --------------------------------------------- عکس‌های فرم (افزودن/حذف/جابه‌جایی) */

function renderPhotos(container, photos) {
  container.innerHTML = photos.map((f, i) => `
    <div class="photo-item" data-idx="${i}">
      <img src="/data/images/${encodeURIComponent(f)}" alt="">
      <span class="photo-item-tools">
        <button type="button" data-photo="up" title="یک پله جلوتر" ${i === 0 ? "disabled" : ""}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m6 14.5 6-6 6 6"/></svg>
        </button>
        <button type="button" data-photo="down" title="یک پله عقب‌تر" ${i === photos.length - 1 ? "disabled" : ""}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9.5 6 6 6-6"/></svg>
        </button>
      </span>
      <button type="button" class="photo-item-remove" data-photo="remove" title="حذف این عکس">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="m6.5 6.5 11 11m0-11-11 11"/></svg>
      </button>
    </div>`).join("");
}

function bindPhotoTools(container, photos) {
  container.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-photo]");
    if (!btn || btn.disabled) return;
    const idx = +btn.closest(".photo-item").dataset.idx;
    const kind = btn.dataset.photo;
    if (kind === "remove") photos.splice(idx, 1);
    else if (kind === "up" && idx > 0) [photos[idx - 1], photos[idx]] = [photos[idx], photos[idx - 1]];
    else if (kind === "down" && idx < photos.length - 1) [photos[idx], photos[idx + 1]] = [photos[idx + 1], photos[idx]];
    else return;
    renderPhotos(container, photos);
  });
}

function bindPhotoAdd(buttonEl, container, photos) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/*";
  input.hidden = true;
  buttonEl.appendChild(input);
  buttonEl.addEventListener("click", () => input.click());
  input.addEventListener("change", async () => {
    const file = input.files[0];
    input.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast("فقط فایل تصویری پذیرفته می‌شود", "error");
      return;
    }
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await api("/api/upload", { method: "POST", body: fd });
      photos.push(res.path);
      renderPhotos(container, photos);
      toast("عکس بارگذاری شد");
    } catch (err) {
      toast(err.message, "error");
    }
  });
}

/* -------------------------------------------- جدول خطوط فاکتور */

function addLineRow(tbody, data = {}) {
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input class="input" data-f="watch_name" type="text" maxlength="200" placeholder="نام ساعت" value="${esc(data.watch_name || "")}"></td>
    <td><input class="input" data-f="reference" type="text" maxlength="100" placeholder="رفرنس (اختیاری)" value="${esc(data.reference || "")}"></td>
    <td><input class="input" data-f="quantity" inputmode="numeric" placeholder="۱" value="${data.quantity ?? ""}"></td>
    <td><input class="input" data-f="unit_price" inputmode="numeric" placeholder="0" value="${data.unit_price ?? ""}"></td>
    <td class="cell-total">${faMoney(0)}</td>
    <td><button type="button" class="line-remove" title="حذف ردیف">${TRASH_SVG}</button></td>`;
  tbody.appendChild(tr);
  // Bind price formatter to unit_price input
  const priceInput = tr.querySelector('[data-f="unit_price"]');
  if (priceInput) bindPriceFormatter(priceInput);
}

function lineRowTotals(tbody) {
  let qty = 0;
  let amount = 0;
  for (const tr of tbody.querySelectorAll("tr")) {
    const q = parseFormattedNumber(tr.querySelector('[data-f="quantity"]').value);
    const p = parseFormattedNumber(tr.querySelector('[data-f="unit_price"]').value);
    const nq = q ? Number(q) : 1;
    const np = p ? Number(p) : 0;
    tr.querySelector(".cell-total").textContent = faMoney(nq * np);
    qty += nq;
    amount += nq * np;
  }
  return { qty, amount };
}

function bindLineTable(tbody, badge) {
  tbody.addEventListener("input", () => {
    const t = lineRowTotals(tbody);
    badge.textContent = t.amount > 0 ? `مجموع: ${faMoney(t.amount)} تومان` : "مجموع: —";
  });
  tbody.addEventListener("click", (e) => {
    const btn = e.target.closest(".line-remove");
    if (!btn) return;
    if (tbody.querySelectorAll("tr").length <= 1) {
      btn.closest("tr").querySelectorAll("input").forEach((i) => { i.value = ""; });
      lineRowTotals(tbody);
      return;
    }
    btn.closest("tr").remove();
    lineRowTotals(tbody);
  });
}

function readLines(tbody) {
  return [...tbody.querySelectorAll("tr")].map((tr) => ({
    watch_name: tr.querySelector('[data-f="watch_name"]').value.trim(),
    reference: tr.querySelector('[data-f="reference"]').value.trim(),
    quantity: parseFormattedNumber(tr.querySelector('[data-f="quantity"]').value),
    unit_price: parseFormattedNumber(tr.querySelector('[data-f="unit_price"]').value),
  }));
}

/* ------------------------------------------------- مودال فاکتور جدید */

function openInvoiceModal(supplierId) {
  const s = supplierById(supplierId);
  /* پرکشیِ در‌جا: آرایه‌ها در bindPhotoAdd/Tools به‌صورت مرجع گرفته شده‌اند */
  newInvoicePhotos.length = 0;
  detailDateChanged = false;
  $("#invoice-supplier-id").value = supplierId;
  $("#invoice-modal-title").textContent = `فاکتور جدید — ${s ? s.name : ""}`;
  $("#invoice-date").value = todayJalaliStr();
  renderPhotos($("#invoice-photo-items"), newInvoicePhotos);
  const tbody = $("#invoice-lines-body");
  tbody.innerHTML = "";
  addLineRow(tbody);
  $("#invoice-total-badge").textContent = "مجموع: —";
  openModal("modal-invoice");
}

$("#btn-new-supplier").addEventListener("click", () => openSupplierModal());
$("#btn-empty-new-supplier").addEventListener("click", () => openSupplierModal());

$("#btn-invoice-add-line").addEventListener("click", () => addLineRow($("#invoice-lines-body")));

bindPhotoTools($("#invoice-photo-items"), newInvoicePhotos);
bindPhotoAdd($("#btn-invoice-add-photo"), $("#invoice-photo-items"), newInvoicePhotos);
bindLineTable($("#invoice-lines-body"), $("#invoice-total-badge"));

$("#btn-save-invoice").addEventListener("click", async () => {
  const supplierId = +$("#invoice-supplier-id").value;
  const date = toEnDigits($("#invoice-date").value).replace(/[^0-9/]/g, "");
  if (!date) { toast("تاریخ خرید را وارد کنید", "error"); return; }
  const lines = readLines($("#invoice-lines-body"));
  for (const l of lines) {
    if (!l.watch_name) { toast("نام ساعت هر ردیف را وارد کنید", "error"); return; }
  }
  const btn = $("#btn-save-invoice");
  btn.disabled = true;
  try {
    await api("/api/ledger/invoices", {
      method: "POST",
      body: {
        supplier_id: supplierId,
        purchase_date: date,
        images: [...newInvoicePhotos],
        lines,
      },
    });
    toast("فاکتور ثبت شد");
    closeModal("modal-invoice");
    delete invoiceCache[supplierId];
    openSupplierId = supplierId;
    await loadSuppliers();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

/* ---------------------------------------------- نمایش تمام‌قد عکس */

/* Image viewer state */
let imgViewerPhotos = [];
let imgViewerIndex = 0;

function showImageFull(filename, photos = null) {
  if (photos) {
    imgViewerPhotos = photos;
    imgViewerIndex = photos.indexOf(filename);
  } else {
    // Single image fallback
    imgViewerPhotos = [filename];
    imgViewerIndex = 0;
  }
  updateImgViewer();
  openModal("modal-img-view");
}

function updateImgViewer() {
  const img = $("#img-view-src");
  img.src = `/data/images/${encodeURIComponent(imgViewerPhotos[imgViewerIndex])}`;
  $("#img-view-prev").disabled = imgViewerIndex === 0;
  $("#img-view-next").disabled = imgViewerIndex === imgViewerPhotos.length - 1;
}

function navigateImgViewer(delta) {
  imgViewerIndex = Math.max(0, Math.min(imgViewerPhotos.length - 1, imgViewerIndex + delta));
  updateImgViewer();
}

// Image viewer navigation
$("#img-view-prev").addEventListener("click", () => navigateImgViewer(-1));
$("#img-view-next").addEventListener("click", () => navigateImgViewer(1));

// Keyboard navigation for image viewer
document.addEventListener("keydown", (e) => {
  const modal = document.getElementById("modal-img-view");
  if (!modal || !modal.classList.contains("open")) return;
  if (e.key === "ArrowLeft") navigateImgViewer(-1);
  else if (e.key === "ArrowRight") navigateImgViewer(1);
  else if (e.key === "Escape") closeModal("modal-img-view");
});

/* ------------------------------------------------- مودال جزئیات/ویرایش */

function detailLineRowHtml(line, i) {
  return `
  <tr data-line="${i}">
    <td><input class="input" data-f="watch_name" type="text" maxlength="200" value="${esc(line.watch_name)}"></td>
    <td><input class="input" data-f="reference" type="text" maxlength="100" value="${esc(line.reference)}"></td>
    <td><input class="input" data-f="quantity" inputmode="numeric" value="${line.quantity}"></td>
    <td><input class="input" data-f="unit_price" inputmode="numeric" value="${line.unit_price}"></td>
    <td class="cell-total">${faMoney(line.quantity * line.unit_price)}</td>
    <td><button type="button" class="line-remove" title="حذف ردیف">${TRASH_SVG}</button></td>
  </tr>`;
}

/* Toggle detail modal between view and edit mode */
function setDetailViewMode(isView) {
  detailViewMode = isView;
  const tbody = $("#detail-lines-body");
  const inputs = tbody.querySelectorAll("input");
  const removeBtns = tbody.querySelectorAll(".line-remove");
  const addLineBtn = $("#btn-detail-add-line");
  const addPhotoBtn = $("#btn-detail-add-photo");
  const saveBtn = $("#btn-save-detail");
  const editBtn = $("#btn-edit-detail");
  const dateInput = $("#detail-date");
  const photoItems = $("#detail-photo-items");

  inputs.forEach(input => {
    input.readOnly = isView;
    if (isView) input.classList.add("readonly"); else input.classList.remove("readonly");
  });
  removeBtns.forEach(btn => btn.classList.toggle("hidden", isView));
  addLineBtn.classList.toggle("hidden", isView);
  addPhotoBtn.classList.toggle("hidden", isView);
  saveBtn.classList.toggle("hidden", isView);
  editBtn.classList.toggle("hidden", !isView); // Show edit in view mode, hide in edit mode
  dateInput.readOnly = isView;
  if (isView) dateInput.classList.add("readonly"); else dateInput.classList.remove("readonly");
  
  // Disable/enable photo reorder/remove in view mode
  photoItems.querySelectorAll("[data-photo]").forEach(btn => {
    btn.disabled = isView;
  });
}

async function openInvoiceDetail(invoiceId) {
  let data;
  try {
    data = (await api(`/api/ledger/invoices/${invoiceId}`)).invoice;
  } catch (err) {
    toast(err.message, "error");
    return;
  }
  detailData = data;
  /* پرکشیِ در‌جا: bindPhotoAdd/Tools به آرایه‌ی اولیه اشاره دارند */
  detailPhotos.length = 0;
  detailPhotos.push(...(data.images || []));
  detailDateChanged = false;

  $("#detail-invoice-id").value = data.id;
  const sup = supplierById(data.supplier_id);
  $("#detail-supplier-name").textContent = sup ? sup.name : "—";
  const date = $("#detail-date");
  date.value = data.purchase_date_fa || toEnDigits(data.purchase_date);
  date.dataset.orig = data.purchase_date;

  const tbody = $("#detail-lines-body");
  tbody.innerHTML = data.lines.map(detailLineRowHtml).join("");

  // Bind price formatter to unit_price inputs in detail modal + نمایش با جداکننده
  tbody.querySelectorAll('[data-f="unit_price"]').forEach((inp) => {
    bindPriceFormatter(inp);
    inp.value = formatNumberWithSeparators(inp.value);
  });

  renderPhotos($("#detail-photo-items"), detailPhotos);
  lineRowTotals(tbody);
  updateDetailTotals();

  // همیشه با حالت نمایش باز شود — بعد از پرشدن جدول
  setDetailViewMode(true);

  openModal("modal-invoice-detail");
}

function updateDetailTotals() {
  if (!detailData) return;
  const t = lineRowTotals($("#detail-lines-body"));
  $("#detail-total-qty").textContent = `${faNum(t.qty)} عدد`;
  $("#detail-total-amount").textContent = faMoney(t.amount);
}

$("#detail-date").addEventListener("input", () => {
  detailDateChanged = true;
});

/* در حالت نمایش، تقویم نباید باز شود */
$("#detail-date").addEventListener("click", (e) => {
  if (detailViewMode) e.stopImmediatePropagation();
}, true);

bindPhotoTools($("#detail-photo-items"), detailPhotos);
bindPhotoAdd($("#btn-detail-add-photo"), $("#detail-photo-items"), detailPhotos);

// Click on photo in detail modal to open full-size viewer with navigation
$("#detail-photo-items").addEventListener("click", (e) => {
  const img = e.target.closest(".photo-item img");
  if (img) {
    const idx = +img.closest(".photo-item").dataset.idx;
    showImageFull(detailPhotos[idx], detailPhotos);
  }
});

$("#btn-detail-add-line").addEventListener("click", () => {
  const tbody = $("#detail-lines-body");
  addLineRow(tbody);
  lineRowTotals(tbody);
  updateDetailTotals();
});

$("#img-view-src").addEventListener("click", () => closeModal("modal-img-view"));

/* ------------------------------------------------ شروع */


const detailBody = $("#detail-lines-body");
detailBody.addEventListener("input", () => {
  lineRowTotals(detailBody);
  updateDetailTotals();
});
detailBody.addEventListener("click", (e) => {
  const btn = e.target.closest(".line-remove");
  if (!btn) return;
  if (detailBody.querySelectorAll("tr").length <= 1) {
    btn.closest("tr").querySelectorAll("input").forEach((i) => { i.value = ""; });
    lineRowTotals(detailBody);
    updateDetailTotals();
    return;
  }
  btn.closest("tr").remove();
  lineRowTotals(detailBody);
  updateDetailTotals();
});

$("#btn-save-detail").addEventListener("click", async () => {
  const id = +$("#detail-invoice-id").value;
  const lines = readLines($("#detail-lines-body"));
  for (const l of lines) {
    if (!l.watch_name) { toast("نام ساعت هر ردیف را وارد کنید", "error"); return; }
  }
  let purchase_date;
  if (detailDateChanged) {
    purchase_date = toEnDigits($("#detail-date").value).replace(/[^0-9/]/g, "");
  } else {
    purchase_date = $("#detail-date").dataset.orig || undefined;
  }
  if (detailDateChanged && !purchase_date) {
    toast("تاریخ نامعتبر است", "error");
    return;
  }
  const payload = { lines, images: [...detailPhotos] };
  if (purchase_date) payload.purchase_date = purchase_date;
  const btn = $("#btn-save-detail");
  btn.disabled = true;
  try {
    await api(`/api/ledger/invoices/${id}`, { method: "PUT", body: payload });
    toast("تغییرات فاکتور ذخیره شد");
    const supplierId = detailData.supplier_id;
    closeModal("modal-invoice-detail");
    delete invoiceCache[supplierId];
    openSupplierId = supplierId;
    await loadSuppliers();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

// Edit button - switch to edit mode
$("#btn-edit-detail").addEventListener("click", () => {
  setDetailViewMode(false);
});

/* ------------------------------------------------ جستجو و فیلتر تاریخ */

$("#supplier-search").addEventListener("input", (e) => {
  supplierQuery = e.target.value;
  renderSuppliers();
});

function refreshWithFilters() {
  /* تاریخِ فیلتر عوض شد؛ کشِ فاکتورها را خالی کن و تازه بیاور */
  for (const k of Object.keys(invoiceCache)) delete invoiceCache[k];
  loadSuppliers();
}

$("#filter-date-from").addEventListener("change", (e) => { dateFrom = e.target.value.trim(); refreshWithFilters(); });
$("#filter-date-to").addEventListener("change", (e) => { dateTo = e.target.value.trim(); refreshWithFilters(); });

$("#filter-reset").addEventListener("click", () => {
  supplierQuery = ""; dateFrom = ""; dateTo = "";
  $("#supplier-search").value = "";
  $("#filter-date-from").value = "";
  $("#filter-date-to").value = "";
  refreshWithFilters();
});

loadSuppliers();

/* --------------------------------------------------- حذف‌ها */

function openDeleteInvoice(invoiceId, supplierId) {
  deletingInvoiceId = invoiceId;
  deletingInvoiceSupplierId = supplierId ? +supplierId : null;
  let label = "—";
  if (deletingInvoiceSupplierId !== null) {
    const row = (invoiceCache[deletingInvoiceSupplierId] || []).find((x) => x.id === invoiceId);
    if (row) {
      label = `${row.purchase_date_fa || "—"} — ${supplierById(deletingInvoiceSupplierId) ? supplierById(deletingInvoiceSupplierId).name : ""}`;
    }
  }
  if (deletingInvoiceSupplierId === null && detailData && detailData.id === invoiceId) {
    deletingInvoiceSupplierId = detailData.supplier_id;
  }
  $("#delete-invoice-name").textContent = label;
  openModal("modal-delete-invoice");
}

$("#btn-confirm-delete-invoice").addEventListener("click", async () => {
  const id = deletingInvoiceId;
  if (!id) return;
  const btn = $("#btn-confirm-delete-invoice");
  btn.disabled = true;
  try {
    await api(`/api/ledger/invoices/${id}`, { method: "DELETE" });
    toast("فاکتور حذف شد");
    const supplierId = deletingInvoiceSupplierId;
    if (supplierId) delete invoiceCache[supplierId];
    if (supplierId) openSupplierId = supplierId;
    await loadSuppliers();
    closeModal("modal-delete-invoice");
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

function openDeleteSupplier(s) {
  if (!s) return;
  deletingSupplierId = s.id;
  $("#delete-supplier-name").textContent = s.name;
  openModal("modal-delete-supplier");
}

$("#btn-confirm-delete-supplier").addEventListener("click", async () => {
  const id = deletingSupplierId;
  if (!id) return;
  const btn = $("#btn-confirm-delete-supplier");
  btn.disabled = true;
  try {
    await api(`/api/ledger/suppliers/${id}`, { method: "DELETE" });
    toast("تأمین‌کننده حذف شد");
    delete invoiceCache[id];
    if (openSupplierId === id) openSupplierId = null;
    await loadSuppliers();
    closeModal("modal-delete-supplier");
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

/* حذف فاکتور از مودال جزئیات */
$("#btn-detail-delete").addEventListener("click", () => {
  if (detailData) openDeleteInvoice(detailData.id, detailData.supplier_id);
});