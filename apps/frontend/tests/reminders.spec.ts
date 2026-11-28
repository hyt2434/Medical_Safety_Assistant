import { test, expect } from "@playwright/test";
import { login } from "./intake-fixture";

test("patient creates schedule, consents to review, activates approval and corrects dose", async ({
  page,
}) => {
  let schedule: any = null,
    shared = false,
    taken = false,
    status = "PENDING",
    record: string | null = null;
  const calls: { path: string; body: any }[] = [];
  await page.route("**/api/v1/reminders/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/capabilities"))
      return route.fulfill({ json: { preview: false } });
    if (route.request().method() !== "GET") {
      const body = route.request().postDataJSON();
      calls.push({ path, body });
      if (path.endsWith("/schedules")) {
        expect(body).toMatchObject({
          entry_version_id: "entry-1",
          confirm: true,
          times: ["08:00"],
          dose_raw: "1 tablet",
        });
        schedule = {
          id: "schedule-1",
          name: "Synthetic medication",
          schedule_details: { times: ["08:00"], dose_raw: "1 tablet" },
          timezone: "Asia/Ho_Chi_Minh",
          verification_status: "PATIENT_CONFIRMED",
          reminder_enabled: false,
        };
        return route.fulfill({ json: schedule });
      }
      if (path.endsWith("/reminder"))
        return route.fulfill({
          status: 409,
          json: {
            error: {
              code: "HCP_REVIEW_REQUIRED",
              message: "HCP approval required",
            },
          },
        });
      if (path.endsWith("/activate")) {
        schedule.verification_status = "HCP_VERIFIED";
        schedule.reminder_enabled = true;
        return route.fulfill({ json: { enabled: true } });
      }
      if (path.endsWith("/doses")) {
        expect(body).toMatchObject({
          schedule_id: "revision-1",
          scheduled_for: "2026-11-27T01:00:00Z",
        });
        if (record) expect(body.supersedes).toBe(record);
        status = body.status;
        taken = status === "TAKEN";
        record = record ? "dose-2" : "dose-1";
        return route.fulfill({ json: { id: record } });
      }
    }
    if (path.endsWith("/entries"))
      return route.fulfill({
        json: [
          {
            id: "entry-1",
            name: "Synthetic medication",
            medication_fields: { dose_raw: "1 tablet" },
          },
        ],
      });
    if (path.endsWith("/schedules"))
      return route.fulfill({ json: schedule ? [schedule] : [] });
    if (path.endsWith("/adherence"))
      return route.fulfill({
        json: {
          days: 7,
          taken: taken ? 1 : 0,
          total_due: 1,
          rate: taken ? 1 : 0,
        },
      });
    return route.fulfill({
      json: schedule?.reminder_enabled
        ? [
            {
              schedule_id: "revision-1",
              name: "Synthetic medication",
              time: "08:00",
              scheduled_for: "2026-11-27T01:00:00Z",
              status,
              record_id: record,
              due: true,
              reminder_enabled: true,
            },
          ]
        : [],
    });
  });
  await page.route("**/api/v1/hcp/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/capabilities"))
      return route.fulfill({ json: { preview: false } });
    if (path.endsWith("/providers"))
      return route.fulfill({
        json: [{ id: "hcp-1", full_name: "Synthetic HCP" }],
      });
    if (route.request().method() === "POST") {
      expect(route.request().postDataJSON()).toEqual({
        kind: "SCHEDULE",
        schedule_id: "schedule-1",
        hcp_id: "hcp-1",
        consent: true,
      });
      shared = true;
      schedule = {
        ...schedule,
        id: "revision-1",
        verification_status: "UNVERIFIED",
        review_decision: "APPROVED",
      };
      return route.fulfill({ json: { id: "case-1" } });
    }
    return route.fulfill({
      json: shared
        ? [
            {
              id: "case-1",
              case_type: "SCHEDULE",
              status: "CLOSED",
              latest_outcome: { decision: "APPROVED", notes: "Reviewed" },
            },
          ]
        : [],
    });
  });
  await login(page);
  await page.goto("/reminders/new");
  await page.getByLabel("Thuốc đã xác nhận").selectOption("entry-1");
  await page.getByRole("checkbox").check();
  for (const invalid of ["24:00", "08:60", "8:00", ", ,"]) {
    await page.getByLabel("Giờ dùng (HH:MM, phân cách bằng dấu phẩy)").fill(invalid);
    await page.getByRole("button", { name: "Lưu lịch dùng thuốc" }).click();
    await expect(page.getByRole("alert")).toContainText("HH:MM");
    expect(calls.filter((c) => c.path.endsWith("/schedules"))).toHaveLength(0);
  }
  await page.getByLabel("Giờ dùng (HH:MM, phân cách bằng dấu phẩy)").fill(" 08:00, , ");
  await page.getByRole("button", { name: "Lưu lịch dùng thuốc" }).click();
  await expect(page).toHaveURL("/reminders");
  await page.getByRole("button", { name: "Bật nhắc", exact: true }).click();
  await page.getByLabel("Chuyên gia nhận ca").selectOption("hcp-1");
  await expect(
    page.getByRole("button", { name: "Gửi ca cho chuyên gia" }),
  ).toBeDisabled();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Gửi ca cho chuyên gia" }).click();
  await page.getByRole("button", { name: "Kích hoạt lịch đã duyệt" }).click();
  await expect(
    page.getByText("Đến giờ dùng thuốc.", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Đã uống", exact: true }).click();
  await expect(page.getByText("1 / 1 liều đến hạn · 100%")).toBeVisible();
  await page.getByRole("button", { name: "Bỏ qua", exact: true }).click();
  await expect(page.getByText("0 / 1 liều đến hạn · 0%")).toBeVisible();
  await page
    .getByRole("link", { name: "Lịch sử dùng thuốc", exact: true })
    .last()
    .click();
  await expect(page).toHaveURL("/dose-history");
  await expect(page.getByText("SKIPPED", { exact: false })).toBeVisible();
  expect(calls.filter((c) => c.path.endsWith("/doses"))).toHaveLength(2);
});

