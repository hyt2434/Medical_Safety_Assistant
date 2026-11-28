import { expect, type Browser, type Page } from "@playwright/test";

export const ACCOUNTS = {
  patient: ["mai.demo@example.com", "Mai-patient-2026"],
  hcp: ["an.demo@example.com", "An-hcp-2026"],
  reviewer: ["huy.demo@example.com", "Huy-review-2026"],
  support: ["khoa.demo@example.com", "Khoa-support-2026"],
  admin: ["ha.demo@example.com", "Ha-admin-2026"],
} as const;
export type Role = keyof typeof ACCOUNTS;

/** The dashboard's "Hoàn thiện hồ sơ" prompt can open over any page; snooze it whenever it blocks. */
export async function dismissProfilePrompt(page: Page) {
  await page.addLocatorHandler(page.getByRole("button", { name: "Nhắc lại sau 7 ngày", exact: true }),
    async (button) => { await button.click(); });
}

/** Sign in through the real login form. */
export async function uiLogin(page: Page, role: Role) {
  await dismissProfilePrompt(page);
  const [email, password] = ACCOUNTS[role];
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(password);
  const response = page.waitForResponse((r) => r.url().endsWith("/api/auth/login"));
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  expect((await response).status()).toBe(200);
  await expect(page).not.toHaveURL(/\/login$/);
}

/** A new browser context signed in via the API (one login per role; the throttle counts successes). */
export async function signedIn(browser: Browser, role: Role, viewport = { width: 1366, height: 900 }) {
  const baseURL = process.env.LIVE_URL || "http://127.0.0.1:5173";
  const context = await browser.newContext({ baseURL, viewport, locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh" });
  const [email, password] = ACCOUNTS[role];
  const r = await context.request.post("/api/auth/login", { data: { email, password }, headers: { Origin: baseURL } });
  expect(r.status(), `login ${role}`).toBe(200);
  const page = await context.newPage();
  await dismissProfilePrompt(page);
  return { context, page };
}

export async function idle(page: Page) {
  const workspace = page.locator(".intake-workspace");
  if (await workspace.count()) await expect(workspace).toHaveAttribute("aria-busy", "false");
}

/** Start a fresh manual intake draft. */
export async function freshIntake(page: Page, mode: "manual" | "chat" | "voice" | "image" = "manual") {
  const capability = page.waitForResponse((r) => r.url().includes("/api/v1/intake/capabilities"));
  await page.goto("/intake?mode=" + mode);
  await capability;
  await idle(page);
  const restart = page.getByRole("button", { name: "Cuộc hội thoại mới", exact: true });
  if (await restart.isVisible()) {
    await restart.click();
    await idle(page);
  }
  const cancel = page.getByRole("button", { name: "Hủy yêu cầu hiện tại", exact: true });
  if (await cancel.isVisible()) {
    await cancel.click();
    await idle(page);
    await page.getByRole("button", { name: "Cuộc hội thoại mới", exact: true }).click();
    await idle(page);
  }
  if (mode === "manual") {
    const tab = page.getByRole("button", { name: "Nhập bằng tay" });
    if (await tab.count()) await tab.first().click();
  }
}

/** Search the catalog, pick the exact product, fill label fields and save to the draft. */
export async function addProduct(page: Page, brand: string, strength: string, timing = "uống lúc 08:00 và 20:00", dose = "1 viên") {
  await page.getByRole("textbox", { name: "Tìm thuốc trong danh mục", exact: true }).fill(brand);
  const search = page.waitForResponse((r) => r.url().includes("/api/reference/medications?"));
  await page.getByRole("button", { name: "Tìm sản phẩm", exact: true }).click();
  const catalog = (await (await search).json()).medications as { brand_name: string; source_medication_id: string; dosage_form: string }[];
  const product = catalog.find((p) => p.brand_name === brand);
  expect(product, `${brand} in catalog`).toBeTruthy();
  await page.getByRole("button", { name: `Chọn ${product!.brand_name} — ${product!.source_medication_id}`, exact: true }).click();
  await page.getByLabel("Hàm lượng theo nhãn", { exact: true }).fill(strength);
  await page.getByLabel("Dạng thuốc", { exact: true }).fill(product!.dosage_form || "viên nén");
  await page.getByLabel("Liều mỗi lần", { exact: true }).fill(dose);
  await page.getByLabel("Thời điểm dùng", { exact: true }).fill(timing);
  const saved = page.waitForResponse((r) => r.url().endsWith("/api/v1/intake/manual"));
  await page.getByRole("button", { name: "Lưu thuốc vào bản nháp", exact: true }).click();
  const review = await (await saved).json();
  await idle(page);
  return review;
}

/** Fail on horizontal page overflow (responsive check). */
export async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect.soft(overflow, `horizontal overflow on ${page.url()}`).toBeLessThanOrEqual(1);
}
