import { chromium } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Capture into staging first. Replacing the original prototype is a separate step.
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const output = path.join(root, "artifacts", "ui-prototype-screens");
const base = process.env.PREVIEW_URL || "http://127.0.0.1:5173";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
  executablePath:
    process.env.CHROME_PATH ||
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 1,
  reducedMotion: "reduce",
  locale: "vi-VN",
  timezoneId: "Asia/Bangkok",
});
const page = await context.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
page.on("requestfailed", (request) => {
  if (!request.url().includes("/favicon.ico"))
    errors.push(`${request.method()} ${request.url()}`);
});
const captures = [];

async function go(route) {
  await page.goto(`${base}${route}`, { waitUntil: "networkidle" });
  await page.locator("main, .not-found").waitFor();
}
async function capture(name, title) {
  // Let SPA navigation/state updates commit before measuring and capturing.
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all(
      [...document.images].map((image) => image.decode().catch(() => {})),
    );
    window.scrollTo(0, 0);
    if (document.activeElement instanceof HTMLElement)
      document.activeElement.blur();
  });
  await page.screenshot({
    path: path.join(output, `${name}.png`),
    fullPage: true,
    animations: "disabled",
  });
  const dimensions = await page.evaluate(() => ({
    width: innerWidth,
    height: Math.max(document.documentElement.scrollHeight, innerHeight),
  }));
  captures.push({
    file: `${name}.png`,
    title,
    route: new URL(page.url()).pathname,
    ...dimensions,
  });
  console.log(
    `${name}.png · ${title} · ${dimensions.width} × ${dimensions.height}`,
  );
}
async function login(hcp = false) {
  await go(hcp ? "/hcp/login" : "/login");
  await page
    .getByRole("button", {
      name: hcp ? "Vào bản mẫu HCP" : "Vào bản mẫu người dùng",
      exact: true,
    })
    .click();
  await page.waitForURL(hcp ? "**/hcp" : "**/dashboard");
}

try {
  await go("/");
  await capture("index", "Trang chủ");
  await go("/login");
  await capture("login", "Đăng nhập người dùng");
  await go("/hcp/login");
  await capture("hcp-login", "Đăng nhập HCP");
  await go("/policy");
  await capture("policy", "Quyền riêng tư và giới hạn");
  await login();
  await capture("dashboard", "Tổng quan người dùng");
  await go("/medications");
  await capture("medications", "Thuốc của tôi");
  await go("/profile");
  await capture("profile", "Hồ sơ và trợ năng");
  await go("/reminders");
  await capture("reminders", "Lịch thuốc và ghi nhận dùng thuốc");
  await go("/intake");
  await page
    .getByRole("button", { name: "Dùng bộ dữ liệu mẫu", exact: true })
    .click();
  await capture("intake", "Nhập toa thuốc — bộ dữ liệu mẫu");
  await page.getByRole("button", { name: "Kiểm tra lại", exact: true }).click();
  await page.waitForURL("**/verify");
  for (const box of await page
    .getByRole("checkbox", { name: "Tôi đã đối chiếu" })
    .all())
    await box.check();
  await page
    .getByRole("checkbox", { name: "Tôi đang dùng dữ liệu giả" })
    .check();
  await capture("verify", "Xác nhận thông tin thuốc");
  await page
    .getByRole("button", { name: "Xem kết quả mẫu", exact: true })
    .click();
  await page.waitForURL("**/results");
  await page
    .getByRole("heading", { name: "Kết quả kiểm tra toa thuốc", exact: true })
    .waitFor();
  await capture("results", "Kết quả mẫu cần chuyên gia review");
  await page
    .getByRole("link", { name: "Soạn yêu cầu mẫu", exact: true })
    .click();
  await page.waitForURL("**/review-request");
  await page
    .getByLabel("Bạn muốn hỏi điều gì?")
    .fill(
      "Tôi cần trao đổi thêm điều gì với bác sĩ về hai thuốc trong toa mẫu này?",
    );
  await page.getByRole("checkbox", { name: "Tôi đồng ý" }).check();
  await capture("hcp-review", "Người dùng gửi yêu cầu chuyên gia");
  await page
    .getByRole("button", { name: "Tạo yêu cầu mẫu", exact: true })
    .click();
  await page.waitForURL("**/results");
  await capture("results-pending", "Kết quả — đang chờ phản hồi HCP");
  await go("/chat");
  await page
    .getByRole("button", { name: "Nguồn dữ liệu ở đâu?", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Tôi nên hỏi dược sĩ gì?", exact: true })
    .click();
  // Keep the most recent exchange visible inside the chat scroll area.
  await page.evaluate(() => {
    const log = document.querySelector(".chat-messages");
    if (log) log.scrollTop = log.scrollHeight;
  });
  await capture("chatbot", "Chat Tiểu Bạch và lịch sử câu hỏi");
  const caseId = await page.evaluate(
    () =>
      JSON.parse(sessionStorage.getItem("tieu-bach-demo-v1")).state.cases.find(
        (c) => c.source === "Người dùng phiên hiện tại",
      ).id,
  );
  await login(true);
  await capture("professional", "Tổng quan chuyên môn HCP");
  await go("/hcp/queue");
  await capture("hcp-queue", "Hàng chờ review");
  await go("/hcp/patients");
  await capture("hcp-patients", "Danh sách bệnh nhân mẫu");
  await go("/hcp/profile");
  await capture("hcp-profile", "Hồ sơ chuyên môn HCP");
  await go("/hcp/database");
  await capture("hcp-database", "Trạng thái nguồn dữ liệu dược");
  await go("/hcp/assessment");
  await capture("hcp-assessment-list", "Chọn ca đánh giá tương tác");
  await go(`/hcp/case/${caseId}`);
  await capture("hcp-case", "Kiểm tra và đối chiếu thuốc trong ca");
  await page
    .getByRole("button", { name: "Xác nhận thuốc", exact: true })
    .click();
  await page.waitForURL(`**/hcp/assessment/${caseId}`);
  await capture("hcp-assessment", "Đánh giá tương tác của ca cụ thể");
  await page.getByRole("link", { name: "Soạn phản hồi", exact: true }).click();
  await page.waitForURL(`**/hcp/confirmation/${caseId}`);
  await page.getByRole("checkbox", { name: "Xác nhận lịch trên toa" }).check();
  await page.getByRole("checkbox", { name: "Tôi đã phân biệt" }).check();
  await capture("hcp-confirmation", "Soạn và xác nhận phản hồi HCP");
  await page
    .getByRole("button", { name: "Ghi nhận phản hồi mẫu", exact: true })
    .click();
  await login();
  await go("/results");
  await capture("results-reviewed", "Người dùng xem phản hồi HCP");
  await go("/login");
  await page
    .getByRole("button", { name: "Truy cập quản trị mẫu", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Vào bản mẫu quản trị", exact: true })
    .click();
  await capture("admin", "Tổng quan quản trị");
  await go("/khong-tim-thay");
  await capture("not-found", "Trang không tìm thấy");
  if (errors.length) throw new Error(`Browser errors: ${errors.join("; ")}`);
  await writeFile(
    path.join(output, "screens.json"),
    JSON.stringify(
      {
        capturedAt: new Date().toISOString(),
        viewport: "1440 × 1000, full page",
        captures,
      },
      null,
      2,
    ) + "\n",
  );
  console.log(`Captured and checked ${captures.length} screens in ${output}`);
} finally {
  await browser.close();
}
