import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";

// Live acceptance UI suite: drives the ALREADY RUNNING app (python scripts/preview-ui.py).
// It writes real records to the configured database. Run:
//   npx playwright test -c playwright.live.config.ts         (HEADED=1 to watch)
const baseURL = process.env.LIVE_URL || "http://127.0.0.1:5173";
const browserPath = process.env.CHROME_PATH || [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
].find((path) => existsSync(path));

export default defineConfig({
  testDir: "./tests-live",
  fullyParallel: false,
  workers: 1,
  timeout: 240000,
  expect: { timeout: 20000 },
  outputDir: "../../artifacts/acceptance/ui-results",
  reporter: [["list"], ["html", { open: "never", outputFolder: "../../artifacts/acceptance/ui-report" }]],
  use: {
    baseURL,
    headless: process.env.HEADED !== "1",
    extraHTTPHeaders: { Origin: baseURL },
    launchOptions: { executablePath: browserPath },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    locale: "vi-VN",
    timezoneId: "Asia/Ho_Chi_Minh",
  },
});
