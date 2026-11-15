import { test, expect } from "@playwright/test";

test("server context persists and client storage cannot escalate privileges", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("multi.demo@example.com");
  await page.getByLabel("Mật khẩu").fill("Multi-role-2026");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.getByRole("button", { name: "HCP", exact: true }).click();
  await expect(page).toHaveURL("/hcp");
  await expect(page.getByRole("link", { name: "Rà soát dữ liệu", exact: true })).toHaveCount(0);
  await page.getByLabel("Ngữ cảnh đang mở").selectOption("medical_reviewer");
  await expect(page.getByRole("link", { name: "Rà soát dữ liệu", exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Ngữ cảnh đang mở")).toHaveValue("medical_reviewer");
  await page.evaluate(() => {
    const stored = JSON.parse(sessionStorage.getItem("tieu-bach-demo-v1")!);
    stored.state.activeContext = "admin";
    stored.state.serverRoles = ["admin"];
    stored.state.serverPermissions = ["admin.roles"];
    sessionStorage.setItem("tieu-bach-demo-v1", JSON.stringify(stored));
  });
  await page.goto("/admin/accounts");
  await expect(page).toHaveURL("/hcp");
  expect((await page.request.get("/api/admin/accounts")).status()).toBe(403);
  expect((await page.request.post("/api/auth/switch-context", { data: { context: "admin" } })).status()).toBe(403);
});

test("live role revocation and 401 restore route protection", async ({ browser }) => {
  const headers = { Origin: test.info().project.use.baseURL! };
  const manager = await browser.newContext({ extraHTTPHeaders: headers });
  const user = await browser.newContext({ extraHTTPHeaders: headers });
  try {
    const base = test.info().project.use.baseURL!;
    await manager.request.post(`${base}/api/auth/login`, { data: { email: "ha.demo@example.com", password: "Ha-admin-2026" } });
    const grant = await manager.request.post(`${base}/api/admin/role-grants`, { data: { userId: "u-support", roleCode: "hcp", granted: true } });
    expect(grant.status()).toBe(200);
    await user.request.post(`${base}/api/auth/login`, { data: { email: "khoa.demo@example.com", password: "Khoa-support-2026" } });
    await user.request.post(`${base}/api/auth/switch-context`, { data: { context: "hcp" } });
    const page = await user.newPage();
    await page.goto(`${base}/hcp`);
    await expect(page.getByLabel("Ngữ cảnh đang mở")).toHaveValue("hcp");
    await manager.request.delete(`${base}/api/admin/users/u-support/roles/hcp`);
    await page.reload();
    await expect(page).toHaveURL(`${base}/staff`);
    expect((await user.request.get(`${base}/api/admin/accounts`)).status()).toBe(403);
    await user.request.post(`${base}/api/auth/logout`);
    await page.reload();
    await expect(page).toHaveURL(`${base}/login`);
    expect((await user.request.get(`${base}/api/auth/me`)).status()).toBe(401);
  } finally {
    await manager.close();
    await user.close();
  }
});

test("expired admin session shows login instead of stale protected data", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("ha.demo@example.com");
  await page.getByLabel("Mật khẩu").fill("Ha-admin-2026");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page).toHaveURL("/admin");
  await page.request.post("/api/auth/logout");
  await page.goto("/admin/accounts");
  await expect(page).toHaveURL("/login");
  await expect(page.getByRole("heading", { name: "Tài khoản và role" })).toHaveCount(0);
});
