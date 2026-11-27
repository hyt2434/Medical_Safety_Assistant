import { test, expect } from "@playwright/test";
import { fixture, login } from './intake-fixture';
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

test("instruction suggestions are opt-in, reversible and saved through Core", async ({ page }) => {
  const original = "Sáng: 1 Chiều: 1Cách dùng: Uống; sau ăn";
  const state = await fixture(page, { instructions_raw: original });
  await login(page); await page.goto('/intake');
  await page.getByLabel('Chọn ảnh toa thuốc', { exact: true }).setInputFiles('public/assets/prescription-sample.png');
  await page.getByRole('button', { name: 'Đọc thông tin từ ảnh', exact: true }).click();
  const input = page.getByLabel('Hướng dẫn #1', { exact: true });
  await expect(input).toHaveValue(original);
  await page.getByRole('button', { name: 'Giữ nguyên cách dùng', exact: true }).click();
  await expect(input).toHaveValue(original);
  await page.reload();
  await page.getByRole('button', { name: 'Áp dụng cách trình bày', exact: true }).click();
  await expect(input).toHaveValue('Sáng: 1; Chiều: 1; Cách dùng: Uống sau ăn');
  expect(state.review.entries[0].medication.instructions_raw).toBe(original);
  await page.getByRole('button', { name: 'Hoàn tác chỉnh cách dùng', exact: true }).click();
  await expect(input).toHaveValue(original);
  await page.reload();
  await page.getByRole('button', { name: 'Áp dụng cách trình bày', exact: true }).click();
  await page.getByRole('button', { name: 'Lưu thay đổi thuốc 1', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Lưu thay đổi thuốc 1', exact: true })).toBeDisabled();
  await page.reload();
  await expect(input).toHaveValue('Sáng: 1; Chiều: 1; Cách dùng: Uống sau ăn');
  expect(state.review.entries[0].confirmed).toBe(false);
  await expect(page.getByText('Chưa rõ đơn vị ở liều', { exact: false })).toBeVisible();
});
