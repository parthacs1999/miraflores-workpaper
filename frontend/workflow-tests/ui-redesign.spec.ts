import { test, expect, type Page } from "@playwright/test";
import { navigate, openSessionMenu } from "../tests/ui-helpers";
const API = "http://localhost:8200";
async function session(page: Page, id = "st-01") {
  await openSessionMenu(page);
  await page.getByLabel("Session staff", { exact: true }).selectOption(id);
  await page
    .getByRole("button", { name: "Start / switch session", exact: true })
    .click();
  await expect(page.getByTestId("current-session")).toContainText(id);
}

test("dashboard metrics use real authorized data and activity lives in a dismissible drawer", async ({
  page,
}) => {
  await page.goto("/");
  await session(page);
  await expect(page.getByTestId("dashboard-metrics")).toBeVisible();
  const f = await (
    await page.request.get(API + "/api/unified-findings?version=v3")
  ).json();
  const d = await (
    await page.request.get(API + "/api/document-accountability?version=v3")
  ).json();
  const w = await (
    await page.request.get(API + "/api/workflow/overview")
  ).json();
  const unresolved = f.findings.filter(
    (x: { status: string; review_validity?: { state: string } }) =>
      x.status !== "resolved" ||
      x.review_validity?.state === "needs_reassessment",
  ).length;
  const metric = (label: string) =>
    page
      .locator(".stat-card")
      .filter({ has: page.getByText(label, { exact: true }) });
  await expect(metric("Open findings").locator(".stat-value")).toHaveText(
    String(unresolved),
  );
  await expect(metric("Documents to review").locator(".stat-value")).toHaveText(
    String(d.counts.requires_review),
  );
  await expect(metric("Outstanding tasks").locator(".stat-value")).toHaveText(
    String(
      w.tasks.filter((t: { state: string }) => t.state !== "complete").length,
    ),
  );
  await expect(page.getByTestId("live-updates")).not.toBeVisible();
  await page
    .getByRole("button", { name: "Open activity and notifications" })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Activity & notifications", exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("live-connection")).toContainText("Live");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("live-updates")).not.toBeVisible();
  await expect(page.getByText("FILING BLOCKED", { exact: true })).toBeVisible();
});

test("every Phase 1–7 workspace is reachable through grouped navigation without console errors", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  await page.goto("/");
  await session(page);
  for (const view of [
    "readiness",
    "tasks",
    "return",
    "documents",
    "reconciliation",
    "adjustments",
    "diligence",
    "notes",
    "signoffs",
    "collaboration",
    "attachments",
    "bulk",
    "version",
    "whatif",
    "replay",
    "impact",
    "finalization",
    "filing",
    "extensions",
    "authorization",
    "amendments",
    "notices",
    "carryovers",
    "assignments",
    "operations",
    "security",
  ]) {
    await navigate(page, view);
    await expect(page).toHaveURL(new RegExp("view=" + view + "(?:&|$)"));
    await expect(
      page.locator('.sidebar-link[aria-current="page"]'),
    ).toHaveAttribute("data-view", view);
    await expect(page.locator("#main-content")).toBeVisible();
    await expect(page.locator(".app-topbar")).toContainText("Filing blocked");
  }
  expect(errors).toEqual([]);
});

test("return-line deep links preserve original engine values and expose context and jurisdiction filters", async ({
  page,
}) => {
  await page.goto("/?view=return&ref=SchC.1");
  await session(page);
  await expect(page.getByTestId("return-line-context")).toBeVisible();
  await expect(page.getByTestId("return-line-context")).toContainText(
    "Prior-year reported value",
  );
  await page
    .getByPlaceholder("Search by form, line, or description...")
    .fill("SchC.1");
  const baseline = (
    await (await page.request.get(API + "/api/return-lines?version=v3")).json()
  ).lines.find((l: { key: string }) => l.key === "SchC.1");
  await expect(
    page.locator(".return-lines-table tbody tr").first().locator("td").nth(1),
  ).toHaveText(
    new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(
      baseline.value,
    ),
  );
  await expect(
    page.getByText("Draft alternatives are never summed.", { exact: false }),
  ).toBeVisible();
  await page
    .getByLabel("Return jurisdiction", { exact: true })
    .selectOption("california");
  await expect(page.getByRole("button", { name: /^SchC\.1 / })).toHaveCount(0);
  await page
    .getByLabel("Return jurisdiction", { exact: true })
    .selectOption("all");
  await expect(page.getByRole("button", { name: /^SchC\.1 / })).toBeVisible();
  await navigate(page, "version");
  await page.goBack();
  await expect(page.getByTestId("return-line-context")).toBeVisible();
});

