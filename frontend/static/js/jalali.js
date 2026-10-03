/* ============================================================
   تبدیل تاریخ جلالی در سمت مرورگر — الگوریتم استاندارد jdf
   (همان الگوریتم سمت سرور، برای سازگاری کامل)
   ============================================================ */

"use strict";

(function () {
  function g2j(gy, gm, gd) {
    const gDm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    const gy2 = gm > 2 ? gy + 1 : gy;
    let days = 355666 + 365 * gy + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100)
      + Math.floor((gy2 + 399) / 400) + gd + gDm[gm - 1];
    let jy = -1595 + 33 * Math.floor(days / 12053);
    days %= 12053;
    jy += 4 * Math.floor(days / 1461);
    days %= 1461;
    if (days > 365) {
      jy += Math.floor((days - 1) / 365);
      days = (days - 1) % 365;
    }
    let jm, jd;
    if (days < 186) {
      jm = 1 + Math.floor(days / 31);
      jd = 1 + (days % 31);
    } else {
      jm = 7 + Math.floor((days - 186) / 30);
      jd = 1 + ((days - 186) % 30);
    }
    return { jy, jm, jd };
  }

  function j2g(jy, jm, jd) {
    jy += 1595;
    let days = -355668 + 365 * jy + Math.floor((jy / 33)) * 8 + Math.floor(((jy % 33) + 3) / 4) + jd;
    days += jm < 7 ? (jm - 1) * 31 : ((jm - 7) * 30) + 186;
    let gy = 400 * Math.floor(days / 146097);
    days %= 146097;
    if (days > 36524) {
      days -= 1;
      gy += 100 * Math.floor(days / 36524);
      days %= 36524;
      if (days >= 365) days += 1;
    }
    gy += 4 * Math.floor(days / 1461);
    days %= 1461;
    if (days > 365) {
      gy += Math.floor((days - 1) / 365);
      days = (days - 1) % 365;
    }
    let gd = days + 1;
    const leap = (gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0;
    const gDm = [0, 31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    let gm = 0;
    while (gm < 13 && gd > gDm[gm]) { gd -= gDm[gm]; gm += 1; }
    return { gy, gm, gd };
  }

  function isJLeap(jy) {
    const { gy, gm, gd } = j2g(jy, 12, 30);
    const back = g2j(gy, gm, gd);
    return back.jy === jy && back.jm === 12 && back.jd === 30;
  }

  function jMonthLength(jy, jm) {
    if (jm <= 6) return 31;
    if (jm <= 11) return 30;
    return isJLeap(jy) ? 30 : 29;
  }

  /* ISO میلادی → رشته‌ی شمسی ۱۴۰۳/۰۵/۱۲ */
  function isoToJalaliStr(iso) {
    if (!iso) return "";
    const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
    if (!y || !m || !d) return "";
    const { jy, jm, jd } = g2j(y, m, d);
    const p = (n) => String(n).padStart(2, "0");
    return `${jy}/${p(jm)}/${p(jd)}`;
  }

  /* ورودی آزاد کاربر (شمسی یا میلادی، با رقم فارسی) → ISO میلادی یا null */
  function parseDateInput(text) {
    if (!text) return null;
    let s = String(text).replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)));
    s = s.trim().replace(/[-.\s]/g, "/").replace(/^\/+|\/+$/g, "");
    const parts = s.split("/").filter(Boolean);
    try {
      if (parts.length === 3) {
        const a = +parts[0], b = +parts[1], c = +parts[2];
        if (a > 1900) { // میلادی
          if (b < 1 || b > 12 || c < 1 || c > 31) return null;
          const dt = new Date(Date.UTC(a, b - 1, c));
          if (isNaN(dt.getTime())) return null;
          return dt.toISOString().slice(0, 10);
        }
        if (a > 1000) { // شمسی
          if (b < 1 || b > 12 || c < 1 || c > jMonthLength(a, b)) return null;
          const { gy, gm, gd } = j2g(a, b, c);
          return `${gy}-${String(gm).padStart(2, "0")}-${String(gd).padStart(2, "0")}`;
        }
        return null;
      }
      if (parts.length === 1 && parts[0].length === 8) {
        const n = +parts[0];
        if (n > 19000000) {
          const dt = new Date(Date.UTC(Math.floor(n / 10000), Math.floor(n / 100) % 100 - 1, n % 100));
          if (isNaN(dt.getTime())) return null;
          return dt.toISOString().slice(0, 10);
        }
        const { gy, gm, gd } = j2g(Math.floor(n / 10000), Math.floor(n / 100) % 100, n % 100);
        return `${gy}-${String(gm).padStart(2, "0")}-${String(gd).padStart(2, "0")}`;
      }
    } catch { return null; }
    return null;
  }

  window.JalaliJS = { g2j, j2g, jMonthLength, isJLeap, isoToJalaliStr, parseDateInput };
})();
