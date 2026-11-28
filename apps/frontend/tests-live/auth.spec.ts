import { test, expect } from "@playwright/test";
import { ACCOUNTS, uiLogin } from "./helpers";

test("AUTH-03: wrong password shows an error and stays on login", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill(ACCOUNTS.patient[0]);
  await page.getByLabel("Mật khẩu", { exact: true }).fill("wrong-password");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});

test("AUTH-05: locked account is refused", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill("locked.demo@example.com");
  await page.getByLabel("Mật khẩu", { exact: true }).fill("Locked-patient-2026");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});

test("AUTH-09: protected pages redirect anonymous visitors to login", async ({ page }) => {
  for (const path of ["/dashboard", "/reminders", "/hcp/queue", "/admin"]) {
    await page.goto(path);
    await expect(page, path).toHaveURL(/login/);
  }
});

test("AUTH-02/07/08/10: patient login, refresh keeps session, guard, logout clears data", async ({ page }) => {
  await uiLogin(page, "patient");
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.reload();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.goto("/admin");
  await expect(page).not.toHaveURL(/\/admin$/);
  await page.goto("/dashboard");
  await page.getByRole("button", { name: "Đăng xuất", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Đăng xuất", exact: true }).click();
  await expect(page.getByLabel("Email", { exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByText("Hatacil 500")).toHaveCount(0);
});

test("AUTH-21: unknown route shows not-found page", async ({ page }) => {
  await page.goto("/khong-ton-tai");
  await expect(page.getByRole("heading").first()).toBeVisible();
  await expect(page.getByRole("link").first()).toBeVisible();
});
