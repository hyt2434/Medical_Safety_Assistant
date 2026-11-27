import { test, expect } from '@playwright/test';
import { fixture, login } from './intake-fixture';

for (const width of [375, 1440]) {
  test(`original intake and chat layout with persisted route steps at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const state = await fixture(page);
    await login(page); await page.goto('/intake');
    await expect(page.getByRole('heading', { name: 'Nhập toa thuốc', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Chọn hoặc kéo ảnh toa vào đây', exact: false })).toBeEnabled();
    const columns = await page.locator('.intake-grid').evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length);
    expect(columns).toBe(width === 1440 ? 2 : 1);
    await page.screenshot({ path: testInfo.outputPath(`intake-${width}.png`), fullPage: true });
    await page.getByLabel('Chọn ảnh toa thuốc', { exact: true }).setInputFiles('public/assets/prescription-sample.png');
    await expect(page.locator('.prescription-preview img')).toBeVisible();
    await page.getByRole('button', { name: 'Đọc thông tin từ ảnh', exact: true }).click();
    await page.getByLabel('Liều mỗi lần #1', { exact: true }).fill('hai viên');
    await expect(page.getByRole('button', { name: 'Tiếp tục xác nhận', exact: false })).toBeDisabled();
    await page.getByRole('button', { name: 'Lưu thay đổi thuốc 1', exact: true }).click();
    await page.getByRole('button', { name: 'Tiếp tục xác nhận', exact: false }).click();
    await expect(page).toHaveURL('/verify'); await page.reload();
    await expect(page.locator('.confirmation-table')).toContainText('hai viên');
    await page.screenshot({ path: testInfo.outputPath(`verify-${width}.png`), fullPage: true });
    await page.getByRole('region', { name: 'Bản nháp đã lưu trên máy chủ' }).getByRole('checkbox').check();
    await page.getByRole('button', { name: 'Xác nhận danh sách', exact: true }).click();
    await expect(page).toHaveURL('/results');
    await expect(page.locator('.result-banner')).toContainText('Thuốc chưa được đánh giá');
    expect(state.calls.filter(call => call.path.endsWith('/actions'))).toHaveLength(0);
    await page.screenshot({ path: testInfo.outputPath(`results-${width}.png`), fullPage: true });
    await page.goto('/chat');
    await expect(page.locator('.chat-sidebar')).toBeVisible();
    await expect(page.locator('.chat-compose')).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`chat-${width}.png`), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
