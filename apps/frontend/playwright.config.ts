import { defineConfig } from "@playwright/test";
import { existsSync } from 'node:fs';
const port = Number(process.env.E2E_PORT || 5184);
const apiPort = Number(process.env.E2E_API_PORT || 8014);
const authDb = process.env.E2E_AUTH_DB || `../../artifacts/auth/e2e-${Date.now()}.sqlite`;
const realIntake = process.env.INTAKE_REAL_E2E === '1';
if (realIntake && (!/dbname=msa_core_test_v4[a-z0-9]*checks\b/.test(process.env.E2E_CORE_DSN || '') ||
  !/\/msa_auth_test_[a-z0-9]+(?:\?|$)/.test(process.env.E2E_AUTH_URL || ''))) {
  throw new Error('Real browser automation requires explicit dedicated Core/Auth TEST databases; dev DBs are refused.');
}
const browserPath = process.env.CHROME_PATH || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(path => existsSync(path));

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  // Source role-grant scenarios share seeded accounts in one isolated Auth DB.
  workers: 1,
  timeout: realIntake ? 240000 : 30000,
  outputDir: process.env.E2E_OUTPUT_DIR || 'test-results',
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    headless: true,
    extraHTTPHeaders: { Origin: `http://127.0.0.1:${port}` },
    launchOptions: {
      executablePath: browserPath,
    },
    screenshot: "off",
    trace: "off",
  },
  webServer: [
    {
      command: `"${process.env.E2E_PYTHON || "python"}" app.py --port ${apiPort} --no-reload`,
      cwd: "../backend",
      url: `http://127.0.0.1:${apiPort}/health`,
      reuseExistingServer: false,
      env: { AUTH_DB_PATH: authDb, AUTH_DATABASE_URL: realIntake ? process.env.E2E_AUTH_URL! : "", AUTH_ALLOWED_ORIGINS: `http://127.0.0.1:${port}`, AUTH_SEED_DEMO: realIntake ? "0" : "1",
        // The suite repeatedly signs into shared fixtures. Throttle limits are tested by backend tests.
        AUTH_LOGIN_ACCOUNT_LIMIT: "1000", AUTH_LOGIN_IP_LIMIT: "2000",
        CORE_DB_DSN: realIntake ? process.env.E2E_CORE_DSN! : "", CORE_REFERENCE_BUILD: realIntake ? process.env.E2E_REFERENCE_BUILD! : "", CORE_USER_BINDINGS: "{}", CORE_DATA_CONTEXT: "SYNTHETIC_TEST" },
    },
    {
      command: "npm run dev",
      url: `http://127.0.0.1:${port}`,
      reuseExistingServer: false,
      env: { FRONTEND_PORT: String(port), API_PROXY_URL: `http://127.0.0.1:${apiPort}` },
    },
  ],
});
