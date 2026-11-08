import { defineConfig } from "@playwright/test";
import proxy from "./playwright.deployment.config";
export default defineConfig({
  ...proxy,
  testDir: "./assignment-tests",
  webServer: (Array.isArray(proxy.webServer) ? proxy.webServer : []).map(
    (server, index) =>
      index === 0
        ? {
            ...server,
            command:
              "../backend/.venv/bin/python ../backend/run_assignment_e2e.py",
          }
        : index === 1
          ? {
              ...server,
              env: {
                ...server.env,
                WORKPAPER_PROFILE: "assignment-demo",
                NEXT_PUBLIC_ASSIGNMENT_DEMO: "1",
                WORKPAPER_ASSIGNMENT_TEST: "1",
                WORKPAPER_PUBLIC_ORIGIN: "https://localhost:3300",
              },
            }
          : server,
  ),
});
