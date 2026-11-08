import { clickAction, navigate, openSessionMenu } from "../tests/ui-helpers";
import { test, expect, type Page } from "@playwright/test";
async function select(page: Page, id: string) {
  await openSessionMenu(page);
  await page.getByLabel("Session staff").selectOption(id);
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Start / switch session", exact: true })
      .click(),
  );
  await expect(page.getByTestId("current-session")).toContainText(id);
}
test("strict identity selection, real readiness blockers, and stale identities", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByText("No active staff session")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Return Explorer", exact: true }),
  ).toHaveCount(0);
  await select(page, "st-01");
  await navigate(page, "readiness");
  await expect(page.getByTestId("filing-readiness")).toHaveText(
    "FILING BLOCKED",
  );
  await expect(
    page.getByText("FINAL_RETURN_AND_CLIENT_AUTHORIZATION_UNVERIFIED", {
      exact: false,
    }),
  ).toBeVisible();
  await navigate(page, "return");
  await expect(
    page.getByRole("button", { name: "Adjustments", exact: true }),
  ).toBeVisible();
  await select(page, "st-05");
  await expect(
    page.getByRole("button", { name: "Return Explorer", exact: true }),
  ).toHaveCount(0);
  await openSessionMenu(page);
  await clickAction(page, async () =>
    page.getByRole("button", { name: "End session", exact: true }).click(),
  );
  await expect(page.getByTestId("current-session")).toHaveText(
    "No active staff session",
  );
});
test("preparation, independent demonstration signoff, and permanent invalidation", async ({
  page,
}) => {
  await page.goto("/");
  await select(page, "st-01");
  await navigate(page, "diligence");
  await page
    .getByLabel("Record title")
    .fill("Browser business receipts preparation");
  await page
    .getByLabel("Record answer")
    .fill(
      "Compared duplicated receipts to client books; engine packet preserved.",
    );
  await page
    .getByLabel("Record authority")
    .fill("Packet business receipts evidence; CPA judgment documented");
  await page.getByLabel("Record references").fill("D16");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Create workflow record", exact: true })
      .click(),
  );
  await expect(page.getByRole("status")).toContainText("Saved");
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
  await expect(page.getByText("valid", { exact: true })).toBeVisible();
  await select(page, "st-01");
  await navigate(page, "diligence");
  const item = page
    .getByRole("listitem")
    .filter({ hasText: "Browser business receipts preparation" });
  await clickAction(page, async () =>
    item.getByRole("button", { name: /^Edit / }).click(),
  );
  await page
    .getByLabel("Record answer")
    .fill("Revised after additional client confirmation.");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Save record revision", exact: true })
      .click(),
  );
  await expect(page.getByRole("status")).toContainText("Saved");
  await navigate(page, "signoffs");
  await expect(page.getByText("invalidated", { exact: true })).toBeVisible();
  await page.reload();
  await navigate(page, "signoffs");
  await expect(page.getByText("invalidated", { exact: true })).toBeVisible();
});
test("blocking note response and independent clearance persist", async ({
  page,
}) => {
  await page.goto("/");
  await select(page, "st-01");
  await navigate(page, "notes");
  await page
    .getByLabel("Note title")
    .fill("Browser duplicate receipts question");
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Resolve overlapping source amounts before filing.");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Create blocking note", exact: true })
      .click(),
  );
  await expect(page.getByRole("status")).toContainText("Saved");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: /^respond note:/ })
      .last()
      .click(),
  );
  await expect(
    page.getByRole("button", { name: /^request resolution note:/ }).last(),
  ).toBeVisible();
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: /^request resolution note:/ })
      .last()
      .click(),
  );
  await select(page, "st-02");
  await navigate(page, "notes");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: /^resolve note:/ })
      .last()
      .click(),
  );
  await expect(page.getByText(/business · resolved/)).toBeVisible();
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Note history", exact: true })
      .last()
      .click(),
  );
  await expect(page.getByTestId("workflow-audit")).toContainText(
    "resolution_requested",
  );
  await expect(page.getByTestId("workflow-audit")).toContainText("st-02");
});
test("admin assignments and clearance-protected sensitive controls", async ({
  page,
}) => {
  await page.goto("/");
  await select(page, "st-05");
  await navigate(page, "assignments");
  await page.getByLabel("Assign staff", { exact: true }).selectOption("st-04");
  await page.getByLabel("Assignment areas", { exact: true }).fill("business");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Assign / activate", exact: true })
      .click(),
  );
  await expect(page.getByRole("status")).toContainText("Saved");
  await select(page, "st-04");
  await navigate(page, "security");
  await expect(
    page.getByRole("button", {
      name: "Reveal sensitive information",
      exact: true,
    }),
  ).toBeDisabled();
  await select(page, "st-03");
  await navigate(page, "security");
  await page
    .getByLabel("Sensitive access purpose")
    .fill("Inspect source identity discrepancy for tax review");
  await clickAction(page, async () =>
    page
      .getByRole("button", {
        name: "Reveal sensitive information",
        exact: true,
      })
      .click(),
  );
  await expect(page.getByTestId("sensitive-mode")).toContainText(
    "reveal active",
  );
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "View sensitive access audit", exact: true })
      .click(),
  );
  await expect(page.getByTestId("workflow-audit")).toContainText("reveal");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Mask sensitive information", exact: true })
      .click(),
  );
  await expect(page.getByTestId("sensitive-mode")).toContainText("masked");
  await select(page, "st-04");
  await navigate(page, "security");
  await expect(page.getByTestId("sensitive-mode")).toContainText("masked");
});
test("diligence submission requires independent review and retains history", async ({
  page,
}) => {
  await page.goto("/");
  await select(page, "st-01");
  await navigate(page, "diligence");
  await page.getByLabel("Record type").selectOption("judgment");
  await page.getByLabel("Record title").fill("Browser documented tax judgment");
  await page
    .getByLabel("Record answer")
    .fill("Source overlap requires documented CPA judgment.");
  await page
    .getByLabel("Record authority")
    .fill("Supplied business receipts sources, no invented tax computation");
  await page.getByLabel("Record references").fill("D16");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Create workflow record", exact: true })
      .click(),
  );
  await expect(page.getByRole("status")).toContainText("Saved");
  const record = page
    .getByRole("listitem")
    .filter({ hasText: "Browser documented tax judgment" });
  await clickAction(page, async () =>
    record.getByRole("button", { name: /^submit / }).click(),
  );
  await expect(record).toContainText("submitted");
  await expect(record.getByRole("button", { name: /^approve / })).toHaveCount(
    0,
  );
  await select(page, "st-02");
  await navigate(page, "diligence");
  const submitted = page
    .getByRole("listitem")
    .filter({ hasText: "Browser documented tax judgment" });
  await clickAction(page, async () =>
    submitted.getByRole("button", { name: /^approve / }).click(),
  );
  await expect(submitted).toContainText("approved");
  await clickAction(page, async () =>
    submitted.getByRole("button", { name: /^History / }).click(),
  );
  await expect(page.getByTestId("workflow-audit")).toContainText("st-01");
  await expect(page.getByTestId("workflow-audit")).toContainText("st-02");
});
test("identity switch clears a second tab and re-locks its workspace", async ({
  page,
  context,
}) => {
  await page.goto("/");
  await select(page, "st-01");
  const other = await context.newPage();
  await other.goto("/");
  await expect(other.getByTestId("current-session")).toContainText("st-01");
  await select(other, "st-03");
  await expect(
    page.getByText("Session changed in another tab. Reload before continuing."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Return Explorer", exact: true }),
  ).toHaveCount(0);
  await page.reload();
  await expect(page.getByTestId("current-session")).toContainText("st-03");
});
