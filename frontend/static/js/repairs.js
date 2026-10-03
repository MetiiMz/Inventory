/* ============================================================
   صفحه‌ی تعمیرات — ثبت، ویرایش، تغییر وضعیت، حذف تکی/گروهی
   ============================================================ */

"use strict";

const STATUS_STEPS = [
  ["received", "دریافت شد"],
  ["in_progress", "تعمیر"],
  ["waiting_parts", "قطعه"],
  ["done", "آماده تحویل"],
  ["delivered", "تحویل شد"],
];
const STATUS_BADGE = {
  received: ["blue", "دریافت شده"],
  in_progress: ["amber", "در حال تعمیر"],
  waiting_parts: ["purple", "انتظار قطعه"],
  done: ["green", "آماده تحویل"],
  delivered: ["gray", "تحویل شده"],
};

let allRepairs = [];
let currentStatus = "";
let editingRepairId = null;
let deletingRepairId = null;
const selectedRepairIds = new Set();

async function loadRepairs() {
  try {
    allRepairs = await api("/api/repairs");
    // پاک‌کردن شناسه‌هایی که دیگر وجود ندارند
    const ids = new Set(allRepairs.map((r) => r.id));
    [...selectedRepairIds].forEach((id) => { if (!ids.has(id)) selectedRepairIds.delete(id); });
    render();
  } catch (err) {
    toast(err.message, "error");
  }
}

function filtered() {
  const q = toEnDigits($("#search").value.trim()).toLowerCase();
  return allRepairs.filter((r) => {
    if (currentStatus && r.status !== currentStatus) return false;
    if (!q) return true;
    return [r.watch_name, r.watch_code, r.customer_name, r.customer_phone]
      .some((v) => String(v || "").toLowerCase().includes(q));
  });
}

function render() {
  const grid = $("#repairs-grid");
  const list = filtered();

  $$("#status-tabs .chip").forEach((c) =>
    c.classList.toggle("active", c.dataset.status === currentStatus));

  if (!list.length) {
    grid.innerHTML = "";
    $("#repairs-empty").classList.remove("hidden");
    updateBulkBar();
    return;
  }
  $("#repairs-empty").classList.add("hidden");

  grid.innerHTML = list.map((r) => {
    const [color, label] = STATUS_BADGE[r.status] || ["gray", r.status];
    const stepIdx = STATUS_STEPS.findIndex(([k]) => k === r.status);
    const steps = STATUS_STEPS.map(([key, text], i) =>
      `<button class="step-btn ${i === stepIdx ? "current" : ""}" data-rid="${r.id}" data-status="${key}" ${i === stepIdx ? "disabled" : ""}>${text}</button>`
    ).join("");
    const checked = selectedRepairIds.has(r.id) ? "checked" : "";
    return `
    <article class="entity-card glass ${checked ? 'row-selected' : ''}" data-id="${r.id}">
      <div class="ec-top">
        <input type="checkbox" class="row-check" data-id="${r.id}" ${checked}
               style="accent-color:var(--accent);width:16px;height:16px;cursor:pointer;flex:0 0 auto;margin-top:4px">
        ${r.image
          ? `<img class="ec-thumb" src="/data/images/${encodeURIComponent(r.image)}" alt="" loading="lazy">`
          : `<span class="ec-thumb"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="6.4"/><path d="M12 9.2V12l2.1 1.5"/></svg></span>`}
        <div class="li-main">
          <div class="ec-title">${esc(r.watch_name)}</div>
          ${r.watch_code ? `<div class="ec-sub code-pill">${esc(r.watch_code)}</div>` : ""}
          <div class="ec-badges">
            <span class="badge ${color}">${label}</span>
            ${r.is_warranty ? '<span class="badge blue">گارانتی</span>' : '<span class="badge gray plain">بدون گارانتی</span>'}
          </div>
        </div>
      </div>
      <div class="ec-body">
        <div class="ec-row"><span class="k">مشتری</span><span class="v">${esc(r.customer_name) || "—"}</span></div>
        <div class="ec-row"><span class="k">تماس</span><span class="v" dir="ltr">${esc(r.customer_phone) || "—"}</span></div>
        <div class="ec-row"><span class="k">تاریخ دریافت</span><span class="v">${r.delivery_date_fa || "—"}</span></div>
        ${r.return_date ? `<div class="ec-row"><span class="k">بازگشت به مشتری</span><span class="v" style="color:var(--green)">${r.return_date_fa}</span></div>` : ""}
        ${r.repair_price ? `<div class="ec-row"><span class="k">هزینه تعمیر</span><span class="v">${r.repair_price_display} تومان</span></div>` : ""}
        ${r.issue ? `<div class="ec-row" style="align-items:flex-start"><span class="k">ایراد</span><span class="v" style="font-weight:500;text-align:left;line-height:1.5">${esc(r.issue)}</span></div>` : ""}
        ${r.notes ? `<div class="ec-row" style="align-items:flex-start"><span class="k">یادداشت</span><span class="v" style="font-weight:500;text-align:left;line-height:1.5">${esc(r.notes)}</span></div>` : ""}
      </div>
      <div class="ec-foot">
        <div class="stepper grow">${steps}</div>
        <button class="btn btn-icon btn-sm" data-act="edit" title="ویرایش">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m14.5 5.5 4 4L8 20H4v-4z"/><path d="m12.5 7.5 4 4"/></svg>
        </button>
        <button class="btn btn-icon btn-sm btn-danger" data-act="delete" title="حذف">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 6.5h15M9.5 6V4.8A1.3 1.3 0 0 1 10.8 3.5h2.4a1.3 1.3 0 0 1 1.3 1.3V6M6.5 6.5l1 13h9l1-13"/></svg>
        </button>
      </div>
    </article>`;
  }).join("");
  updateBulkBar();
}

