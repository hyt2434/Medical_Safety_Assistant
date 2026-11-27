import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";

await mkdir("artifacts", { recursive: true });
const browser = await chromium.launch({
  executablePath:
    process.env.CHROME_PATH ||
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const base = process.env.PREVIEW_URL || "http://127.0.0.1:5173";
try {
  await page.goto(base);
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: "artifacts/landing-desktop.png",
    fullPage: true,
  });
  await page.goto(`${base}/login`);
  await page
    .getByRole("button", { name: "Vào bản mẫu người dùng", exact: true })
    .click();
  await page.screenshot({
    path: "artifacts/dashboard-desktop.png",
    fullPage: true,
  });
  await page.goto(`${base}/intake`);
  await page.getByRole("button", { name: "Dùng bộ dữ liệu mẫu" }).click();
  await page.screenshot({
    path: "artifacts/intake-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 375, height: 900 });
  await page.goto(`${base}/dashboard`);
  await page.screenshot({
    path: "artifacts/dashboard-mobile.png",
    fullPage: true,
  });
  await page.goto(`${base}/intake`);
  await page.screenshot({
    path: "artifacts/intake-mobile.png",
    fullPage: true,
  });
  await page.goto(`${base}/hcp/login`);
  await page
    .getByRole("button", { name: "Vào bản mẫu HCP", exact: true })
    .click();
  await page.goto(`${base}/hcp/queue`);
  await page.screenshot({
    path: "artifacts/hcp-queue-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: "artifacts/hcp-queue-desktop.png",
    fullPage: true,
  });
} finally {
  await browser.close();
}
console.log("Screenshots saved to artifacts/");
