import { test, expect } from "@playwright/test";

test("crop coordinates reach OCR; users see a review warning instead of technical evidence", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("mai.demo@example.com");
  await page.getByLabel("Mật khẩu").fill("Mai-patient-2026");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page).toHaveURL("/dashboard");
  await page.goto("/intake");
  await page
    .getByRole("button", { name: "Nhắc lại sau 7 ngày", exact: true })
    .click();
  await page
    .getByLabel("Chọn ảnh toa thuốc", { exact: true })
    .setInputFiles("public/assets/prescription-sample.png");
  await page.getByText("Chọn vùng cần đọc", { exact: false }).click();
  const keyboardToggle = page.getByRole("button", {
    name: "Điều chỉnh bằng bàn phím",
    exact: true,
  });
  await expect(keyboardToggle).toHaveAttribute("aria-expanded", "false");
  await keyboardToggle.focus();
  await keyboardToggle.press("Enter");
  await page.getByLabel("Phải", { exact: true }).fill("62");
  await keyboardToggle.press("Space");
  await expect(keyboardToggle).toHaveAttribute("aria-expanded", "false");
  let requestBody = "";
  await page.route("**/api/v1/ocr/extractions", async (route) => {
    requestBody = route.request().postData() || "";
    await route.fulfill({
      json: {
        medication_entries: [],
        extraction_run: {
          raw_output: {
            ocr: { text: "Example 10mg — văn bản đọc được" },
            parsed: {
              warnings: [],
              medications: [],
              review_guidance: {
                message:
                  "Đã đọc được chữ nhưng chưa tách được danh sách thuốc.",
              },
            },
          },
        },
      },
    });
  });
  await page.getByRole("button", { name: "Đọc thông tin từ ảnh" }).click();
  await expect(page.getByRole("status")).toContainText("Đã đọc được chữ");
  expect(requestBody).toContain('name="region"');
  expect(requestBody).toContain('"right":0.62');
  await expect(
    page.getByText("Văn bản đọc được từ ảnh", { exact: true }),
  ).toHaveCount(0);
  await page.unroute("**/api/v1/ocr/extractions");
  await page.route("**/api/v1/ocr/extractions", (route) =>
    route.fulfill({
      json: {
        medication_entries: [
          {
            extracted_name: "Example",
            extracted_strength: "10mg",
            dosage_instructions: "Uống sáng",
          },
        ],
        extraction_run: {
          raw_output: {
            ocr: { text: "Example 10mg" },
            parsed: {
              warnings: ["Chỉ đọc vùng đã chọn."],
              medications: [
                {
                  name_raw: "Example",
                  evidence_text: "Example 10mg",
                  product_review_candidates: [
                    {
                      candidate_fields: {
                        name_raw: "Other",
                        strength_raw: "20mg",
                      },
                    },
                  ],
                },
              ],
            },
          },
        },
      },
    }),
  );
  await page.getByRole("button", { name: "Đọc thông tin từ ảnh" }).click();
  await expect(page.getByRole("status")).toContainText("Đã đọc thông tin");
  await expect(
    page.getByRole("note", { name: "Nhắc kiểm tra toa thuốc" }),
  ).toContainText("Dò lại toa thuốc trước khi xác nhận");
  await expect(page.getByText("Other · 20mg", { exact: true })).toHaveCount(0);
  const draft = await page.evaluate(
    () =>
      JSON.parse(sessionStorage.getItem("tieu-bach-demo-v1") || "{}").state
        .draft,
  );
  expect(draft[0]).toMatchObject({
    name: "Example",
    strength: "10mg",
    verified: false,
  });
  await page.screenshot({
    path: test.info().outputPath("ocr-review-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 375, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: test.info().outputPath("ocr-review-mobile.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Đọc toàn bộ ảnh", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Bằng chứng đọc toa" }),
  ).toHaveCount(0);
});
