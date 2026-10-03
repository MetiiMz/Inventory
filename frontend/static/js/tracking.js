/* ============================================================
   صفحه‌ی پیگیری سفارش‌ها — ساعت/قطعه‌ی درخواستی مشتری‌ها
   ============================================================ */

"use strict";

const TRACKING_BADGE = {
  new: ["blue", "جدید"],
  ordered: ["amber", "سفارش داده شد"],
  found: ["green", "پیدا شد"],
  delivered: ["gray", "تحویل شد"],
  cancelled: ["red", "لغو شد"],
};

let allTracking = [];
let currentStatus = "";
let editingTrackingId = null;
let deletingTrackingId = null;
const selectedTrackingIds = new Set();

async function loadTracking() {
  try {
    allTracking = await api("/api/tracking");
    const ids = new Set(allTracking.map((t) => t.id));
    [...selectedTrackingIds].forEach((id) => { if (!ids.has(id)) selectedTrackingIds.delete(id); });
    render();
  } catch (err) {
    toast(err.message, "error");
  }
}

function filtered() {
  const q = toEnDigits($("#search").value.trim()).toLowerCase();
  return allTracking.filter((t) => {
    if (currentStatus && t.status !== currentStatus) return false;
    if (!q) return true;
    return [t.item_name, t.item_code, t.customer_name, t.customer_phone]
      .some((v) => String(v || "").toLowerCase().includes(q));
  });
}