test("finding lists paginate and keep inspectable tax computations", async ({
  page,
}) => {
  await page.goto("/");
  await session(page);
  await navigate(page, "reconciliation");
  const dashboard = page.getByTestId("reconciliation-dashboard");
  await expect(dashboard.locator(".finding-table tbody tr")).toHaveCount(20);
  await dashboard
    .getByRole("button", { name: "Next page", exact: true })
    .click();
  await expect(dashboard.locator(".pagination")).toContainText("21–40");
  await page.getByLabel("Find reconciliation issue").fill("business.receipts");
  await expect(dashboard.locator(".finding-table tbody tr")).toHaveCount(1);
  await page
    .getByRole("button", {
      name: "Inspect reconciliation business.receipts",
      exact: true,
    })
    .click();
  await expect(page.getByTestId("reconciliation-expected")).toHaveText(
    "151300",
  );
  await expect(page.getByTestId("reconciliation-reported")).toHaveText(
    "163700",
  );
  await expect(page.getByTestId("reconciliation-difference")).toHaveText(
    "12400",
  );
});

test("cancelled consequential action sends no mutation and restores keyboard focus", async ({
  page,
}) => {
  await page.goto("/");
  await session(page, "st-02");
  await navigate(page, "signoffs");
  let writes = 0;
  page.on("request", (r) => {
    if (r.url().endsWith("/api/workflow/signoffs") && r.method() === "POST")
      writes++;
  });
  const action = page.getByRole("button", {
    name: "Record demonstration reviewer sign-off",
    exact: true,
  });
  await action.click();
  const dialog = page.getByRole("alertdialog", {
    name: "Confirm workpaper action",
    exact: true,
  });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("not a legal electronic signature");
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(writes).toBe(0);
  await expect(action).toBeFocused();
});

test("identity switch clears restricted evidence and admin deep links fail closed", async ({
  page,
}) => {
  await page.goto("/?view=return&ref=F1040.1a");
  await session(page);
  await expect(page.getByTestId("return-line-context")).toBeVisible();
  await session(page, "st-05");
  await expect(page.getByTestId("return-line-context")).toHaveCount(0);
  await expect(page.locator('.sidebar-link[data-view="return"]')).toHaveCount(
    0,
  );
  await expect(
    page.getByText("This workspace requires a broader assignment"),
  ).toBeVisible();
  expect(
    (await page.request.get(API + "/api/return-lines?version=v3")).status(),
  ).toBe(403);
  await navigate(page, "security");
  await expect(page.getByTestId("sensitive-mode")).toContainText("masked");
  await expect(
    page.getByRole("button", {
      name: "Reveal sensitive information",
      exact: true,
    }),
  ).toBeDisabled();
  expect(await page.content()).not.toContain("666-41-2287");
});

