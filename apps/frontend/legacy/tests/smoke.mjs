import puppeteer from "puppeteer-core";
import assert from "node:assert/strict";
import { mkdir, access } from "node:fs/promises";
import { createServer } from "vite";
const base = process.env.FRONTEND_URL || "http://127.0.0.1:5173";
const candidates = [
  process.env.BROWSER_PATH,
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "/usr/bin/chromium",
  "/usr/bin/google-chrome",
].filter(Boolean);
let executablePath;
for (const p of candidates) {
  try {
    await access(p);
    executablePath = p;
    break;
  } catch {}
}
if (!executablePath)
  throw new Error(
    "Set BROWSER_PATH to a local Chrome, Edge or Chromium executable.",
  );
await mkdir("artifacts", { recursive: true });
const server = process.env.FRONTEND_URL
  ? null
  : await createServer({
      server: { host: "127.0.0.1", port: 5173, strictPort: true },
    });
await server?.listen();
const browser = await puppeteer.launch({
  executablePath,
  headless: true,
  args: ["--no-sandbox"],
  userDataDir: `artifacts/browser-profile-${Date.now()}`,
});
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const go = async (route) => {
    await page.goto(`${base}/pa1.html#/${route}`);
    await page.waitForSelector("main h1");
  };
  const click = async (s) => {
    await page.click(s);
    await new Promise((r) => setTimeout(r, 80));
  };
  await page.setViewport({ width: 1440, height: 1000 });
  await go("index");
  await page.evaluate(() => sessionStorage.clear());
  await page.reload();
  const routes = [
    "index",
    "login",
    "hcp-login",
    "dashboard",
    "intake",
    "verify",
    "results",
    "results-pending",
    "results-reviewed",
    "medications",
    "reminders",
    "profile",
    "chatbot",
    "hcp-review",
    "professional",
    "hcp-queue",
    "hcp-case",
    "hcp-assessment",
    "hcp-assessment-list",
    "hcp-confirmation",
    "hcp-patients",
    "hcp-database",
    "hcp-profile",
    "admin",
    "policy",
    "not-found",
  ];
  for (const r of routes) {
    await go(r);
    assert(await page.$("h1"), r);
  }
  // Patient -> consent -> HCP queue -> verification -> reply -> explicit schedule opt-in.
  await go("intake");
  await click("#intake-form button[type=submit]");
  assert(page.url().endsWith("/verify"));
  await page.$$eval("#verify-form input[type=checkbox]", (els) =>
    els.forEach((e) => e.click()),
  );
  await click("#verify-form button[type=submit]");
  assert(page.url().endsWith("/results"));
  assert(await page.$eval("#schedule-form button", (b) => b.disabled));
  await go("hcp-review");
  await click("input[name=consent]");
  await click("#request-form button[type=submit]");
  assert(page.url().endsWith("/results-pending"));
  await click("[data-action=open-patient-case]");
  await page.$$eval("#case-form input[type=checkbox]", (els) =>
    els.forEach((e) => e.click()),
  );
  await click("#case-form button[type=submit]");
  assert(page.url().endsWith("/hcp-assessment"));
  await go("hcp-confirmation");
  await click("input[name=schedule]");
  await click("input[name=ack]");
  await click("#review-form button[type=submit]");
  assert(page.url().endsWith("/hcp-queue"));
  await go("results-reviewed");
  assert.equal(
    await page.$eval("#schedule-form button", (b) => b.disabled),
    false,
  );
  await click("input[name=seen]");
  await click("input[name=want]");
  await click("#schedule-form button");
  assert(page.url().endsWith("/reminders"));
  assert.equal(await page.$$eval("#dose-list .card", (els) => els.length), 5);
  await click("[data-action=dose][data-id=m2][data-value=taken]");
  await page.reload();
  assert(await page.$('[data-action=dose][data-id=m2][data-value=""]'));
  await go("chatbot");
  await page.type("#chat-input", "<img src=x onerror=alert(1)>");
  await click("#chat-form button");
  assert.equal(await page.$$eval(".messages img", (els) => els.length), 0);
  await go("medications");
  await page.type("#med-search", "no-such-med");
  assert.equal(await page.$eval("#empty-search", (e) => e.hidden), false);
  await go("profile");
  await page.$eval("input[name=name]", (e) => (e.value = "Mai thử nghiệm"));
  await click("#profile-form button");
  await page.reload();
  assert.equal(
    await page.$eval("input[name=name]", (e) => e.value),
    "Mai thử nghiệm",
  );
  // Editing intake invalidates old result; the existing schedules are preserved.
  await go("intake");
  await click("#intake-form button[type=submit]");
  await go("results");
  assert.equal(await page.$("#schedule-form"), null);
  await go("reminders");
  assert.equal(await page.$$eval("#dose-list .card", (els) => els.length), 5);
  // Verify every route for horizontal overflow at required phone/tablet widths.
  for (const width of [320, 375, 414, 768, 1440]) {
    await page.setViewport({ width, height: 1000 });
    for (const r of routes) {
      await go(r);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth + 1,
      );
      assert.equal(overflow, false, `${r}: horizontal overflow at ${width}`);
    }
  }
  for (const r of [
    "index",
    "dashboard",
    "intake",
    "professional",
    "hcp-queue",
    "chatbot",
  ]) {
    await go(r);
    await page.screenshot({
      path: `artifacts/${r}-desktop.png`,
      fullPage: true,
    });
  }
  await page.setViewport({ width: 375, height: 900 });
  await go("dashboard");
  await page.screenshot({
    path: "artifacts/dashboard-mobile.png",
    fullPage: true,
  });
  assert.deepEqual(errors, []);
  console.log(
    "PASS: 26 routes; patient/HCP workflow; persistence; input escaping; search; invalidation; 5 responsive widths.",
  );
} finally {
  await browser.close();
  await server?.close();
}
