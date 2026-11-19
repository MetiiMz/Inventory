/* ============================================================
   کارت‌های مودال جزئیات — کد مشترک صفحه‌ی فروش‌ها و تقویم
   (سرصفحه‌ی تصویر+نام و «کاشی»های درون کارت)

   این فایل باید پیش از sold.js و calendar.js بارگذاری شود و به
   esc() / faNum() از app.js تکیه دارد؛ پس app.js باید قبل از آن
   در صفحه باشد (base.html).

   قاعده‌ی مشترک: هر مقدار کاربر پیش از رسیدن به این توابع با esc()
   امن می‌شود و مقدار خالی به «—» تبدیل می‌شود تا شبکه‌ی کارت با
   نبودِ یک مقدار جابه‌جا نشود.
   ============================================================ */

"use strict";

/* برچسب و رنگ نوع پرداخت — مشترک بین فروش‌ها و تقویم */
const PAYMENT_BADGE = {
  cash: ["green", "تسویه کامل"],
  deposit: ["amber", "بیعانه"],
  credit: ["blue", "اعتباری"],
};

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

/* سرصفحه‌ی مودال: تصویر ۹۶px (کلیک روی آن لایت‌باکس سراسری را باز می‌کند)
   و نام بزرگ. نبودِ تصویر → آیکون ساعت. */
function sdHeader(imageFile, name) {
  return `
    <div class="sd-header">
      ${imageFile
        ? `<img class="thumb sd-thumb" src="/data/images/${encodeURIComponent(imageFile)}" alt="" loading="lazy">`
        : `<span class="thumb sd-thumb"><svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="6.4"/><path d="M12 9.2V12l2.1 1.5"/></svg></span>`}
      <div class="sd-head-text">
        <h4 class="sd-name">${esc(name)}</h4>
      </div>
    </div>`;
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
