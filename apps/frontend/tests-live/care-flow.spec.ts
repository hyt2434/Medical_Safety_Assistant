import { test, expect, type Page } from "@playwright/test";
import { addProduct, idle, freshIntake, signedIn } from "./helpers";

// End-to-end in two browsers: patient intake → assessment → schedule → HCP review → activation.
test.describe.configure({ mode: "serial" });

// A unique dose label makes this run's cards identifiable among earlier test data.
const DOSE = `1 viên #${Date.now() % 100000}`;
let patient: Page;
let hcp: Page;

test.beforeAll(async ({ browser }) => {
  patient = (await signedIn(browser, "patient")).page;
  hcp = (await signedIn(browser, "hcp")).page;
});

test("MAN/VER: manual intake → confirm → assessment shows the Major interaction", async () => {
  await freshIntake(patient, "manual");
  await addProduct(patient, "Hatacil 500", "500mg", undefined, DOSE);
  const review = await addProduct(patient, "DOMESIM 20 mg", "20mg", undefined, DOSE);
  expect(review.state).toBe("AWAITING_CONFIRMATION");
  await patient.getByRole("button", { name: "Tiếp tục xác nhận", exact: false }).click();
  await expect(patient).toHaveURL(/\/verify/);

  const confirmButton = patient.getByRole("button", { name: "Xác nhận danh sách", exact: true });
  await expect(confirmButton).toBeDisabled(); // VER-02
  await patient.getByText("Tôi đã xem lại và đồng ý xác nhận đúng bản nháp này.").click();
  const confirmed = patient.waitForResponse((r) => r.url().endsWith("/api/v1/intake/confirm"));
  await confirmButton.click();
  expect((await confirmed).status()).toBe(200);
  await expect(patient).toHaveURL(/\/results/);

  const assessed = patient.waitForResponse((r) => r.url().endsWith("/api/v1/intake/actions"));
  await patient.getByRole("button", { name: "Nhận diện và đánh giá tương tác", exact: true }).click();
  expect((await assessed).status()).toBe(200);
  const result = patient.getByRole("region", { name: "Kết quả tương tác thực tế" });
  await expect(result).toBeVisible();
  await expect(result).toContainText(/MAJOR|Major/);
  await expect(result).toContainText("PARTIAL");
  await patient.screenshot({ path: "../../artifacts/acceptance/screens/results-major.png", fullPage: true });
});

test("REM-03/05/12: create a schedule from the label, reminder needs HCP review", async () => {
  await patient.goto("/reminders/new");
  const entries = patient.getByLabel("Thuốc đã xác nhận");
  await expect(entries.locator("option", { hasText: "Hatacil 500" }).first()).toBeAttached();
  await entries.selectOption({ label: "Hatacil 500" });
  await expect(patient.getByLabel("Liều trên toa")).toHaveValue(DOSE);
  await patient.getByRole("checkbox").check();

  const times = patient.getByLabel("Giờ dùng (HH:MM, phân cách bằng dấu phẩy)");
  await times.fill("8h");
  await patient.getByRole("button", { name: "Lưu lịch dùng thuốc" }).click();
  await expect(patient.getByRole("alert")).toContainText("HH:MM"); // REM-05

  await times.fill("08:00, 20:00");
  const created = patient.waitForResponse((r) => r.url().endsWith("/api/v1/reminders/schedules") && r.request().method() === "POST");
  await patient.getByRole("button", { name: "Lưu lịch dùng thuốc" }).click();
  expect((await created).status()).toBe(201);
  await expect(patient).toHaveURL(/\/reminders$/);

  const card = patient.locator(".card").filter({ hasText: DOSE }).filter({ hasText: "PATIENT_CONFIRMED" });
  await expect(card).toContainText("PATIENT_CONFIRMED");
  await card.getByRole("button", { name: "Bật nhắc", exact: true }).click();
  await expect(patient.getByRole("status").filter({ hasText: "cần chuyên gia phê duyệt" })).toBeVisible();
  await expect(card.getByLabel("Chuyên gia nhận ca")).toBeVisible();
});

