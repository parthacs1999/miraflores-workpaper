import { defineConfig } from "@playwright/test";

// Keep all original scenarios, using private servers and a disposable SQLite DB.
process.env.E2E_BASE_URL = "http://localhost:3100";
process.env.E2E_API_URL = "http://localhost:8100";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  use: { baseURL: process.env.E2E_BASE_URL, browserName: "chromium", trace: "retain-on-failure" },
  webServer: [
    {
      command: "../backend/.venv/bin/python ../backend/run_e2e.py",
      url: "http://localhost:8100/health",
      reuseExistingServer: false,
      env: { PYTHONDONTWRITEBYTECODE: "1" },
    },
    {
      command: "npm run build -- --webpack && npm run start -- --port 3100",
      url: "http://localhost:3100",
      timeout: 180_000,
      reuseExistingServer: false,
      env: { NEXT_DIST_DIR: ".next-e2e", NEXT_PUBLIC_API_URL: "http://localhost:8100" },
    },
  ],
});
