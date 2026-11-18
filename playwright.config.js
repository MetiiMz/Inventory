// Browser checks for the TikoTime frontend (real browser, Chromium, temp DB).
// Run with:  TIKOTIME_DB=/tmp/check_*.db npx playwright test
//            (the Django dev server must be running on http://127.0.0.1:8000)
module.exports = {
  testDir: "./docs/browser-checks",
  testMatch: /.*-check\.js$/,
  use: {
    baseURL: "http://127.0.0.1:8000",
    headless: true,
    actionTimeout: 10000,
    navigationTimeout: 20000,
  },
};