test("HCP-01/03: patient sends the schedule to An with explicit consent", async () => {
  const card = patient.locator(".card").filter({ hasText: DOSE }).filter({ hasText: "PATIENT_CONFIRMED" });
  const send = card.getByRole("button", { name: "Gửi ca cho chuyên gia" });
  await card.getByLabel("Chuyên gia nhận ca").selectOption({ label: "Lê Minh An" });
  await expect(send).toBeDisabled();
  await card.getByRole("checkbox").check();
  const sent = patient.waitForResponse((r) => r.url().endsWith("/api/v1/hcp/cases") && r.request().method() === "POST");
  await send.click();
  expect((await sent).status()).toBe(201);
  await expect(patient.getByRole("status").filter({ hasText: "Đã gửi ca" })).toBeVisible();
  await expect(card.getByRole("region", { name: "Lịch đề xuất" })).toContainText("Chờ rà soát");
});

test("HCP-06/07/08/16: HCP opens the newest case, messages and approves", async () => {
  await hcp.goto("/hcp/queue");
  await expect(hcp.getByRole("heading", { name: "Hàng đợi chuyên gia" })).toBeVisible();
  await hcp.getByRole("link", { name: "Mở ca", exact: true }).first().click();
  await expect(hcp.getByRole("heading", { name: /SCHEDULE · OPEN/ })).toBeVisible();
  await expect(hcp.getByText(`Hatacil 500 · ${DOSE} · 08:00, 20:00 · Asia/Ho_Chi_Minh`)).toBeVisible();
  await expect(hcp.getByText(/MAJOR:/).first()).toBeVisible();

  await hcp.getByLabel("Tin nhắn", { exact: true }).fill("Bạn có đang uống thuốc khác không?");
  await hcp.getByRole("button", { name: "Gửi tin nhắn", exact: true }).click();
  await expect(hcp.getByText("Bạn có đang uống thuốc khác không?")).toBeVisible();

  await hcp.getByRole("combobox", { name: "Quyết định", exact: true }).selectOption("APPROVED");
  await hcp.getByLabel("Nhận định chuyên môn").fill("Đồng ý, theo dõi đau cơ khi dùng cùng simvastatin.");
  await hcp.getByRole("button", { name: "Lưu kết quả rà soát" }).click();
  await expect(hcp.getByText(/APPROVED: Đồng ý/)).toBeVisible();
  await expect(hcp.getByRole("button", { name: "Lưu kết quả rà soát" })).toHaveCount(0); // HCP-13
  await hcp.screenshot({ path: "../../artifacts/acceptance/screens/hcp-case-approved.png", fullPage: true });
});

test("HCP-16/17: patient sees the approval, activates, then toggles the reminder", async () => {
  await patient.goto("/reminders");
  await idle(patient);
  const approved = patient.locator(".card").filter({ hasText: DOSE }).filter({ hasText: "APPROVED" });
  const activate = approved.getByRole("button", { name: "Kích hoạt lịch đã duyệt" });
  await expect(activate).toBeVisible();
  const activated = patient.waitForResponse((r) => r.url().includes("/activate"));
  await activate.click();
  expect((await activated).status()).toBe(200);
  const card = patient.locator(".card").filter({ hasText: DOSE }).filter({ hasText: "HCP_VERIFIED" });
  await expect(card.getByRole("button", { name: "Tắt nhắc", exact: true })).toBeVisible();
  await card.getByRole("button", { name: "Tắt nhắc", exact: true }).click();
  await expect(card.getByRole("button", { name: "Bật nhắc", exact: true })).toBeVisible();
  await card.getByRole("button", { name: "Bật nhắc", exact: true }).click();
  await expect(card.getByRole("button", { name: "Tắt nhắc", exact: true })).toBeVisible();
  await expect(patient.getByText("Tuân thủ 7 ngày")).toBeVisible();
  await patient.screenshot({ path: "../../artifacts/acceptance/screens/reminders-active.png", fullPage: true });
});

test("Patient messages the HCP from 'Ca đã gửi'", async () => {
  await patient.getByRole("button", { name: "Xem trao đổi" }).first().click();
  await patient.getByLabel("Tin nhắn cho chuyên gia").fill("Tôi chỉ uống hai thuốc này.");
  await patient.getByRole("button", { name: "Gửi tin nhắn", exact: true }).first().click();
  await expect(patient.getByText("Tôi chỉ uống hai thuốc này.")).toBeVisible();
});
