import { test, expect } from '@playwright/test';
import { fixture, login } from './intake-fixture';

test('spelling corrections require a choice and Save; preserve strength and remain unconfirmed', async ({ page }) => {
  const state = await fixture(page, { name_raw: 'Desloratad1ne', strength_raw: '5 mg', instructions_raw: '' });
  await page.route('**/api/reference/medication-spelling?**', route => route.fulfill({ json: { suggestions:
    new URL(route.request().url()).searchParams.get('q') === 'Desloratad1ne' ? [
      { id: 'test-product', name: 'Desloratadine', strength: '5mg', form: 'Viên nén', source_record_id: 'test-source' }
    ] : [] } }));
  await login(page); await page.goto('/intake');
  await page.getByLabel('Chọn ảnh toa thuốc', { exact: true }).setInputFiles('public/assets/prescription-sample.png');
  await page.getByRole('button', { name: 'Đọc thông tin từ ảnh', exact: true }).click();
  const name = page.getByLabel('Tên thuốc #1', { exact: true });
  await page.getByRole('button', { name: 'Giữ nguyên tên', exact: true }).click();
  await expect(name).toHaveValue('Desloratad1ne');
  await page.reload();
  await page.getByRole('button', { name: 'Dùng tên Desloratadine', exact: true }).click();
  await expect(name).toHaveValue('Desloratadine');
  expect(state.review.entries[0].medication.name_raw).toBe('Desloratad1ne');
  await page.getByRole('button', { name: 'Hoàn tác đổi tên', exact: true }).click();
  await expect(name).toHaveValue('Desloratad1ne');
  await page.reload();
  await page.getByRole('button', { name: 'Dùng tên Desloratadine', exact: true }).click();
  await page.getByRole('button', { name: 'Lưu thay đổi thuốc 1', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Lưu thay đổi thuốc 1', exact: true })).toBeDisabled();
  await page.reload();
  await expect(name).toHaveValue('Desloratadine');
  await expect(page.getByLabel('Hàm lượng #1', { exact: true })).toHaveValue('5 mg');
  expect(state.review.entries[0].confirmed).toBe(false);
  expect(state.review.entries[0].medication.instructions_raw).toBeNull();
  await page.setViewportSize({ width: 375, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
