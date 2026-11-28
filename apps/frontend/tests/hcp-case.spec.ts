import { test, expect } from "@playwright/test";

test("assigned HCP records review and leaves closure to patient activation", async ({
  page,
}) => {
  const row = {
    id: "case-1",
    case_type: "SCHEDULE",
    status: "OPEN",
    created_at: "2026-11-27T00:00:00Z",
    schedule_id: "schedule-1",
    schedule: {
      name: "Synthetic medication",
      schedule_details: { times: ["08:00"], dose_raw: "1 tablet" },
      timezone: "Asia/Ho_Chi_Minh",
    },
    messages: [] as object[],
    outcomes: [] as object[],
  };
  await page.route("**/api/v1/hcp/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/capabilities"))
      return route.fulfill({ json: { preview: false } });
    if (path.endsWith("/messages")) {
      expect(route.request().postDataJSON()).toEqual({
        text: "Please confirm the instructions",
      });
      row.messages.push({
        id: "m1",
        content: "Please confirm the instructions",
        sent_at: row.created_at,
      });
      return route.fulfill({ json: { id: "m1" } });
    }
    if (path.endsWith("/review")) {
      expect(route.request().postDataJSON()).toEqual({
        decision: "APPROVED",
        notes: "Reviewed exact schedule and assessment",
      });
      row.outcomes.push({
        id: "o1",
        decision: "APPROVED",
        notes: "Reviewed exact schedule and assessment",
      });
      return route.fulfill({ json: row.outcomes[0] });
    }
    return route.fulfill({ json: path.endsWith("/cases") ? [row] : row });
  });
  await page.goto("/login");
  await page
    .getByLabel("Email", { exact: true })
    .fill("multi.demo@example.com");
  await page.getByLabel("Mật khẩu", { exact: true }).fill("Multi-role-2026");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.getByRole("button", { name: "HCP", exact: true }).click();
  await page.goto("/hcp/queue");
  await page.getByRole("link", { name: "Mở ca", exact: true }).click();
  await expect(
    page.getByText("Synthetic medication", { exact: false }),
  ).toBeVisible();
  await page
    .getByLabel("Tin nhắn", { exact: true })
    .fill("Please confirm the instructions");
  await page.getByRole("button", { name: "Gửi tin nhắn", exact: true }).click();
  await expect(
    page.getByText("Please confirm the instructions", { exact: false }),
  ).toBeVisible();
  await page.getByRole("combobox", { name: "Quyết định", exact: true }).selectOption("APPROVED");
  await page
    .getByLabel("Nhận định chuyên môn")
    .fill("Reviewed exact schedule and assessment");
  await page.getByRole("button", { name: "Lưu kết quả rà soát" }).click();
  await expect(
    page.getByRole("heading", { name: "SCHEDULE · OPEN" }),
  ).toBeVisible();
  await expect(
    page.getByText("APPROVED: Reviewed exact schedule and assessment", { exact: true }),
  ).toBeVisible();
});

test("denied HCP case does not fall back to demo data", async ({ page }) => {
  await page.route("**/api/v1/hcp/**", (r) =>
    r.fulfill({ status: 403, json: { detail: "Case access denied" } }),
  );
  await page.goto("/login");
  await page
    .getByLabel("Email", { exact: true })
    .fill("multi.demo@example.com");
  await page.getByLabel("Mật khẩu", { exact: true }).fill("Multi-role-2026");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.getByRole("button", { name: "HCP", exact: true }).click();
  await page.goto("/hcp/case/forbidden");
  await expect(page.getByText("Case access denied")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Lưu kết quả rà soát" }),
  ).toHaveCount(0);
});
