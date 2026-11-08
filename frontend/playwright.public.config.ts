import { defineConfig } from "@playwright/test";
import proxy from "./playwright.deployment.config";
export default defineConfig({
  ...proxy,
  testDir: "./public-tests",
  webServer: (Array.isArray(proxy.webServer) ? proxy.webServer : []).map(
    (server, index) =>
      index === 0
        ? {
            ...server,
            command: "../backend/.venv/bin/python ../backend/run_public_e2e.py",
          }
        : index === 1
          ? {
              ...server,
              env: {
                ...server.env,
                WORKPAPER_PROFILE: "public-demo",
                NEXT_PUBLIC_PUBLIC_DEMO: "1",
                WORKPAPER_PUBLIC_TEST: "1",
                WORKPAPER_PUBLIC_ORIGIN: "https://localhost:3300",
              },
            }
          : server,
  ),
});