function updateBulkBar() {
  const bar = $("#bulk-bar");
  if (!selectedRepairIds.size) {
    bar.classList.add("hidden");
    return;
  }
  bar.classList.remove("hidden");
  $("#bulk-count").textContent = `${faNum(selectedRepairIds.size)} مورد انتخاب شده`;
}

$("#repairs-grid").addEventListener("change", (e) => {
  const check = e.target.closest(".row-check");
  if (!check) return;
  const id = +check.dataset.id;
  if (check.checked) selectedRepairIds.add(id);
  else selectedRepairIds.delete(id);
  check.closest("[data-id]").classList.toggle("row-selected", check.checked);
  updateBulkBar();
});

$("#repairs-grid").addEventListener("click", async (e) => {
  const stepBtn = e.target.closest(".step-btn");
  if (stepBtn && !stepBtn.disabled) {
    try {
      await api(`/api/repairs/${stepBtn.dataset.rid}/status`, {
        method: "POST",
        body: { status: stepBtn.dataset.status },
      });
      toast(stepBtn.dataset.status === "delivered"
        ? "تحویل شد — تاریخ بازگشت امروز ثبت شد"
        : "وضعیت به‌روزرسانی شد");
      loadRepairs();
    } catch (err) {
      toast(err.message, "error");
    }
    return;
  }

  const actBtn = e.target.closest("[data-act]");
  if (!actBtn) return;
  const card = actBtn.closest("[data-id]");
  const r = allRepairs.find((x) => x.id === +card.dataset.id);
  if (!r) return;
  if (actBtn.dataset.act === "edit") openRepairModal(r);
  if (actBtn.dataset.act === "delete") {
    deletingRepairId = r.id;
    $("#delete-repair-name").textContent = `«${r.watch_name}» — ${r.customer_name}`;
    openModal("modal-delete-repair");
  }
});