test("mobile sidebar, search, and filing controls stay accessible without page overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await session(page);
  await expect(
    page.getByRole("button", { name: "Open navigation", exact: true }),
  ).toBeVisible();
  await navigate(page, "documents");
  await expect(page.getByPlaceholder("Search documents...")).toBeVisible();
  await page.getByPlaceholder("Search documents...").fill("D09");
  await page.getByRole("button", { name: /^D09 / }).click();
  await expect(page.getByTestId("document-inspector")).toBeVisible();
  await navigate(page, "finalization");
  await expect(page.getByTestId("real-filing-status")).toContainText(
    "FILING BLOCKED",
  );
  await expect(page.getByLabel("Finalization mode")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page
    .getByRole("button", { name: "Open navigation", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Close navigation", exact: true })
    .click();
  await expect(page.locator(".app-shell")).not.toHaveClass(/mobile-nav-open/);
});

test("workflow search and sidebar collapse navigate using real views", async ({
  page,
}) => {
  await page.goto("/");
  await session(page);
  await page
    .getByRole("button", { name: "Collapse sidebar", exact: true })
    .click();
  await expect(page.locator(".app-shell")).toHaveClass(/sidebar-collapsed/);
  await page
    .getByRole("button", { name: "Expand sidebar", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Search workflows", exact: true })
    .click();
  await page.getByLabel("Search application workflows").fill("Notices");
  await page
    .getByRole("dialog", { name: "Find a workflow", exact: true })
    .getByRole("button", { name: /Notices & Examination/ })
    .click();
  await expect(page.getByTestId("filing-lifecycle")).toBeVisible();
  await expect(
    page.getByRole("dialog", { name: "Find a workflow", exact: true }),
  ).not.toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Notice intake and examination response",
      exact: true,
    }),
  ).toBeVisible();
});

test("expired access clears the previous workspace and gives a recoverable session message", async ({
  page,
}) => {
  await page.goto("/?view=return&ref=F1040.1a");
  await session(page);
  await expect(page.getByTestId("return-line-context")).toBeVisible();
  await page.route("**/api/return-lines?version=v3", (r) =>
    r.fulfill({ status: 401, json: { detail: "Staff session required" } }),
  );
  await navigate(page, "version");
  await navigate(page, "return");
  await expect(
    page.getByText(
      "Session or engagement assignment changed. Reload and select an authorized staff session.",
    ),
  ).toBeVisible();
  await expect(page.getByTestId("return-line-context")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Start / switch session", exact: true }),
  ).toBeVisible();
});

test("an unavailable adjustment ledger never masquerades as an approved workpaper value", async ({
  page,
}) => {
  await page.goto("/");
  await session(page);
  await page.route("**/api/adjustments?version=v3", (r) =>
    r.fulfill({
      status: 503,
      json: { detail: "Ledger temporarily unavailable" },
    }),
  );
  await navigate(page, "return");
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Adjustment ledger unavailable" }),
  ).toBeVisible();
  await page
    .getByPlaceholder("Search by form, line, or description...")
    .fill("SchC.1");
  await expect(
    page.locator(".return-lines-table tbody tr").first().locator("td").last(),
  ).toHaveText("Unavailable");
  await expect(
    page.locator(".return-lines-table tbody tr").first().locator("td").nth(1),
  ).toHaveText("163,700");
});

test("a stale unauthorized read cannot tear down the newly selected staff identity", async ({
  page,
}) => {
  await page.goto("/");
  await session(page);
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  let started: () => void = () => {};
  const requested = new Promise<void>((resolve) => {
    started = resolve;
  });
  await page.route("**/api/return-lines?version=v3", async (route) => {
    started();
    await held;
    await route
      .fulfill({
        status: 401,
        json: { detail: "Session changed; discard this response" },
      })
      .catch(() => {});
  });
  await navigate(page, "return");
  await requested;
  // Only the old request is delayed. The new identity's reads use the real API.
  await page.unroute("**/api/return-lines?version=v3");
  await session(page, "st-03");
  release();
  await navigate(page, "security");
  await expect(page.getByTestId("current-session")).toContainText("st-03");
  await expect(page.getByTestId("sensitive-mode")).toContainText("masked");
  await expect(
    page.getByText(
      "Session or engagement assignment changed. Reload and select an authorized staff session.",
    ),
  ).toHaveCount(0);
});

test("area-restricted preparers retain their authorized diligence and review workflows", async ({
  page,
}) => {
  await page.goto("/");
  await session(page, "st-04");
  await navigate(page, "diligence");
  await expect(page.getByLabel("Record title", { exact: true })).toBeVisible();
  await page
    .getByLabel("Record area", { exact: true })
    .selectOption("business");
  await expect(page.getByLabel("Record area", { exact: true })).toHaveValue(
    "business",
  );
  await navigate(page, "notes");
  await expect(page.getByLabel("Note title", { exact: true })).toBeVisible();
  await navigate(page, "signoffs");
  await expect(page.getByLabel("Sign-off area", { exact: true })).toBeVisible();
  await expect(page.locator('.sidebar-link[data-view="return"]')).toHaveCount(
    0,
  );
  expect(
    (await page.request.get(API + "/api/return-lines?version=v3")).status(),
  ).toBe(403);
  await navigate(page, "security");
  await expect(
    page.getByRole("button", {
      name: "Reveal sensitive information",
      exact: true,
    }),
  ).toBeDisabled();
});
