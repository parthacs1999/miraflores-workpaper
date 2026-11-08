import { clickAction, navigate, openSessionMenu } from "../tests/ui-helpers";
import { test, expect, type Page } from "@playwright/test";
async function select(page: Page, id = "st-01") {
  await openSessionMenu(page);
  await page.getByLabel("Session staff").selectOption(id);
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Start / switch session", exact: true })
      .click(),
  );
  await expect(page.getByTestId("current-session")).toContainText(id);
}
async function changes(page: Page, tab: string) {
  await navigate(
    page,
    (
      {
        "Version Comparison": "version",
        "What-if Analysis": "whatif",
        "Timeline Replay": "replay",
        "Change Impact": "impact",
      } as Record<string, string>
    )[tab],
  );
}

test("three stored versions compare with exact effects and navigable evidence", async ({
  page,
}) => {
  await page.goto("/");
  await select(page);
  await changes(page, "Version Comparison");
  await expect(page.getByTestId("comparison-counts")).toContainText("changed:");
  await page.getByLabel("Compare line search").fill("F1040.24");
  const row = page.getByTestId("comparison-F1040.24");
  await expect(row).toContainText("77200");
  await expect(row).toContainText("77470");
  await expect(row).toContainText("81962");
  await expect(row).toContainText("$4762");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Inspect F1040.24 v2", exact: true })
      .click(),
  );
  await expect(page.getByTestId("resolution-status")).toContainText("resolved");
  await expect(
    page.getByText("v2 lineage and source evidence", { exact: true }),
  ).toBeVisible();
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Change details F1040.24", exact: true })
      .click(),
  );
  await expect(
    page.getByRole("heading", {
      name: "Change details: F1040.24",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByLabel("Compare from").selectOption("v2");
  await expect(page.getByTestId("comparison-F1040.24")).toContainText("$4492");
  await page
    .getByLabel("Show unchanged and other-version lines", { exact: true })
    .check();
  await page.getByLabel("Compare line search").fill("F1040.1a");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Inspect F1040.1a v3", exact: true })
      .click(),
  );
  await clickAction(page, async () =>
    page.getByRole("button", { name: "ev-0016", exact: true }).click(),
  );
  await expect(page.getByTestId("source-verification")).toBeVisible();
  await expect(page.getByTestId("source-highlight")).toBeVisible();
});
test("supported scenarios reject conflicting savings and persist hypothetical analysis only", async ({
  page,
}) => {
  await page.goto("/");
  await select(page);
  await changes(page, "What-if Analysis");
  await page
    .getByLabel("Scenario equipment_section179", { exact: true })
    .check();
  await expect(page.getByTestId("scenario-warnings")).toContainText(
    "No combined result",
  );
  await expect(
    page.getByText(
      "california · tax effect -1050 · penalty effect Not supplied",
      { exact: true },
    ),
  ).toBeVisible();
  await page.getByLabel("Scenario equipment_no_bonus", { exact: true }).check();
  await expect(page.getByTestId("scenario-warnings")).toContainText(
    "Conflicting alternatives",
  );
  await page
    .getByLabel("Scenario analysis note")
    .fill("Consider alternatives without applying a correction.");
  await expect(
    page.getByRole("button", {
      name: "Save hypothetical analysis",
      exact: true,
    }),
  ).toBeDisabled();
  await page
    .getByLabel("Scenario equipment_no_bonus", { exact: true })
    .uncheck();
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Save hypothetical analysis", exact: true })
      .click(),
  );
  await expect(page.getByRole("status")).toContainText(
    "no tax adjustment or approval",
  );
  await page.reload();
  await changes(page, "What-if Analysis");
  await clickAction(page, async () =>
    page
      .getByRole("button", {
        name: "Load saved analyses and history",
        exact: true,
      })
      .click(),
  );
  await expect(
    page.getByText(
      /hypothetical · equipment_section179 · Consider alternatives/,
    ),
  ).toBeVisible();
  await page.getByLabel("Scenario baseline").selectOption("v1");
  await page
    .getByLabel("Scenario equipment_section179", { exact: true })
    .check();
  await expect(page.getByTestId("scenario-warnings")).toContainText(
    "incompatible",
  );
  await expect(
    page.getByRole("button", {
      name: "Save hypothetical analysis",
      exact: true,
    }),
  ).toBeDisabled();
});
test("timeline withholds future nested evidence and scripted filing never clears readiness", async ({
  page,
}) => {
  await page.goto("/");
  await select(page);
  await changes(page, "Timeline Replay");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Replay selected time", exact: true })
      .click(),
  );
  await expect(page.getByTestId("replay-context")).toContainText(
    "engine baseline v1",
  );
  await expect(page.getByTestId("replay-documents")).not.toContainText("D31");
  await expect(page.getByTestId("replay-documents")).not.toContainText("D72");
  await page.getByLabel("Replay evidence reference").fill("agency:/notices/1");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Resolve historical evidence", exact: true })
      .click(),
  );
  await expect(page.getByTestId("historical-evidence")).toContainText(
    "unresolved",
  );
  await expect(page.getByTestId("historical-evidence")).not.toContainText(
    "2028-02-19",
  );
  await page.getByLabel("Replay time UTC").fill("2026-07-15T02:11:00");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Replay selected time", exact: true })
      .click(),
  );
  await expect(page.getByTestId("replay-events")).toContainText(
    "efile_accepted_federal",
  );
  await expect(page.getByTestId("replay-documents")).not.toContainText("D72");
  await expect(page.getByTestId("replay-events")).toContainText(
    "never completes live workflow",
  );
  await navigate(page, "readiness");
  await expect(page.getByTestId("filing-readiness")).toHaveText(
    "FILING BLOCKED",
  );
});
test("actual business adjustment invalidates approval while impact preview preserves it", async ({
  page,
}) => {
  await page.goto("/");
  await select(page, "st-02");
  await navigate(page, "signoffs");
  await clickAction(page, async () =>
    page
      .getByRole("button", {
        name: "Record demonstration reviewer sign-off",
        exact: true,
      })
      .click(),
  );
  await expect(page.getByRole("status")).toContainText(
    "No legal electronic signature",
  );
  const before = await (
    await page.request.get("http://localhost:8200/api/workflow/overview")
  ).json();
  const signed = before.signoffs
    .filter(
      (s: { area: string; state: string }) =>
        s.area === "business" && s.state === "valid",
    )
    .at(-1);
  expect(signed).toBeTruthy();
  await changes(page, "Change Impact");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Preview change impact", exact: true })
      .click(),
  );
  await expect(page.getByTestId("impact-areas")).toContainText("business");
  let status = await (
    await page.request.get("http://localhost:8200/api/workflow/overview")
  ).json();
  expect(
    status.signoffs.find((s: { id: string }) => s.id === signed.id).state,
  ).toBe("valid");
  await select(page);
  await navigate(page, "return");
  await clickAction(page, async () =>
    page.getByRole("button", { name: "Adjustments", exact: true }).click(),
  );
  await clickAction(page, async () =>
    page
      .getByRole("button", {
        name: "Load business receipts example",
        exact: true,
      })
      .click(),
  );
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Save adjustment draft", exact: true })
      .click(),
  );
  await expect(page.getByTestId("adjustment-state")).toHaveText("draft");
  status = await (
    await page.request.get("http://localhost:8200/api/workflow/overview")
  ).json();
  expect(
    status.signoffs.find((s: { id: string }) => s.id === signed.id).state,
  ).toBe("invalidated");
  await select(page, "st-02");
  await changes(page, "Change Impact");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Preview change impact", exact: true })
      .click(),
  );
  await page
    .getByLabel("Impact assessment note")
    .fill("Investigated current duplicated receipt adjustment dependency.");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Record impact reassessment", exact: true })
      .click(),
  );
  await expect(page.getByRole("status")).toContainText(
    "Impact assessment recorded",
  );
});
test("administrator cannot enter tax change analysis or fetch its protected APIs", async ({
  page,
}) => {
  await page.goto("/");
  await select(page, "st-05");
  await expect(
    page.getByRole("button", { name: "Change Analysis", exact: true }),
  ).toHaveCount(0);
  const denied = await page.request.get(
    "http://localhost:8200/api/version-comparison",
  );
  expect(denied.status()).toBe(403);
  await select(page, "st-04");
  const replay = await page.request.get(
    "http://localhost:8200/api/timeline-replay/evidence?at=2026-06-23&ref=D03",
  );
  expect(replay.status()).toBe(200);
  const text = await replay.text();
  expect(text).not.toContain("482915");
  expect(replay.headers()["cache-control"]).toContain("no-store");
});
