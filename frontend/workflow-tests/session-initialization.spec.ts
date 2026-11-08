import { clickAction, openSessionMenu } from "../tests/ui-helpers";
import { test, expect } from "@playwright/test";

test("locked backend reports the real configuration failure and can retry into strict demo", async ({
  page,
}) => {
  let staffRequests = 0;
  await page.route("**/api/workflow/session/staff", async (route) => {
    staffRequests++;
    await route.continue();
  });
  await page.route("**/api/workflow/session", (route) =>
    route.fulfill({
      json: {
        mode: "locked",
        staff: null,
        detail: "Access is locked; configure WORKPAPER_MODE securely",
      },
    }),
  );
  await page.goto("/");
  const error = page.getByTestId("session-initialization-error");
  await expect(error).toContainText("Backend session provider is locked");
  await expect(error).toContainText("run_secure.py --demo");
  await expect(error).toContainText("http://localhost:8200");
  await expect(page.getByLabel("Session staff")).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Start / switch session", exact: true }),
  ).toBeDisabled();
  expect(staffRequests).toBe(0);
  await page.unroute("**/api/workflow/session");
  await clickAction(page, async () =>
    page
      .getByRole("button", {
        name: "Retry session initialization",
        exact: true,
      })
      .click(),
  );
  await expect(page.getByLabel("Session staff")).toBeEnabled();
  await expect(error).toHaveCount(0);
  for (const id of ["st-01", "st-02", "st-03"]) {
    await openSessionMenu(page);
    await page.getByLabel("Session staff").selectOption(id);
    await clickAction(page, async () =>
      page
        .getByRole("button", { name: "Start / switch session", exact: true })
        .click(),
    );
    await expect(page.getByTestId("current-session")).toContainText(id);
  }
});

test("unavailable backend shows an actionable connection error and recoverable retry", async ({
  page,
}) => {
  await page.route("**/api/workflow/session", (route) =>
    route.abort("connectionrefused"),
  );
  await page.goto("/");
  await expect(page.getByTestId("session-initialization-error")).toContainText(
    "Cannot reach the workpaper backend",
  );
  await expect(page.getByTestId("session-initialization-error")).toContainText(
    "NEXT_PUBLIC_API_URL",
  );
  await expect(page.getByLabel("Session staff")).toBeDisabled();
  await page.unroute("**/api/workflow/session");
  await clickAction(page, async () =>
    page
      .getByRole("button", {
        name: "Retry session initialization",
        exact: true,
      })
      .click(),
  );
  await expect(page.getByLabel("Session staff")).toBeEnabled();
});

test("wrong API server and empty provider options have explicit initialization errors", async ({
  page,
}) => {
  await page.route("**/api/workflow/session", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: "<html>Wrong server</html>",
    }),
  );
  await page.goto("/");
  await expect(page.getByTestId("session-initialization-error")).toContainText(
    "must point to FastAPI",
  );
  await page.unroute("**/api/workflow/session");
  await page.route("**/api/workflow/session/staff", (route) =>
    route.fulfill({ json: { staff: [] } }),
  );
  await clickAction(page, async () =>
    page
      .getByRole("button", {
        name: "Retry session initialization",
        exact: true,
      })
      .click(),
  );
  await expect(page.getByTestId("session-initialization-error")).toContainText(
    "No staff options were returned",
  );
  await expect(
    page.getByRole("button", { name: "Start / switch session", exact: true }),
  ).toBeDisabled();
});
