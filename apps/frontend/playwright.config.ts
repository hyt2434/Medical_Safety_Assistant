import { defineConfig } from "@playwright/test";
const port = Number(process.env.E2E_PORT || 5184);
const apiPort = Number(process.env.E2E_API_PORT || 8014);
const authDb = process.env.E2E_AUTH_DB || `../../artifacts/auth/e2e-${Date.now()}.sqlite`;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  timeout: 30000,
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    headless: true,
    extraHTTPHeaders: { Origin: `http://127.0.0.1:${port}` },
    launchOptions: {
      executablePath:
        process.env.CHROME_PATH ||
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
    },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `"${process.env.E2E_PYTHON || "python"}" app.py --port ${apiPort} --no-reload`,
      cwd: "../backend",
      url: `http://127.0.0.1:${apiPort}/health`,
      reuseExistingServer: false,
      env: { AUTH_DB_PATH: authDb, AUTH_DATABASE_URL: "", AUTH_ALLOWED_ORIGINS: `http://127.0.0.1:${port}`, AUTH_SEED_DEMO: "1" },
    },
    {
      command: "npm run dev",
      url: `http://127.0.0.1:${port}`,
      reuseExistingServer: false,
      env: { FRONTEND_PORT: String(port), API_PROXY_URL: `http://127.0.0.1:${apiPort}` },
    },
  ],
});
