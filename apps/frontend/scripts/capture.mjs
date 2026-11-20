import { chromium } from "@playwright/test";
import { existsSync } from "node:fs";
import { mkdir } from "node:fs/promises";

const base = process.env.PREVIEW_URL || "http://127.0.0.1:5173";
const executablePath = process.env.CHROME_PATH || [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
].find(path => existsSync(path));
await mkdir("artifacts", { recursive: true });
const browser = await chromium.launch({ executablePath, headless: true });
const context = await browser.newContext({ extraHTTPHeaders: { Origin: new URL(base).origin } });
const page = await context.newPage();
async function login(email, password, destination) {
  const result = await context.request.post(`${base}/api/auth/login`, { data: { email, password } });
  if (!result.ok()) throw new Error(`Development login failed: ${result.status()}`);
  await page.goto(`${base}${destination}`);
  await page.locator("main h1").waitFor();
}
async function capture(name, route, width = 1440) {
  await page.setViewportSize({ width, height: 1000 });
  await page.goto(`${base}${route}`);
  await page.locator("main h1").waitFor();
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: `artifacts/${name}.png`, fullPage: true });
}
try {
  await capture("landing-desktop", "/");
  await login("mai.demo@example.com", "Mai-patient-2026", "/dashboard");
  await page.getByRole("button", { name: "Nhắc lại sau 7 ngày", exact: true }).click();
  await capture("dashboard-desktop", "/dashboard");
  await page.goto(`${base}/intake`);
  await page.getByRole("button", { name: "Dùng dữ liệu minh họa", exact: true }).click();
  await capture("intake-desktop", "/intake");
  await capture("dashboard-mobile", "/dashboard", 375);
  await capture("intake-mobile", "/intake", 375);
  await login("an.demo@example.com", "An-hcp-2026", "/hcp");
  await capture("hcp-queue-mobile", "/hcp/queue", 375);
  await capture("hcp-queue-desktop", "/hcp/queue");
} finally {
  await browser.close();
}
