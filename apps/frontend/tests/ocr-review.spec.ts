import { test, expect } from "@playwright/test";

test("persisted OCR edits must be reviewed before confirmation and safety requests", async ({ page }) => {
  // HTTP fixtures isolate the UI contract; real OCR/PostgreSQL is tested separately.
  const calls: string[] = [];
  let current = {
    workflow_id: "11111111-1111-4111-8111-111111111111", revision: 1,
    state: "AWAITING_CONFIRMATION", assistant_message: "Hãy xem lại bản nháp",
    entries: [{ entry_version_id: "22222222-2222-4222-8222-222222222222",
      medication: { name_raw: "Panadol Viên Sui", strength_raw: "500mg", dose_raw: "1 viên" } as Record<string, unknown> }],
  };
  await page.route("**/api/v1/intake/**", async route => {
    const path = new URL(route.request().url()).pathname;
    calls.push(path);
    if (path.endsWith("/capabilities")) return route.fulfill({ json: { persistent_intake: true } });
    if (path.endsWith("/workflows")) return route.fulfill({ json: current });
    if (path.endsWith("/ocr")) return route.fulfill({ json: { review: current, ocr: {
      medication_entries: [{ extracted_name: "Panadol Viên Sui", extracted_strength: "500mg", dosage_instructions: "Uống sáng 1 viên" }],
      extraction_run: { raw_output: { ocr: { text: "Panadol Viên Sui 500mg" }, parsed: { medications: [], warnings: [] } } },
    } } });
    const body = route.request().postDataJSON();
    expect(body).not.toHaveProperty("owner");
    expect(body).not.toHaveProperty("user_id");
    expect(body.workflow_id).toBe(current.workflow_id);
    expect(body.revision).toBe(current.revision);
    if (path.endsWith("/ocr/edit")) {
      expect(body.medication.name_raw).toBe("Panadol Viên Sủi");
      expect(body.medication.dosage_form_raw).toBe("Viên sủi");
      expect(body.medication.dose_raw).toBe("một viên");
      current = { ...current, revision: current.revision + 1,
        entries: [{ ...current.entries[0], medication: body.medication }] };
    } else if (path.endsWith("/confirm")) {
      expect(body.explicit_confirmation).toBe(true);
      current = { ...current, revision: current.revision + 1, state: "COMPLETED" };
    } else if (path.endsWith("/actions")) {
      expect(body.action).toBe("ASSESS");
      expect(body.explicit_request).toBe(true);
      current = { ...current, revision: current.revision + 1, assistant_message: "Moderate · PARTIAL" };
    } else throw new Error(`Unexpected intake request: ${path}`);
    return route.fulfill({ json: current });
  });
  await page.goto("/login");
  await page.getByLabel("Email").fill("mai.demo@example.com");
  await page.getByLabel("Mật khẩu").fill("Mai-patient-2026");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page).toHaveURL("/dashboard");
  await page.getByRole("button", { name: "Nhắc lại sau 7 ngày", exact: true }).click();
  await page.goto("/intake");
  await page.getByLabel("Chọn ảnh toa thuốc", { exact: true }).setInputFiles("public/assets/prescription-sample.png");
  await page.getByRole("button", { name: "Đọc thông tin từ ảnh" }).click();
  const pane = page.getByRole("region", { name: "Bản nháp đã lưu trên máy chủ" });
  const confirm = pane.getByRole("button", { name: "Xác nhận danh sách và đánh giá" });
  await expect(confirm).toBeDisabled();
  await page.getByLabel("Tên trên toa *", { exact: true }).fill("Panadol Viên Sủi");
  await page.getByLabel("Dạng thuốc trên nhãn").fill("Viên sủi");
  await page.getByLabel("Liều mỗi lần trên toa").fill("một viên");
  await page.getByLabel("Thời điểm trên toa").fill("mỗi sáng");
  await pane.getByRole("button", { name: "Lưu thay đổi và xem bản xác nhận" }).click();
  await pane.getByRole("checkbox").check();
  await expect(confirm).toBeEnabled();
  await page.getByLabel("Thời điểm trên toa").fill("mỗi sáng sau ăn");
  await expect(confirm).toBeDisabled();
  expect(calls.some(path => path.endsWith("/confirm") || path.endsWith("/actions"))).toBe(false);
  await pane.getByRole("button", { name: "Lưu thay đổi và xem bản xác nhận" }).click();
  await pane.getByRole("checkbox").check();
  await confirm.click();
  await expect(pane.getByRole("status")).toHaveText("Moderate · PARTIAL");
  expect(calls.slice(-2)).toEqual(["/api/v1/intake/confirm", "/api/v1/intake/actions"]);
  expect(current.entries[0].medication.administrations).toEqual([
    { timing_raw: "mỗi sáng sau ăn", dose_raw: "một viên", timing_slots_raw: [] },
  ]);
});

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
  await expect(page.getByRole("alert")).toContainText("Đã đọc được chữ");
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
