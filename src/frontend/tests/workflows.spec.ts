import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";

test("chat history survives navigation and reload; mascot opens chat for each role", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("link", { name: "Mở chat Tiểu Bạch", exact: true })
    .click();
  await expect(page).toHaveURL("/login");
  await page
    .getByRole("button", { name: "Vào bản mẫu người dùng", exact: true })
    .click();
  await expect(page).toHaveURL("/chat");
  await expect(
    page.getByRole("link", { name: "Mở chat Tiểu Bạch", exact: true }),
  ).toHaveCount(0);
  const history = page.getByRole("navigation", { name: "Lịch sử câu hỏi" });
  await page
    .getByRole("button", { name: "Nguồn dữ liệu ở đâu?", exact: true })
    .click();
  await page
    .getByLabel("Nhập câu hỏi cho Tiểu Bạch")
    .fill("Tôi nên hỏi dược sĩ điều gì?");
  await page.getByRole("button", { name: "Gửi câu hỏi", exact: true }).click();
  await expect(history.getByRole("button")).toHaveCount(2);
  await page.goto("/medications");
  await page
    .getByRole("link", { name: "Mở chat Tiểu Bạch", exact: true })
    .click();
  await expect(history.getByRole("button")).toHaveCount(2);
  await page.reload();
  await expect(history.getByRole("button")).toHaveCount(2);
  await page.getByLabel("Tìm trong lịch sử câu hỏi").fill("Nguồn");
  await expect(history.getByRole("button")).toHaveCount(1);
  await history.getByRole("button").click();
  await expect(page.locator(".chat-message.user.selected")).toContainText(
    "Nguồn dữ liệu ở đâu?",
  );
  await page
    .getByRole("button", { name: "Xóa lịch sử chat", exact: true })
    .click();
  await page.getByRole("button", { name: "Giữ lịch sử", exact: true }).click();
  await expect(history.getByRole("button")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Xóa lịch sử chat", exact: true })
    .click();
  await page.getByRole("button", { name: "Xóa lịch sử", exact: true }).click();
  await expect(history.getByRole("button")).toHaveCount(0);
  await page.reload();
  await expect(history.getByRole("button")).toHaveCount(0);
  await login(page, true);
  await page
    .getByRole("link", { name: "Mở chat Tiểu Bạch", exact: true })
    .click();
  await expect(page).toHaveURL("/chat");
  await expect(
    page
      .getByRole("navigation", { name: "Điều hướng chính" })
      .getByRole("link", { name: "Tổng quan HCP", exact: true }),
  ).toBeVisible();
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
  await page
    .getByRole("navigation", { name: "Điều hướng trang chủ" })
    .getByRole("link", { name: "Về tổng quan", exact: true })
    .click();
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
  await login(page, true);
  await page.goto("/");
  await page
    .getByRole("navigation", { name: "Điều hướng trang chủ" })
    .getByRole("link", { name: "Về HCP", exact: true })
    .click();
  await expect(page).toHaveURL("/hcp");
});

async function login(page: Page, hcp = false) {
  await page.goto(hcp ? "/hcp/login" : "/login");
  await page
    .getByRole("button", {
      name: hcp ? "Vào bản mẫu HCP" : "Vào bản mẫu người dùng",
      exact: true,
    })
    .click();
  await expect(page).toHaveURL(hcp ? "/hcp" : "/dashboard");
}

