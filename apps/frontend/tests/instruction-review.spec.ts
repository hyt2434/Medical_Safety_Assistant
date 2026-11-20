import { test, expect } from "@playwright/test";
import { reviewInstruction } from "../src/instructionFormatting";

test("format rules preserve clinical tokens and detect only bare schedule quantities", () => {
  const example = "Sáng: 1 Chiều: 1Cách dùng: Uống; sau ăn";
  expect(reviewInstruction(example)).toEqual({ suggestion: "Sáng: 1; Chiều: 1; Cách dùng: Uống sau ăn", missingUnit: true });
  for (const text of ["Không uống trước ăn", "Sáng: 0,5 ml; Tối: 1/2 viên", "Uống 5 mcg lúc 08:30", "Sáng: 1 viên; Chiều: 1 viên", "Uống; không uống sau ăn"]) {
    const result = reviewInstruction(text);
    expect(result.missingUnit).toBe(false);
    expect((result.suggestion || text).replace(/\s/g, "")).toBe(text.replace(/\s/g, ""));
  }
  expect(reviewInstruction("Sáng: 0,5; Tối: 1/2").missingUnit).toBe(true);
  expect(reviewInstruction("").suggestion).toBeNull();
  const corrected = reviewInstruction(example).suggestion!;
  expect(reviewInstruction(corrected).suggestion).toBeNull();
});

test("instruction suggestions apply only by choice, undo and retain source history", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("mai.demo@example.com");
  await page.getByLabel("Mật khẩu").fill("Mai-patient-2026");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page).toHaveURL("/dashboard");
  await page.goto("/intake");
  await page.getByRole("button", { name: "Nhắc lại sau 7 ngày" }).click();
  const original = "Sáng: 1 Chiều: 1Cách dùng: Uống; sau ăn";
  await page.route("**/api/v1/ocr/extractions", route => route.fulfill({ json: { medication_entries: [{ extracted_name: "Example", extracted_strength: "5 mg", dosage_instructions: original }] } }));
  await page.route("**/api/reference/medication-spelling?**", route => route.fulfill({ json: { suggestions: [] } }));
  await page.getByLabel("Chọn ảnh toa thuốc", { exact: true }).setInputFiles("public/assets/prescription-sample.png");
  await page.getByRole("button", { name: "Đọc thông tin từ ảnh" }).click();
  const input = page.getByLabel("Cách dùng trên toa *", { exact: true });
  await expect(input).toHaveValue(original);
  await expect(page.getByText("Chưa rõ đơn vị ở liều", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Giữ nguyên cách dùng", exact: true }).click();
  await expect(page.getByRole("button", { name: "Áp dụng cách trình bày" })).toHaveCount(0);
  await expect(input).toHaveValue(original);
  await page.reload();
  await page.getByRole("button", { name: "Áp dụng cách trình bày" }).click();
  await expect(input).toHaveValue("Sáng: 1; Chiều: 1; Cách dùng: Uống sau ăn");
  await expect(page.getByText("Chưa rõ đơn vị ở liều", { exact: false })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Hoàn tác chỉnh cách dùng" }).click();
  await expect(input).toHaveValue(original);
  const medicine = await page.evaluate(() => JSON.parse(sessionStorage.getItem("tieu-bach-demo-v1")!).state.draft[0]);
  expect(medicine).toMatchObject({ name: "Example", strength: "5 mg", verified: false, ocrOriginalInstruction: original });
  expect(medicine.instructionCorrections.map((event: {action: string}) => event.action)).toEqual(["apply", "undo"]);
  await input.fill("Sáng: 1 viên Chiều: 1 viên");
  await expect(page.getByText("Chưa rõ đơn vị ở liều", { exact: false })).toHaveCount(0);
  await page.setViewportSize({ width: 375, height: 844 });
  await page.locator(".intake-form").screenshot({ path: test.info().outputPath("instruction-review-mobile.png") });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
