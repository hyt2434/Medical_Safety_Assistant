import { test, expect, type Page } from "@playwright/test";

async function login(page: Page, email: string, password: string) {
  const response = await page.request.post("/api/auth/login", {
    data: { email: `${email}.demo@example.com`, password },
  });
  expect(response.status()).toBe(200);
}
test("patient can create and revoke local sharing, create reminders, and keep caregiver invitations", async ({
  page,
}) => {
  await login(page, "mai", "Mai-patient-2026");
  await page.goto("/share-summary");
  await page.getByRole("button", { name: "Tạo quyền chia sẻ mẫu" }).click();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Thu hồi bản chia sẻ mẫu" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Thu hồi bản chia sẻ mẫu" }).click();
  await expect(
    page.getByRole("button", { name: "Thu hồi bản chia sẻ mẫu" }),
  ).toHaveCount(0);
  await page.goto("/caregivers");
  await page.getByLabel("Email / số liên hệ").fill("nguoi-than@example.com");
  await page.getByRole("button", { name: "Lưu lời mời mẫu" }).click();
  await page.reload();
  await expect(page.getByRole("main")).toContainText("nguoi-than@example.com");
  await expect(page.getByRole("main")).toContainText("Chưa gửi");
  await page.goto("/reminders/new");
  await expect(
    page.getByRole("button", { name: "Lưu lời nhắc" }),
  ).toBeDisabled();
  await page.getByLabel("Thuốc đã xác nhận").selectOption({ index: 1 });
  await page.getByLabel("Giờ nhắc").fill("09:45");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Lưu lời nhắc" }).click();
  await expect(page).toHaveURL("/reminders");
  await expect(page.getByRole("main")).toContainText("09:45");
});

test("reviewer records a decision with a reason and finds it in history", async ({
  page,
}) => {
  await login(page, "huy", "Huy-review-2026");
  await page.goto("/reviewer");
  await page.getByRole("link", { name: /DR-01/ }).click();
  await page
    .getByLabel("Hoạt chất / giá trị đề xuất")
    .fill("Omeprazole đối soát mẫu");
  await page
    .getByLabel("Lý do", { exact: true })
    .fill("Cần bổ sung bằng chứng nguồn cho bản ghi thử nghiệm.");
  await page.getByRole("button", { name: "Lưu quyết định mẫu" }).click();
  await expect(page.getByRole("status")).toContainText("Đã lưu quyết định");
  await page.getByRole("link", { name: "Xem lịch sử duyệt" }).click();
  await expect(page.getByRole("main")).toContainText(
    "Cần bổ sung bằng chứng nguồn",
  );
  await page.request.post("/api/auth/logout");
  await login(page, "an", "An-hcp-2026");
  await page.goto("/reviewer");
  await expect(page).toHaveURL("/hcp");
});

test("support creates a ticket and saves its response and status", async ({
  page,
}) => {
  await login(page, "khoa", "Khoa-support-2026");
  await page.goto("/staff/report");
  await page.getByLabel("Tiêu đề sự cố").fill("Không mở được lịch mẫu");
  await page
    .getByLabel("Mô tả và bước tái hiện")
    .fill("Mở trang lịch, chọn ngày và kiểm tra thông báo.");
  await page.getByRole("button", { name: "Tạo ticket mẫu" }).click();
  await expect(page).toHaveURL(/\/staff\/tickets\/SUP-/);
  await page
    .getByRole("combobox", { name: "Trạng thái", exact: true })
    .selectOption("doing");
  await page
    .getByLabel("Phản hồi", { exact: true })
    .fill("Đã tái hiện, đang kiểm tra giao diện lịch.");
  await page.getByRole("button", { name: "Lưu phản hồi mẫu" }).click();
  await page.reload();
  await expect(
    page.getByRole("combobox", { name: "Trạng thái", exact: true }),
  ).toHaveValue("doing");
  await expect(page.getByRole("main")).toContainText(
    "Đã tái hiện, đang kiểm tra",
  );
});

test("new Figma routes render at mobile and desktop without broken assets or overflow", async ({
  page,
}) => {
  test.setTimeout(180000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const groups: [string, string, string[]][] = [
    [
      "mai",
      "Mai-patient-2026",
      [
        "/medications/s1",
        "/medication-history",
        "/dose-history",
        "/health-summary",
        "/share-summary",
        "/caregivers",
        "/reminders/new",
        "/review-tracking",
      ],
    ],
    ["an", "An-hcp-2026", ["/hcp/patients/TC01", "/hcp/patients/TC01/summary"]],
    [
      "huy",
      "Huy-review-2026",
      [
        "/reviewer",
        "/reviewer/records/DR-01",
        "/reviewer/mapping/DR-01",
        "/reviewer/history",
        "/reviewer/sources",
      ],
    ],
    [
      "khoa",
      "Khoa-support-2026",
      ["/staff", "/staff/tickets", "/staff/report"],
    ],
    [
      "ha",
      "Ha-admin-2026",
      ["/admin/roles", "/admin/database", "/admin/operations"],
    ],
  ];
  for (const [email, password, paths] of groups) {
    await login(page, email, password);
    for (const width of [375, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      for (const path of paths) {
        await page.goto(path);
        await expect(page.locator("main h1,main h2").first()).toBeVisible();
        await page.evaluate(() => document.fonts.ready);
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
          `${path} at ${width}`,
        ).toBe(true);
        expect(
          await page.evaluate(() =>
            [...document.images]
              .filter((i) => i.complete && !i.naturalWidth)
              .map((i) => i.src),
          ),
          path,
        ).toEqual([]);
      }
    }
  }
  expect(errors).toEqual([]);
});