async function verifiedSample(page: Page) {
  await page.goto("/intake");
  await page.getByRole("button", { name: "Dùng bộ dữ liệu mẫu" }).click();
  await page.getByRole("button", { name: "Kiểm tra lại", exact: true }).click();
  await page.getByRole("checkbox", { name: "Tôi đã đối chiếu" }).nth(0).check();
  await page.getByRole("checkbox", { name: "Tôi đã đối chiếu" }).nth(1).check();
  await page
    .getByRole("checkbox", { name: "Tôi đang dùng dữ liệu giả" })
    .check();
  await page.getByRole("button", { name: "Xem kết quả mẫu" }).click();
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
  await page.getByRole("link", { name: "Soạn yêu cầu mẫu" }).click();
  await page
    .getByLabel("Bạn muốn hỏi điều gì?")
    .fill("Xin kiểm tra lại tình huống toa mẫu.");
  await page.getByRole("checkbox", { name: "Tôi đồng ý" }).check();
  await page.getByRole("button", { name: "Tạo yêu cầu mẫu" }).click();
  await expect(page.getByText("Chờ phản hồi", { exact: true })).toBeVisible();
  await login(page, true);
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
  await page.getByRole("button", { name: "Ghi nhận phản hồi mẫu" }).click();
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

test("unverified input is blocked, edits invalidate results, unknown drugs stay unassessed", async ({
  page,
}) => {
  await login(page);
  await page.goto("/intake");
  await page.getByRole("button", { name: "Dùng bộ dữ liệu mẫu" }).click();
  await page.getByRole("button", { name: "Kiểm tra lại", exact: true }).click();
  await page.getByRole("button", { name: "Xem kết quả mẫu" }).click();
  await expect(page.getByRole("status")).toContainText("xác nhận từng thuốc");
  await verifiedSample(page);
  await page.goto("/intake");
  await page.getByLabel("Tên trên toa").first().fill("Thuốc chưa ánh xạ");
  await page.goto("/results");
  await expect(
    page.getByRole("heading", { name: "Chưa có kết quả hợp lệ" }),
  ).toBeVisible();
  await page.goto("/verify");
  for (const box of await page
    .getByRole("checkbox", { name: "Tôi đã đối chiếu" })
    .all())
    await box.check();
  await page.getByRole("button", { name: "Xem kết quả mẫu" }).click();
  await expect(
    page.getByRole("heading", { name: "Chưa đủ thông tin để đánh giá" }),
  ).toBeVisible();
  await page.goto("/verify");
  await page
    .getByRole("checkbox", { name: "Tôi đang dùng dữ liệu giả" })
    .check();
  await page.getByRole("button", { name: "Xem kết quả mẫu" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Thuốc chưa được đánh giá",
      exact: true,
    }),
  ).toBeVisible();
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
  await expect(page.getByRole("status")).toContainText("Chưa có OCR");
  await expect(
    page.getByRole("heading", { name: "Chưa có thuốc được nhập" }),
  ).toBeVisible();
  await page.goto("/medications");
  await page.getByLabel("Tìm thuốc hoặc hoạt chất").fill("Metformin");
  await expect(page.locator(".medicine-cards .card")).toHaveCount(1);
  await page.getByLabel("Tìm thuốc hoặc hoạt chất").fill("zzzzzzz");
  await expect(
    page.getByRole("heading", { name: "Không tìm thấy thuốc" }),
  ).toBeVisible();
  await page.goto("/profile");
  await page.getByLabel("Họ và tên").fill("Người dùng thử");
  await page.getByRole("button", { name: "Lưu hồ sơ mẫu" }).click();
  await page.reload();
  await expect(page.getByLabel("Họ và tên")).toHaveValue("Người dùng thử");
  await page.goto("/reminders");
  await page.locator(".date-strip button").last().click();
  await expect(
    page.getByRole("heading", { name: "Chưa có lịch cho ngày này" }),
  ).toBeVisible();
  await page.goto("/chat");
  await page.getByRole("button", { name: "Nguồn dữ liệu ở đâu?" }).click();
  await expect(page.getByRole("log")).toContainText("chưa kết nối hai nguồn");
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
    await login(page, true);
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
  await page.goto("/login");
  await page.getByRole("button", { name: "Truy cập quản trị mẫu" }).click();
  await page
    .getByRole("button", { name: "Vào bản mẫu quản trị", exact: true })
    .click();
  await expect(page).toHaveURL("/admin");
  await expect(
    page.getByRole("heading", { name: "Không gian quản trị", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
