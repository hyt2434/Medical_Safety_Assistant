import puppeteer from "puppeteer-core";
import assert from "node:assert/strict";
import path from "node:path";
import fs from "node:fs";
import { createServer } from "vite";
const root = path.resolve("artifacts/pa2");
fs.mkdirSync(root + "/screenshots", { recursive: true });
const executable =
  process.env.BROWSER_PATH ||
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const server = await createServer({
  server: { host: "127.0.0.1", port: 5179, strictPort: true },
});
await server.listen();
const browser = await puppeteer.launch({
  executablePath: executable,
  headless: true,
  userDataDir: root + "/profile-" + Date.now(),
  args: ["--no-sandbox"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 1000 });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto("http://127.0.0.1:5179");
await page.evaluate(() => localStorage.clear());
await page.reload();
await page.evaluate(() => document.fonts.ready);
assert.ok(await page.evaluate(() => document.fonts.check('16px "IBM Plex Sans Variable"')));
const click = async (s) => {
  await page.click(s);
  await new Promise((r) => setTimeout(r, 100));
};
const submit = async (s) => {
  await page.$eval(s, (f) => f.requestSubmit());
  await new Promise((r) => setTimeout(r, 120));
};
const type = async (s, v) => {
  await page.$eval(s + ":not(meta)", (el, v) => (el.value = v), v);
};
const route = async (r) => {
  await page.evaluate((r) => (location.hash = r), r);
  await new Promise((r) => setTimeout(r, 120));
};
const data = () =>
  page.evaluate(() => JSON.parse(localStorage.getItem("msa-frontend-pa2-v2")));
const login = async (r) => {
  if (await page.$("[data-action=logout]"))
    await click(".topbar [data-action=logout]");
  await click(`[data-role=${r}]`);
  await submit("#login-form");
};
try {
  await page.screenshot({
    path: root + "/screenshots/login.png",
    fullPage: true,
  });
  await login("patient");
  assert.equal(await page.$('.sidebar'), null);
  await click('.menu-toggle');
  await page.screenshot({path: root + '/screenshots/patient-menu.png', fullPage: true});
  await click('#workspace-navigation a[href="#chat"]');
  assert.equal(await page.$eval('.menu-toggle', e => e.getAttribute('aria-expanded')), 'false');
  await route('home');
  await click('.assistant-shortcut');
  assert.equal(await page.evaluate(() => location.hash), '#chat');
  await route('home');
  await page.evaluate(
    () => (document.querySelector("#notice").textContent = ""),
  );
  await page.screenshot({
    path: root + "/screenshots/01-patient-home.png",
    fullPage: true,
  });
  await route("safety");
  await click("[data-action=assess]");
  await new Promise((r) => setTimeout(r, 500));
  assert.equal((await data()).assessments.length, 1);
  assert.equal((await data()).assessments[0].severe, true);
  await route("review");
  await click("[name=consent]");
  await submit("#share-case");
  assert.equal((await data()).requests.length, 1);
  await route("reminders");
  await click("[name=verified]");
  await submit("#new-reminder");
  assert.equal(
    (await data()).plans.find((p) => p.med === "A").status,
    "Pending",
  );
  assert.equal(
    (await data()).plans.find((p) => p.med === "C").status,
    "Active",
  );
  await login("hcp");
  await click("[data-action=open-case]");
  await type(
    "[name=message]",
    "Xin bổ sung thông tin nguồn để tôi xem xét lịch đã ghi nhận.",
  );
  await page.select("[name=outcome]", "Awaiting Patient Response");
  await submit("#case-reply");
  assert.equal((await data()).requests[0].status, "Awaiting Patient Response");
  await login("patient");
  await route("review");
  await click("[data-action=reply]");
  await type("[name=message]", "Tôi đã bổ sung thông tin theo yêu cầu.");
  await submit("#case-reply");
  assert.equal((await data()).requests[0].status, "Pending HCP Response");
  assert.ok((await data()).requests[0].messages[1].replyTo);
  await login("hcp");
  await page.evaluate(() => (document.querySelector("#notice").textContent = ""));
  await page.screenshot({path:root+"/screenshots/hcp-queue-pending.png",fullPage:true});
  await click("[data-action=open-case]");
  await page.evaluate(
    () => (document.querySelector("#notice").textContent = ""),
  );
  await page.screenshot({
    path: root + "/screenshots/02-hcp-conversation.png",
    fullPage: true,
  });
  await type("[name=message]", "Đã xem xét lịch trong kịch bản mẫu.");
  await page.select("[name=outcome]", "Reviewed");
  await click("[name=schedule]");
  await submit("#case-reply");
  assert.equal(
    (await data()).plans.find((p) => p.med === "A").status,
    "Active",
  );
  await login("patient");
  await route("summary");
  await click("[data-action=draft-summary]");
  await click("#summary-form [type=checkbox]");
  await submit("#summary-form");
  assert.equal((await data()).summaries.length, 1);
  assert.equal((await data()).summaries[0].shared, false);
  await click("#share-summary [type=checkbox]");
  await submit("#share-summary");
  await click("#confirm-dialog [value=ok]");
  assert.equal((await data()).summaries[0].shared, true);
  await route("chat");
  await type("[name=question]", "Tôi muốn đổi giờ thuốc");
  await submit("#chat-form");
  assert.equal((await data()).chat.at(-1).route, "intake");
  await route("support");
  await type("[name=title]", "OCR không phản hồi");
  await type(
    "[name=description]",
    "Bấm xử lý ảnh và gặp thông báo hết thời gian.",
  );
  await click("[name=diagnostic]");
  await submit("#ticket-form");
  assert.equal((await data()).tickets.length, 1);
  await login("support");
  await page.select("[name=status]", "Pending User Response");
  await type("[name=note]", "Vui lòng cho biết thời điểm gặp lỗi.");
  await submit(".resolve-ticket");
  assert.equal((await data()).tickets[0].status, "Pending User Response");
  await page.evaluate(
    () => (document.querySelector("#notice").textContent = ""),
  );
  await page.screenshot({
    path: root + "/screenshots/03-support-ticket.png",
    fullPage: true,
  });
  await login("reviewer");
  await page.select("#scenario", "missing");
  await type("[name=reason]", "Thiếu bằng chứng nguồn.");
  await submit("#dataset-form");
  assert.equal((await data()).reviews[0].decision, "Needs Correction");
  await page.evaluate(
    () => (document.querySelector("#notice").textContent = ""),
  );
  await page.screenshot({
    path: root + "/screenshots/04-data-review.png",
    fullPage: true,
  });
  await login("admin");
  await type("[name=name]", "Demo User");
  await type("[name=email]", "new@demo.local");
  await click("[name=roles][value=patient]");
  await submit("#account-form");
  await click("#confirm-dialog [value=ok]");
  assert.equal((await data()).accounts.length, 6);
  assert.equal((await data()).audit.length, 1);
  await route("review");
  assert.match(
    await page.$eval("#main", (e) => e.textContent),
    /không được phép/,
  );
  await login("patient");
  await route("intake");
  await page.select("#scenario", "save");
  await click("[name=confirmed]");
  const rev = (await data()).revision;
  await submit("#intake-form");
  assert.equal((await data()).revision, rev);

  // Every role-specific screen must render without browser errors or page overflow.
  for (const [r, routes] of Object.entries({
    patient: [
      "home",
      "intake",
      "safety",
      "review",
      "reminders",
      "history",
      "chat",
      "summary",
      "support",
    ],
    hcp: ["queue", "review", "shared"],
    reviewer: ["dataset"],
    admin: ["accounts", "audit"],
    support: ["tickets"],
  })) {
    await login(r);
    for (const target of routes) {
      await route(target);
      await page.evaluate(
        () => (document.querySelector("#notice").textContent = ""),
      );
      await page.screenshot({
        path: root + "/screenshots/" + r + "-" + target + ".png",
        fullPage: true,
      });
      assert.ok(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        r + " " + target + " desktop overflow",
      );
    }
  }
  await login("patient");
  await route("home");
  await page.setViewport({ width: 390, height: 844 });
  await page.evaluate(
    () => (document.querySelector("#notice").textContent = ""),
  );
  await page.screenshot({
    path: root + "/screenshots/05-patient-mobile.png",
    fullPage: true,
  });
  assert.ok(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "Mobile horizontal overflow",
  );
  await page.screenshot({
    path: root + "/screenshots/mobile-viewport.png",
    fullPage: false,
  });
  for (const width of [320, 375, 414, 768]) {
    await page.setViewport({ width, height: 1000 });
    for (const [r, routes] of Object.entries({
      patient: [
        "home",
        "intake",
        "safety",
        "review",
        "reminders",
        "history",
        "chat",
        "summary",
        "support",
      ],
      hcp: ["queue", "review", "shared"],
      reviewer: ["dataset"],
      admin: ["accounts", "audit"],
      support: ["tickets"],
    })) {
      await login(r);
      for (const target of routes) {
        await route(target);
        assert.ok(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
          `${r}/${target} overflow at ${width}`,
        );
      }
    }
  }
  assert.deepEqual(errors, []);
  await page.setViewport({ width: 375, height: 844 });
  await login("patient");
  assert.equal(await page.$eval('.menu-toggle', e => e.getAttribute('aria-expanded')), 'false');
  await click('.menu-toggle');
  assert.equal(await page.$eval('.menu-toggle', e => e.getAttribute('aria-expanded')), 'true');
  assert.ok(await page.$eval('#workspace-navigation', e => e.getBoundingClientRect().height > 0));
  await page.keyboard.press('Escape');
  assert.equal(await page.$eval('.menu-toggle', e => e.getAttribute('aria-expanded')), 'false');
  if (process.argv.includes("--report")) {
    const destination = path.resolve(
      "../../pa/pa2/ui-report/sections/ui-images",
    );
    fs.mkdirSync(destination, { recursive: true });
    const files = [
      "login",
      "patient-menu",
      "patient-home",
      "patient-intake",
      "patient-safety",
      "patient-review",
      "hcp-queue",
      "hcp-review",
      "patient-reminders",
      "patient-history",
      "patient-chat",
      "patient-summary",
      "hcp-shared",
      "reviewer-dataset",
      "admin-accounts",
      "admin-audit",
      "patient-support",
      "support-tickets",
      "mobile-viewport",
    ];
    const reportSources = {"hcp-queue":"hcp-queue-pending", "hcp-review":"02-hcp-conversation"};
    for (const file of files)
      fs.copyFileSync(
        root + "/screenshots/" + (reportSources[file] || file) + ".png",
        destination + "/" + file + ".png",
      );
    fs.writeFileSync(
      destination + "/capture-manifest.json",
      JSON.stringify(
        {
          source: "apps/frontend",
          entry: "src/pa2/app.ts",
          capturedAt: new Date().toISOString(),
          desktop: { width: 1440, height: 1000 },
          mobile: { width: 390, height: 844 },
          screenshots: files.map((file) => file + ".png"),
          method:
            "Browser screenshots after real UI interactions; fictional data",
        },
        null,
        2,
      ),
    );
    console.log("Updated 19 report screenshots from the TypeScript frontend.");
  }
  console.log(
    "PASS: cross-role review, reply queue, reminder gate, summary consent, chat routing, support, reviewer evidence, admin audit, access denial, failed save, responsive layout.",
  );
} catch (e) {
  console.log("BROWSER ERRORS", errors);
  console.log(await page.$eval("#main", (e) => e.innerText));
  throw e;
} finally {
  await browser.close();
  await server.close();
}
