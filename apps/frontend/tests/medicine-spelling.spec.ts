import { test, expect } from "@playwright/test";

test("OCR spelling is opt-in, reversible, and incomplete fields are highlighted", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("mai.demo@example.com");
  await page.getByLabel("Mật khẩu").fill("Mai-patient-2026");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page).toHaveURL("/dashboard");
  await page.goto("/intake");
  await page.getByRole("button", { name: "Nhắc lại sau 7 ngày", exact: true }).click();
  await page.route("**/api/v1/ocr/extractions", route => route.fulfill({ json: { medication_entries: [
    { extracted_name: "Desloratad1ne", extracted_strength: "5 mg", dosage_instructions: "" },
  ] } }));
  await page.route("**/api/reference/medication-spelling?**", route => {
    const q = new URL(route.request().url()).searchParams.get("q");
    return route.fulfill({ json: { suggestions: q === "Desloratad1ne" ? [
      { id: "test-product", name: "Desloratadine", strength: "5mg", form: "Viên nén", source_record_id: "test-source" },
    ] : [] } });
  });
  await page.getByLabel("Chọn ảnh toa thuốc", { exact: true }).setInputFiles("public/assets/prescription-sample.png");
  await page.getByRole("button", { name: "Đọc thông tin từ ảnh" }).click();
  const name = page.getByLabel("Tên trên toa *", { exact: true });
  const instruction = page.getByLabel("Cách dùng trên toa *", { exact: true });
  await expect(name).toHaveValue("Desloratad1ne");
  await expect(instruction).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByText("Cần bổ sung: cách dùng.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Giữ nguyên tên", exact: true }).click();
  await expect(name).toHaveValue("Desloratad1ne");
  await name.fill("Desloratad1n");
  await name.fill("Desloratad1ne ");
  await name.fill("Desloratad1ne");
  // Revisit remounts the suggestion UI while preserving the OCR draft.
  await page.reload();
  await expect(page.getByRole("button", { name: "Dùng tên Desloratadine", exact: true })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 844 });
  await page.locator(".intake-form").screenshot({ path: test.info().outputPath("spelling-suggestions-mobile.png") });
  await page.getByRole("button", { name: "Dùng tên Desloratadine", exact: true }).click();
  await expect(name).toHaveValue("Desloratadine");
  await expect(page.getByLabel("Hàm lượng *", { exact: true })).toHaveValue("5 mg");
  const draft = await page.evaluate(() => JSON.parse(sessionStorage.getItem("tieu-bach-demo-v1") || "{}").state.draft[0]);
  expect(draft).toMatchObject({ verified: false, ocrOriginalName: "Desloratad1ne", instruction: "" });
  expect(draft.nameCorrections[0]).toMatchObject({ action: "apply", catalogId: "test-product", from: "Desloratad1ne", to: "Desloratadine" });
  await page.getByRole("button", { name: "Hoàn tác đổi tên" }).click();
  await expect(name).toHaveValue("Desloratad1ne");
  await page.setViewportSize({ width: 375, height: 844 });
  await page.screenshot({ path: test.info().outputPath("spelling-incomplete-mobile.png"), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await instruction.fill("Theo toa gốc");
  await expect(instruction).toHaveAttribute("aria-invalid", "false");
  await expect(page.locator(".medicine-editor-incomplete")).toHaveCount(0);
  await expect(page.getByLabel("Hoạt chất (nếu đã biết)", { exact: true })).toHaveValue("");
  await name.fill("Tên chưa rõ");
  await expect(name).toHaveAttribute("aria-invalid", "true");
  await page.unroute("**/api/reference/medication-spelling?**");
  await page.route("**/api/reference/medication-spelling?**", route => route.fulfill({ status: 503, json: { detail: "Unavailable" } }));
  await name.fill("Another name");
  await expect(page.getByText("Chưa tải được gợi ý.", { exact: false })).toBeVisible();
  await expect(name).toHaveValue("Another name");
});