function openRepairModal(r = null) {
  editingRepairId = r ? r.id : null;
  const form = $("#repair-form");
  form.reset();
  $("#repair-modal-title").textContent = r ? "ویرایش پرونده تعمیر" : "ثبت ساعت تعمیری";

  const wrap = $("#modal-repair .img-upload");
  wrap.dataset.ready = "";
  wrap.querySelector('input[type="hidden"]').value = r ? r.image || "" : "";

  form.querySelector('[name="watch_name"]').value = r?.watch_name || "";
  form.querySelector('[name="watch_code"]').value = r?.watch_code || "";
  form.querySelector('[name="issue"]').value = r?.issue || "";
  form.querySelector('[name="delivery_date"]').value = r?.delivery_date
    ? jFromIso(r.delivery_date) : todayJalaliStr();
  form.querySelector('[name="return_date"]').value = r?.return_date
    ? jFromIso(r.return_date) : "";
  form.querySelector('[name="customer_name"]').value = r?.customer_name || "";
  form.querySelector('[name="customer_phone"]').value = r?.customer_phone || "";
  form.querySelector('[name="repair_price"]').value = r?.repair_price
    ? faNum(Number(r.repair_price).toLocaleString("en-US")).replace(/,/g, "٬") : "";
  form.querySelector('[name="status"]').value = r?.status || "received";
  form.querySelector('[name="notes"]').value = r?.notes || "";

  const sw = $("#warranty-switch");
  sw.classList.toggle("on", !!(r && r.is_warranty));
  sw.setAttribute("aria-checked", sw.classList.contains("on") ? "true" : "false");

  document.dispatchEvent(new CustomEvent("modal:opened", { detail: { root: $("#modal-repair") } }));
  openModal("modal-repair");
}

$("#btn-save-repair").addEventListener("click", async () => {
  const form = $("#repair-form");
  if (!form.reportValidity()) return;
  const fd = new FormData(form);
  const payload = {};
  for (const [k, v] of fd.entries()) payload[k] = v;
  payload.is_warranty = $("#warranty-switch").classList.contains("on");
  payload.repair_price = toEnDigits(payload.repair_price || "0").replace(/[^\d]/g, "") || "0";
  payload.customer_phone = toEnDigits(payload.customer_phone || "").trim();

  const btn = $("#btn-save-repair");
  btn.disabled = true;
  try {
    if (editingRepairId) {
      await api(`/api/repairs/${editingRepairId}`, { method: "PUT", body: payload });
      toast("پرونده تعمیر به‌روزرسانی شد");
    } else {
      await api("/api/repairs", { method: "POST", body: payload });
      toast("ساعت تعمیری ثبت شد");
    }
    closeModal("modal-repair");
    loadRepairs();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

$("#btn-new").addEventListener("click", () => openRepairModal());

$("#btn-confirm-delete").addEventListener("click", async () => {
  if (!deletingRepairId) return;
  try {
    await api(`/api/repairs/${deletingRepairId}`, { method: "DELETE" });
    toast("پرونده حذف شد");
    closeModal("modal-delete-repair");
    loadRepairs();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    deletingRepairId = null;
  }
});

/* ------------------------------------------------ حذف گروهی */

$("#btn-bulk-delete").addEventListener("click", () => {
  if (!selectedRepairIds.size) return;
  $("#delete-bulk-count").textContent = faNum(selectedRepairIds.size) + " پرونده";
  openModal("modal-delete-bulk");
});

$("#btn-confirm-bulk-delete").addEventListener("click", async () => {
  const btn = $("#btn-confirm-bulk-delete");
  btn.disabled = true;
  try {
    const res = await api("/api/repairs/bulk-delete", {
      method: "POST",
      body: { ids: [...selectedRepairIds] },
    });
    toast(`${faNum(res.deleted)} پرونده حذف شد`);
    selectedRepairIds.clear();
    closeModal("modal-delete-bulk");
    loadRepairs();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

$("#btn-bulk-clear").addEventListener("click", () => {
  selectedRepairIds.clear();
  render();
});

/* ------------------------------------------------ جستجو و فیلتر */

let searchTimer;
$("#search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(render, 140);
});

$("#status-tabs").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  currentStatus = chip.dataset.status;
  render();
});

$("#btn-export").addEventListener("click", () => {
  const a = document.createElement("a");
  a.href = "/export/repairs.xlsx";
  document.body.appendChild(a);
  a.click();
  a.remove();
});

document.addEventListener("DOMContentLoaded", () => {
  bindMoneyInput(document.querySelector('#repair-form [name="repair_price"]'));
  loadRepairs();
});
