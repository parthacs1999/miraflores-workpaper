import { defineConfig } from "@playwright/test";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
process.env.PROXY_E2E_DIR ??= mkdtempSync(
  join(tmpdir(), "miraflores-proxy-e2e-"),
);
const env = { WORKPAPER_ENV: "test", PROXY_E2E_DIR: process.env.PROXY_E2E_DIR };
export default defineConfig({
  testDir: "./deployment-tests",
  globalTeardown: "./deployment-tests/cleanup.mjs",
  workers: 1,
  retries: 0,
  timeout: 60000,
  use: {
    baseURL: "https://localhost:3300",
    ignoreHTTPSErrors: true,
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  webServer: [
    {
      command: "../backend/.venv/bin/python ../backend/run_proxy_e2e.py",
      url: "http://localhost:8300/health",
      reuseExistingServer: false,
      env,
    },
    {
      command: "npm run build -- --webpack && npm run start -- --port 3301",
      url: "http://localhost:3301",
      timeout: 180000,
      reuseExistingServer: false,
      env: {
        ...env,
        NEXT_DIST_DIR: ".next-proxy-e2e",
        NEXT_PUBLIC_API_URL: "",
        WORKPAPER_PROXY_TEST: "1",
        WORKPAPER_BACKEND_ORIGIN: "http://127.0.0.1:8300",
      },
    },
    {
      command: "node deployment-tests/https-proxy.mjs",
      url: "https://localhost:3300",
      ignoreHTTPSErrors: true,
      reuseExistingServer: false,
      env,
    },
  ],
});
