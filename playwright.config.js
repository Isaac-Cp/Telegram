const { defineConfig, devices } = require("@playwright/test");

const baseURL = process.env.DASHBOARD_BASE_URL || "http://127.0.0.1:8000";

module.exports = defineConfig({
  testDir: "./tests",
  testMatch: /.*\.visual\.spec\.js/,
  timeout: 120_000,
  expect: {
    timeout: 30_000,
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.03,
    },
  },
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "dashboard-desktop",
      use: {
        viewport: { width: 1440, height: 900 },
      },
    },
    {
      name: "dashboard-mobile",
      use: {
        ...devices["iPhone 14"],
        browserName: "chromium",
      },
    },
  ],
  webServer: process.env.DASHBOARD_BASE_URL
    ? undefined
    : {
        command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --lifespan off",
        url: baseURL,
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
