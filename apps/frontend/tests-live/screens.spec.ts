import { test, expect } from "@playwright/test";
import { noHorizontalScroll, signedIn, type Role } from "./helpers";

// Every page of every role, desktop and phone: loads, no console errors, no horizontal scroll.
// Screenshots land in artifacts/acceptance/screens/<viewport>/ for a quick visual pass.
const PAGES: Record<Role, string[]> = {
  patient: ["/dashboard", "/intake", "/verify", "/results", "/chat", "/reminders", "/reminders/new", "/dose-history",
    "/medications", "/profile", "/caregivers", "/health-summary", "/share-summary", "/medication-history",
    "/review-request", "/review-tracking"],
  hcp: ["/hcp", "/hcp/queue", "/hcp/patients", "/hcp/assessment", "/hcp/profile", "/hcp/database"],
  reviewer: ["/reviewer", "/reviewer/queue", "/reviewer/history", "/reviewer/sources"],
  support: ["/staff", "/staff/tickets", "/staff/report", "/staff/directory"],
  admin: ["/admin", "/admin/accounts", "/admin/roles", "/admin/audit", "/admin/staff", "/admin/database", "/admin/operations"],
};
const VIEWPORTS = { desktop: { width: 1366, height: 900 }, phone: { width: 375, height: 740 } };

for (const [viewportName, viewport] of Object.entries(VIEWPORTS)) {
  for (const [role, paths] of Object.entries(PAGES) as [Role, string[]][]) {
    test(`${role} pages on ${viewportName}`, async ({ browser }) => {
      const { context, page } = await signedIn(browser, role, viewport);
      const errors: string[] = [];
      page.on("console", (m) => { if (m.type() === "error") errors.push(`${page.url()}: ${m.text()}`); });
      page.on("pageerror", (e) => errors.push(`${page.url()}: ${e.message}`));
      for (const path of paths) {
        await page.goto(path);
        await page.waitForLoadState("networkidle");
        await expect.soft(page, `${path} should not bounce to login`).not.toHaveURL(/\/login/);
        await expect.soft(page.locator("main, #root").first()).not.toBeEmpty();
        await noHorizontalScroll(page);
        const file = path.replace(/^\//, "").replace(/\//g, "_") || "home";
        await page.screenshot({ path: `../../artifacts/acceptance/screens/${viewportName}/${role}-${file}.png`, fullPage: true });
      }
      expect.soft(errors, "console errors").toEqual([]);
      await context.close();
    });
  }
}