for (const decision of ['REJECTED', 'CHANGES_REQUESTED']) {
  test(`retained schedule can be disabled and ${decision} proposal can be resent`, async ({page}) => {
    const proposal = {id:'pending',entry_version_id:'entry',name:'Medicine',timezone:'UTC',
      schedule_details:{times:['09:00'],dose_raw:'one'},verification_status:'UNVERIFIED',review_decision:decision,reminder_enabled:false};
    const retained = { ...proposal, id:'verified', verification_status:'PATIENT_CONFIRMED',
      schedule_details:{times:['08:00'],dose_raw:'one'},reminder_enabled:true,review_decision:null};
    let toggled=false, resent=false;
    await page.route('**/api/v1/reminders/**', async route => {
      const path=new URL(route.request().url()).pathname;
      if(path.endsWith('/reminder')) {
        expect(path).toContain('/verified/'); expect(route.request().postDataJSON()).toEqual({enabled:false});
        retained.reminder_enabled=false;toggled=true;return route.fulfill({json:{enabled:false}});
      }
      if(path.endsWith('/schedules'))return route.fulfill({json:[retained, proposal]});
      if(path.endsWith('/adherence'))return route.fulfill({json:{days:7,taken:0,total_due:0,rate:null}});
      return route.fulfill({json:[]});
    });
    await page.route('**/api/v1/hcp/**', async route => {
      const path=new URL(route.request().url()).pathname;
      if(path.endsWith('/capabilities'))return route.fulfill({json:{preview:false}});
      if(path.endsWith('/providers'))return route.fulfill({json:[{id:'hcp',full_name:'Provider'}]});
      if(route.request().method()==='POST') {
        expect(route.request().postDataJSON()).toEqual({kind:'SCHEDULE',schedule_id:'pending',hcp_id:'hcp',consent:true});
        resent=true;return route.fulfill({json:{id:'new-case'}});
      }
      return route.fulfill({json:[]});
    });
    await login(page);await page.goto('/reminders');
    await expect(page.getByText(`UNVERIFIED · ${decision}`)).toBeVisible();
    await page.getByRole('button',{name:'Tắt nhắc',exact:true}).click();
    await expect(page.getByRole('button',{name:'Bật nhắc',exact:true})).toBeEnabled();
    expect(toggled).toBe(true);
    await page.getByRole('button',{name:'Gửi chuyên gia',exact:true}).last().click();
    await page.getByLabel('Chuyên gia nhận ca').selectOption('hcp');
    await page.getByRole('checkbox').check();
    await page.getByRole('button',{name:'Gửi ca cho chuyên gia',exact:true}).click();
    await expect(page.getByText('Đã gửi ca. Chờ kết quả rà soát.')).toBeVisible();
    expect(resent).toBe(true);
  });
}

test('undecided proposal blocks enabling but still allows disabling the retained reminder', async ({page}) => {
  const proposal = {id:'pending',entry_version_id:'entry',name:'Medicine',timezone:'UTC',
    schedule_details:{times:['09:00'],dose_raw:'one'},verification_status:'UNVERIFIED',review_decision:null,reminder_enabled:false};
  const retained = {...proposal,id:'verified',verification_status:'PATIENT_CONFIRMED',
    reminder_enabled:true,pending_proposal:proposal};
  const writes: unknown[] = [];
  await page.route('**/api/v1/reminders/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if(path.endsWith('/reminder')) {
      expect(path).toContain('/verified/');
      writes.push(route.request().postDataJSON());
      retained.reminder_enabled=false;
      return route.fulfill({json:{enabled:false}});
    }
    if(path.endsWith('/schedules'))return route.fulfill({json:[retained]});
    if(path.endsWith('/adherence'))return route.fulfill({json:{days:7,taken:0,total_due:0,rate:null}});
    return route.fulfill({json:[]});
  });
  await page.route('**/api/v1/hcp/**', route => route.fulfill({json:
    route.request().url().endsWith('/capabilities') ? {preview:false} : []}));
  await login(page);
  await page.goto('/reminders');
  await expect(page.getByRole('region',{name:'Lịch đề xuất'})).toContainText('Chờ rà soát');
  await page.getByRole('button',{name:'Tắt nhắc',exact:true}).click();
  await expect(page.getByRole('button',{name:'Bật nhắc',exact:true})).toBeDisabled();
  expect(writes).toEqual([{enabled:false}]);
});
