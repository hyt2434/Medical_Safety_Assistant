import { test, expect } from "@playwright/test";
import { sampleMedicines } from '../src/state';
import { fixture } from './intake-fixture';
import type { Page } from "@playwright/test";

test('chat resumes its server workflow after navigation and reload', async ({ page }) => {
  const state = await fixture(page);
  await login(page);
  await page.goto('/chat');
  await page.getByLabel('Tin nhắn', { exact: true }).fill('Tôi nên hỏi dược sĩ điều gì?');
  await page.getByRole('button', { name: 'Gửi tin nhắn', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Câu trả lời có nguồn' })).toContainText('Câu trả lời từ backend');
  await page.goto('/medications');
  await page.getByRole('link', { name: 'Mở chat Tiểu Bạch', exact: true }).click();
  await expect(page).toHaveURL('/chat');
  await expect(page.getByRole('region', { name: 'Câu trả lời có nguồn' })).toContainText('Câu trả lời từ backend');
  await page.reload();
  await expect(page.getByRole('region', { name: 'Câu trả lời có nguồn' })).toContainText('Câu trả lời từ backend');
  expect(state.calls.filter(call => call.path.endsWith('/workflows'))).toHaveLength(1);
  expect(state.calls.filter(call => call.path.endsWith('/messages'))).toHaveLength(1);
});

test("breadcrumbs and home keep a path back to the active workspace", async ({
  page,
}) => {
  await login(page);
  await page.goto("/medications");
  const trail = page.getByRole("navigation", { name: "Vị trí hiện tại" });
  await expect(trail.locator('[aria-current="page"]')).toHaveText(
    "Thuốc của tôi",
  );
  await trail.getByRole("link", { name: "Trang chủ", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Quay lại", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("link", { name: "Tiếp tục cùng Tiểu Bạch", exact: true }).click();
  await expect(page).toHaveURL("/dashboard");
  const saved = await page.evaluate(() =>
    sessionStorage.getItem("tieu-bach-demo-v1"),
  );
  const directPage = await page.context().newPage();
  await directPage.addInitScript(
    (value) => sessionStorage.setItem("tieu-bach-demo-v1", value!),
    saved,
  );
  await directPage.goto("/profile");
  await directPage
    .getByRole("button", { name: "Quay lại", exact: true })
    .click();
  await expect(directPage).toHaveURL("/dashboard");
  await directPage.close();
  await login(page, "hcp");
  await page.goto("/");
  await page.getByRole("link", { name: "Tiếp tục cùng Tiểu Bạch", exact: true }).click();
  await expect(page).toHaveURL("/hcp");
});

const demoPassword = {
  patient: "Mai-patient-2026",
  hcp: "An-hcp-2026",
  admin: "Ha-admin-2026",
  reviewer: "Huy-review-2026",
  support: "Khoa-support-2026",
  multi: "Multi-role-2026",
  locked: "Locked-patient-2026",
} as const;
const demoEmail = {
  patient: "mai.demo@example.com",
  hcp: "an.demo@example.com",
  admin: "ha.demo@example.com",
  reviewer: "huy.demo@example.com",
  support: "khoa.demo@example.com",
  multi: "multi.demo@example.com",
} as const;

async function login(
  page: Page,
  kind: keyof typeof demoEmail = "patient",
) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(demoEmail[kind]);
  await page.getByLabel("Mật khẩu").fill(demoPassword[kind]);
  const loginResponse = page.waitForResponse(response => response.url().endsWith('/api/auth/login') && response.request().method() === 'POST');
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  const loggedIn = await loginResponse;
  expect(loggedIn.status(), await loggedIn.text()).toBe(200);
  if (kind === "multi") {
    await expect(
      page.getByRole("button", { name: "Chuyên viên dữ liệu", exact: true }),
    ).toBeVisible();
    return;
  }
  const destination = {
    patient: "/dashboard",
    hcp: "/hcp",
    admin: "/admin",
    reviewer: "/reviewer",
    support: "/staff",
    multi: "/login",
  }[kind];
  await expect(page).toHaveURL(destination);
  const later = page.getByRole("button", { name: "Nhắc lại sau 7 ngày", exact: true });
  // UUID identities replaced the old u-patient key; the dialog may already be deferred.
  if (kind === 'patient' && await later.isVisible()) await later.click();
}

async function completeProfile(page: Page) {
  await page.goto('/profile');
  await page.getByLabel('Năm sinh *', { exact: true }).fill('1990');
  await page.getByLabel('Dị ứng hoặc phản ứng từng gặp *', { exact: true }).fill('Không ghi nhận - dữ liệu kiểm thử');
  await page.getByLabel('Bệnh nền / ghi chú *', { exact: true }).fill('Không ghi nhận - dữ liệu kiểm thử');
  await page.getByRole('button', { name: 'Lưu thay đổi', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Đã lưu hồ sơ');
}

// HCP/reminder screens remain explicit prototypes; seed only their isolated browser fixture.
async function seedPrototype(page: Page) {
  await page.evaluate((medicines) => {
    const key = 'tieu-bach-demo-v1';
    const saved = JSON.parse(sessionStorage.getItem(key)!);
    saved.state.draft = medicines.map(m => ({ ...m, verified: false }));
    saved.state.source = 'Bộ dữ liệu mẫu Clopidogrel / Omeprazole';
    saved.state.assessment = null;
    sessionStorage.setItem(key, JSON.stringify(saved));
  }, sampleMedicines);
  await page.goto('/verify');
}

async function verifiedSample(page: Page) {
  await completeProfile(page);
  await seedPrototype(page);
  await page.getByRole("button", { name: "Xác nhận thuốc Clopidogrel", exact: true }).click();
  await page.getByRole("button", { name: "Xác nhận thuốc Getzome Capsules", exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Đã xác nhận' })).toHaveText('Đã xác nhận 2/2 thuốc');
  await page.getByRole("button", { name: "Xem kết quả", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "Tình huống mẫu cần chuyên gia xem lại",
    }),
  ).toBeVisible();
}

test("patient request, HCP review, explicit opt-in and reminder recording", async ({
  page,
}) => {
  await login(page);
  await verifiedSample(page);
  await page
    .getByRole("checkbox", { name: "Tôi đã xem thông tin lịch" })
    .check();
  await page.getByRole("checkbox", { name: "Tôi muốn thiết lập" }).check();
  await page
    .getByRole("button", { name: "Kiểm tra điều kiện tạo lịch" })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Lịch mới đang chờ review",
  );
  await page.getByRole("link", { name: "Soạn yêu cầu", exact: true }).click();
  await page
    .getByLabel("Bạn muốn hỏi điều gì?")
    .fill("Xin kiểm tra lại tình huống toa mẫu.");
  await page.getByRole("checkbox", { name: "Tôi đồng ý" }).check();
  await page.getByRole("button", { name: "Tạo yêu cầu", exact: true }).click();
  await expect(page.getByText("Chờ phản hồi", { exact: true })).toBeVisible();
  await login(page, "hcp");
  await page.goto("/hcp/queue");
  await page
    .getByRole("row")
    .filter({ hasText: "BN-DEMO" })
    .getByRole("link", { name: "Thẩm định" })
    .click();
  await page.getByRole("button", { name: "Xác nhận thuốc" }).click();
  await page.getByRole("link", { name: "Soạn phản hồi" }).click();
  await page.getByRole("checkbox", { name: "Xác nhận lịch trên toa" }).check();
  await page.getByRole("checkbox", { name: "Tôi đã phân biệt" }).check();
  await page.getByRole("button", { name: "Ghi nhận phản hồi", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Đã lưu phản hồi");
  await login(page);
  await page.goto("/results");
  await expect(
    page.getByText("Đã phản hồi mẫu", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("checkbox", { name: "Tôi đã xem thông tin lịch" }),
  ).not.toBeChecked();
  await page
    .getByRole("checkbox", { name: "Tôi đã xem thông tin lịch" })
    .check();
  await page.getByRole("checkbox", { name: "Tôi muốn thiết lập" }).check();
  await page
    .getByRole("button", { name: "Kiểm tra điều kiện tạo lịch" })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Đã tạo lịch trong bản mẫu",
  );
  await page.goto("/reminders");
  const clopidogrel = page
    .locator(".dose-item")
    .filter({ hasText: "Clopidogrel" });
  await clopidogrel
    .getByRole("button", { name: "Đã uống", exact: true })
    .click();
  await expect(clopidogrel.getByText("Đã uống", { exact: true })).toBeVisible();
  await page.reload();
  await expect(
    page
      .locator(".dose-item")
      .filter({ hasText: "Clopidogrel" })
      .getByText("Đã uống", { exact: true }),
  ).toBeVisible();
});

test('Core edits invalidate confirmation and do not fabricate assessments', async ({ page }) => {
  const state = await fixture(page);
  await login(page); await page.goto('/intake');
  await page.getByLabel('Chọn ảnh toa thuốc', { exact: true }).setInputFiles('public/assets/prescription-sample.png');
  await page.getByRole('button', { name: 'Đọc thông tin từ ảnh', exact: true }).click();
  const confirm = page.getByRole('button', { name: 'Xác nhận danh sách', exact: true });
  await expect(confirm).toBeDisabled();
  await page.getByRole('region', { name: 'Bản nháp đã lưu trên máy chủ' }).getByRole('checkbox').check();
  await expect(confirm).toBeEnabled();
  await page.getByLabel('Tên thuốc #1', { exact: true }).fill('Thuốc chưa ánh xạ');
  await expect(confirm).toBeDisabled();
  await page.getByRole('button', { name: 'Lưu thay đổi thuốc 1', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Lưu thay đổi thuốc 1', exact: true })).toBeDisabled();
  expect(state.review.entries[0].confirmed).toBe(false);
  expect(state.calls.some(c => c.path.endsWith('/actions'))).toBe(false);
  await expect(page.getByRole('region', { name: 'Kết quả tương tác thực tế' })).toHaveCount(0);
});

test("filters, local upload, profile, guard and empty dates", async ({
  page,
}) => {
  await page.goto("/hcp/queue");
  await expect(page).toHaveURL("/hcp/login");
  await login(page);
  await page.goto("/intake");
  await page
    .getByLabel("Chọn ảnh toa thuốc", { exact: true })
    .setInputFiles("public/assets/prescription-sample.png");
  await expect(page.getByRole('region', { name: 'Bản nháp đã lưu trên máy chủ' })).toHaveCount(0);
  await page.goto("/medications");
  await page.getByLabel("Tìm thuốc hoặc hoạt chất").fill("Metformin");
  await expect(page.locator(".medicine-cards .card")).toHaveCount(1);
  await page.getByLabel("Tìm thuốc hoặc hoạt chất").fill("zzzzzzz");
  await expect(
    page.getByRole("heading", { name: "Không tìm thấy thuốc" }),
  ).toBeVisible();
  await page.goto("/profile");
  await completeProfile(page);
  await page.getByLabel("Họ và tên").fill("Người dùng thử");
  await page.getByRole("button", { name: "Lưu thay đổi", exact: true }).click();
  await page.reload();
  await expect(page.getByLabel("Họ và tên")).toHaveValue("Người dùng thử");
  await page.goto("/reminders");
  await page.locator(".date-strip button").last().click();
  await expect(
    page.getByRole("heading", { name: "Chưa có lịch cho ngày này" }),
  ).toBeVisible();
  await page.goto("/chat");
  await expect(page.getByRole('button', { name: 'Gửi tin nhắn', exact: true })).toBeDisabled();
});

test("all routes render without errors or horizontal overflow at supported sizes", async ({
  page,
}) => {
  test.setTimeout(120000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  for (const width of [320, 375, 414, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ["/", "/login", "/policy"]) {
      await page.goto(path);
      await expect(
        page.locator("h1:visible, h2:visible").first(),
      ).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
    await login(page);
    for (const path of [
      "/dashboard",
      "/intake",
      "/verify",
      "/results",
      "/medications",
      "/reminders",
      "/chat",
      "/profile",
      "/review-request",
    ]) {
      await page.goto(path);
      await expect(page.locator("main h1, main h2").first()).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        `${width}: ${path}`,
      ).toBe(true);
    }
    await login(page, "hcp");
    for (const path of [
      "/hcp",
      "/hcp/queue",
      "/hcp/patients",
      "/hcp/case/TC01",
      "/hcp/assessment/TC01",
      "/hcp/confirmation/TC01",
      "/hcp/profile",
      "/hcp/database",
    ]) {
      await page.goto(path);
      await expect(page.locator("main h1, main h2").first()).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        `${width}: ${path}`,
      ).toBe(true);
    }
  }
  expect(errors).toEqual([]);
});

test("mobile menu, accessible dialog and admin navigation", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 900 });
  await login(page);
  await page.getByRole("button", { name: "Mở menu", exact: true }).click();
  await page
    .getByRole("navigation", { name: "Điều hướng chính" })
    .getByRole("link", { name: "Thuốc của tôi" })
    .click();
  const add = page.getByRole("button", { name: "Thêm thuốc", exact: true });
  await add.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(add).toBeFocused();
  await login(page, "admin");
  await expect(page).toHaveURL("/admin");
  await expect(
    page.getByRole("heading", { name: "Tổng quan quản trị", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("reviewer edits catalog data; staff and admin share one personnel table", async ({
  page,
}) => {
  await login(page, "reviewer");
  await page
    .getByRole("link", { name: "Rà soát dữ liệu", exact: true })
    .click();
  await page.getByLabel("Giá trị DR-01").fill("Omeprazole mẫu");
  await page.reload();
  await expect(page.getByLabel("Giá trị DR-01")).toHaveValue("Omeprazole mẫu");
  await login(page, "hcp");
  await page.goto("/hcp/data-review");
  await expect(page.getByLabel("Giá trị DR-01")).toHaveCount(0);
  await expect(page).toHaveURL('/hcp');
  await expect(page.getByRole('link', { name: 'Rà soát dữ liệu', exact: true })).toHaveCount(0);
  await login(page, "support");
  await page.getByRole("link", { name: "Nhân sự", exact: true }).click();
  await expect(page.getByRole("table")).toContainText("NS-ADMIN-01");
  await expect(page.getByRole("table")).toContainText("NS-HT-01");
  await expect(page.getByLabel("Chức danh Nguyễn Thu Hà")).toHaveCount(0);
  await login(page, "admin");
  await page.goto("/admin/staff");
  await expect(page.getByRole("table")).toContainText("Đỗ Văn Khoa");
  await page.getByLabel("Chức danh Đỗ Văn Khoa").fill("Điều phối mẫu");
  await page.goto("/admin/accounts");
  await page.getByRole("button", { name: "Đỗ Văn Khoa" }).click();
  const hcpRole = page.getByLabel("HCP cho Đỗ Văn Khoa");
  if (await hcpRole.isChecked()) {
    await hcpRole.click();
    await expect(hcpRole).not.toBeChecked();
  }
  await hcpRole.click();
  await expect(hcpRole).toBeChecked();
  await page.goto("/admin/audit");
  await expect(page.getByText("role.grant", { exact: true }).first()).toBeVisible();
  await page.goto("/admin/accounts");
  await page.getByRole("button", { name: "Đỗ Văn Khoa" }).click();
  const granted = page.getByLabel("HCP cho Đỗ Văn Khoa");
  await granted.click();
  await expect(granted).not.toBeChecked();
  await login(page, "support");
  await page.getByRole("link", { name: "Nhân sự", exact: true }).click();
  await expect(page.getByRole("table")).toContainText("Điều phối mẫu");
  await expect(page.getByLabel("Ngữ cảnh đang mở")).toHaveCount(0);
});

test("password login, locked account, multi-role context, refresh and logout", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(demoEmail.patient);
  await page.getByLabel("Mật khẩu").fill("wrong-password");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("không đúng");
  await page.getByLabel("Email").fill("locked.demo@example.com");
  await page.getByLabel("Mật khẩu").fill(demoPassword.locked);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("khóa");
  await login(page, "multi");
  await page
    .getByRole("button", { name: "Chuyên viên dữ liệu", exact: true })
    .click();
  await expect(page).toHaveURL("/reviewer");
  await expect(
    page.getByRole("link", { name: "Rà soát dữ liệu", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(page).toHaveURL("/reviewer");
  await expect(
    page
      .getByRole("navigation", { name: "Điều hướng chính" })
      .getByRole("link", { name: "Rà soát dữ liệu", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Đăng xuất", exact: true }).click();
  await page.getByRole("button", { name: "Đăng xuất", exact: true }).last().click();
  await expect(page).toHaveURL("/login");
  await page.goto("/admin");
  await expect(page).toHaveURL("/login");
});
