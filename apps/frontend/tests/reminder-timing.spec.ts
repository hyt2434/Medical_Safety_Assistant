import { test, expect } from '@playwright/test';
import { isRecentDueDose } from '../src/reminderTiming';
import type { DoseOccurrence } from '../src/api';
import { login } from './intake-fixture';

const now = Date.parse('2026-11-28T12:00:00Z');
function dose(minutes: number): DoseOccurrence {
  return {schedule_id:'schedule',name:'Medicine',time:'12:00',
    scheduled_for:new Date(now - minutes * 60000).toISOString(),
    status:'PENDING',record_id:null,due:minutes >= 0,reminder_enabled:true};
}

test('due banner uses the exact sixty-minute window and pending enabled doses', () => {
  for (const minutes of [-1, 0, 59, 60, 60.01, 120]) {
    expect(isRecentDueDose(dose(minutes), now)).toBe(minutes >= 0 && minutes <= 60);
  }
  expect(isRecentDueDose({...dose(5),status:'TAKEN'},now)).toBe(false);
  expect(isRecentDueDose({...dose(5),reminder_enabled:false},now)).toBe(false);
});

test('old due doses stay recordable without displaying the due banner', async ({page}) => {
  const old = {...dose(120), scheduled_for:new Date(Date.now()-2*60*60*1000).toISOString()};
  await page.route('**/api/v1/reminders/**', route => {
    const path = new URL(route.request().url()).pathname;
    return route.fulfill({json:path.endsWith('/today') ? [old] :
      path.endsWith('/adherence') ? {days:7,taken:0,total_due:1,rate:0} : []});
  });
  await page.route('**/api/v1/hcp/**', route => route.fulfill({json:
    route.request().url().endsWith('/capabilities') ? {preview:false} : []}));
  await login(page);
  await page.goto('/reminders');
  await expect(page.getByText('Medicine · 12:00',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Đã uống',exact:true})).toBeEnabled();
  await expect(page.getByText('Đến giờ dùng thuốc.',{exact:false})).toHaveCount(0);
});