function render() {
  const grid = $("#tracking-grid");
  const list = filtered();

  $$("#status-tabs .chip").forEach((c) =>
    c.classList.toggle("active", c.dataset.status === currentStatus));

  if (!list.length) {
    grid.innerHTML = "";
    $("#tracking-empty").classList.remove("hidden");
    updateBulkBar();
    return;
  }
  $("#tracking-empty").classList.add("hidden");

  grid.innerHTML = list.map((t) => {
    const [color, label] = TRACKING_BADGE[t.status] || ["gray", t.status];
    const checked = selectedTrackingIds.has(t.id) ? "checked" : "";
    const steps = ["new", "ordered", "found", "delivered"]
      .filter((k) => k !== t.status || t.status === "delivered")
      .map((k) => {
        const [, text] = TRACKING_BADGE[k];
        return `<button class="step-btn ${k === t.status ? "current" : ""}" data-tid="${t.id}" data-status="${k}" ${k === t.status ? "disabled" : ""}>${text}</button>`;
      }).join("");
    return `
    <article class="entity-card glass ${checked ? 'row-selected' : ''}" data-id="${t.id}">
      <div class="ec-top">
        <input type="checkbox" class="row-check" data-id="${t.id}" ${checked}
               style="accent-color:var(--accent);width:16px;height:16px;cursor:pointer;flex:0 0 auto;margin-top:4px">
        ${t.image
          ? `<img class="ec-thumb" src="/data/images/${encodeURIComponent(t.image)}" alt="" loading="lazy">`
          : `<span class="ec-thumb"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20.5 20.5-4.6-4.6"/></svg></span>`}
        <div class="li-main">
          <div class="ec-title">${esc(t.item_name)}</div>
          <div class="ec-badges">
            <span class="badge ${color}">${label}</span>
          </div>
        </div>
      </div>
      <div class="ec-body">
        ${t.item_code ? `<div class="ec-row" style="align-items:flex-start"><span class="k">کد / مشخصات</span><span class="v" style="font-weight:500;text-align:left;line-height:1.5">${esc(t.item_code)}</span></div>` : ""}
        <div class="ec-row"><span class="k">مشتری</span><span class="v">${esc(t.customer_name) || "—"}</span></div>
        <div class="ec-row"><span class="k">تماس</span><span class="v" dir="ltr">${t.customer_phone_fa || "—"}</span></div>
        ${t.price ? `<div class="ec-row"><span class="k">قیمت</span><span class="v">${t.price_display} تومان</span></div>` : ""}
        ${t.notes ? `<div class="ec-row" style="align-items:flex-start"><span class="k">یادداشت</span><span class="v" style="font-weight:500;text-align:left;line-height:1.5">${esc(t.notes)}</span></div>` : ""}
      </div>
      <div class="ec-foot">
        <div class="stepper grow">${t.status === "cancelled" ? "" : steps}</div>
        ${t.status === "cancelled" ? '<span class="li-sub">لغو شده</span>' : ""}
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
  if (!selectedTrackingIds.size) {
    bar.classList.add("hidden");
    return;
  }
  bar.classList.remove("hidden");
  $("#bulk-count").textContent = `${faNum(selectedTrackingIds.size)} مورد انتخاب شده`;
}

$("#tracking-grid").addEventListener("change", (e) => {
  const check = e.target.closest(".row-check");
  if (!check) return;
  const id = +check.dataset.id;
  if (check.checked) selectedTrackingIds.add(id);
  else selectedTrackingIds.delete(id);
  check.closest("[data-id]").classList.toggle("row-selected", check.checked);
  updateBulkBar();
});

$("#tracking-grid").addEventListener("click", async (e) => {
  const stepBtn = e.target.closest(".step-btn");
  if (stepBtn && !stepBtn.disabled) {
    const t = allTracking.find((x) => x.id === +stepBtn.dataset.tid);
    if (!t) return;
    try {
      await api(`/api/tracking/${t.id}`, { method: "PUT", body: { ...t, status: stepBtn.dataset.status } });
      toast("وضعیت به‌روزرسانی شد");
      loadTracking();
    } catch (err) {
      toast(err.message, "error");
    }
    return;
  }

  const actBtn = e.target.closest("[data-act]");
  if (!actBtn) return;
  const card = actBtn.closest("[data-id]");
  const t = allTracking.find((x) => x.id === +card.dataset.id);
  if (!t) return;
  if (actBtn.dataset.act === "edit") openTrackingModal(t);
  if (actBtn.dataset.act === "delete") {
    deletingTrackingId = t.id;
    $("#delete-tracking-name").textContent = `«${t.item_name}»`;
    openModal("modal-delete-tracking");
  }
});

function openTrackingModal(t = null) {
  editingTrackingId = t ? t.id : null;
  const form = $("#tracking-form");
  form.reset();
  $("#tracking-modal-title").textContent = t ? "ویرایش سفارش" : "ثبت سفارش جدید";

  const wrap = $("#modal-tracking .img-upload");
  wrap.dataset.ready = "";
  wrap.querySelector('input[type="hidden"]').value = t ? t.image || "" : "";

  form.querySelector('[name="item_name"]').value = t?.item_name || "";
  form.querySelector('[name="item_code"]').value = t?.item_code || "";
  form.querySelector('[name="customer_name"]').value = t?.customer_name || "";
  form.querySelector('[name="customer_phone"]').value = t?.customer_phone || "";
  form.querySelector('[name="price"]').value = t?.price
    ? faNum(Number(t.price).toLocaleString("en-US")).replace(/,/g, "٬") : "";
  form.querySelector('[name="status"]').value = t?.status || "new";
  form.querySelector('[name="notes"]').value = t?.notes || "";

  document.dispatchEvent(new CustomEvent("modal:opened", { detail: { root: $("#modal-tracking") } }));
  openModal("modal-tracking");
}

$("#btn-save-tracking").addEventListener("click", async () => {
  const form = $("#tracking-form");
  if (!form.reportValidity()) return;
  const fd = new FormData(form);
  const payload = {};
  for (const [k, v] of fd.entries()) payload[k] = v;
  payload.price = toEnDigits(payload.price || "0").replace(/[^\d]/g, "") || "0";
  payload.customer_phone = toEnDigits(payload.customer_phone || "").trim();

  const btn = $("#btn-save-tracking");
  btn.disabled = true;
  try {
    if (editingTrackingId) {
      await api(`/api/tracking/${editingTrackingId}`, { method: "PUT", body: payload });
      toast("سفارش به‌روزرسانی شد");
    } else {
      await api("/api/tracking", { method: "POST", body: payload });
      toast("سفارش جدید ثبت شد");
    }
    closeModal("modal-tracking");
    loadTracking();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

$("#btn-new").addEventListener("click", () => openTrackingModal());

$("#btn-confirm-delete").addEventListener("click", async () => {
  if (!deletingTrackingId) return;
  try {
    await api(`/api/tracking/${deletingTrackingId}`, { method: "DELETE" });
    toast("سفارش حذف شد");
    closeModal("modal-delete-tracking");
    loadTracking();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    deletingTrackingId = null;
  }
});

/* ------------------------------------------------ حذف گروهی */

$("#btn-bulk-delete").addEventListener("click", () => {
  if (!selectedTrackingIds.size) return;
  $("#delete-bulk-count").textContent = faNum(selectedTrackingIds.size) + " سفارش";
  openModal("modal-delete-bulk");
});

$("#btn-confirm-bulk-delete").addEventListener("click", async () => {
  const btn = $("#btn-confirm-bulk-delete");
  btn.disabled = true;
  try {
    const res = await api("/api/tracking/bulk-delete", {
      method: "POST",
      body: { ids: [...selectedTrackingIds] },
    });
    toast(`${faNum(res.deleted)} سفارش حذف شد`);
    selectedTrackingIds.clear();
    closeModal("modal-delete-bulk");
    loadTracking();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

$("#btn-bulk-clear").addEventListener("click", () => {
  selectedTrackingIds.clear();
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
  a.href = "/export/tracking.xlsx";
  document.body.appendChild(a);
  a.click();
  a.remove();
});

document.addEventListener("DOMContentLoaded", () => {
  bindMoneyInput(document.querySelector('#tracking-form [name="price"]'));
  loadTracking();
});
