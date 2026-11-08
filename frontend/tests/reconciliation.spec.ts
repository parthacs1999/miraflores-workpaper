import { clickAction } from "./ui-helpers";
import { test, expect, Page } from "@playwright/test";
const API = process.env.E2E_API_URL ?? "http://localhost:8000";
async function openReceipts(page: Page) {
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Reconciliation Dashboard", exact: true })
      .click(),
  );
  await page.getByLabel("Find reconciliation issue").fill("business.receipts");
  await clickAction(page, async () =>
    page
      .getByRole("button", {
        name: "Inspect reconciliation business.receipts",
        exact: true,
      })
      .click(),
  );
}

test("independent receipts reconciliation links a partner-approved correction and preserves the engine", async ({
  page,
  request,
}) => {
  const baseline = await (
    await request.get(`${API}/api/return-lines?version=v3`)
  ).json();
  await page.goto("/");
  await openReceipts(page);
  const calc = page.getByTestId("reconciliation-calculation");
  await expect(calc.getByTestId("reconciliation-expected")).toHaveText(
    "151300",
  );
  await expect(calc.getByTestId("reconciliation-difference")).toHaveText(
    "12400",
  );
  await expect(calc).toContainText("163700");
  await clickAction(page, async () =>
    calc
      .getByRole("button", { name: "doc:D15#page3", exact: true })
      .first()
      .click(),
  );
  await expect(page.getByTestId("resolution-status")).toHaveText(
    "resolved · document_page",
  );
  await clickAction(page, async () =>
    page
      .getByTestId("evidence-resolver")
      .getByRole("button", { name: "Open D15", exact: true })
      .click(),
  );
  await clickAction(page, async () =>
    page
      .getByTestId("document-inspector")
      .getByText(/Extracted fields \(/)
      .click(),
  );
  await clickAction(page, async () =>
    page
      .getByTestId("document-inspector")
      .getByRole("button", { name: /^ev-0109 ·/ })
      .click(),
  );
  await expect(page.getByTestId("source-verification")).toBeVisible();
  await expect(page.getByTestId("field-verification")).toBeVisible();
  await page
    .getByLabel("Reconciliation reviewer", { exact: true })
    .selectOption("st-01");
  await page
    .getByLabel("Reconciliation notes", { exact: true })
    .fill(
      "D14 and D15 page 3 establish that Paywell receipts were already booked.",
    );
  await page
    .getByLabel("Reconciliation authority", { exact: true })
    .fill(
      "Printed D14/D15/D21 and packet R-SCHC-GROSS; no tax engine recomputation.",
    );
  await clickAction(page, async () =>
    page
      .getByRole("button", {
        name: "Create linked adjustment draft",
        exact: true,
      })
      .click(),
  );
  await expect(page.getByRole("status")).toContainText(
    "Draft correction linked",
  );
  const unified = await (
    await request.get(`${API}/api/unified-findings`)
  ).json();
  const finding = unified.findings.find(
    (f: { issue_key: string }) => f.issue_key === "business.receipts",
  );
  const adjustment = finding.adjustment_links[0];
  expect(adjustment.state).toBe("draft");
  await clickAction(page, async () =>
    page
      .getByRole("button", {
        name: `Open adjustment ${adjustment.id}`,
        exact: true,
      })
      .click(),
  );
  await expect(page.getByTestId("adjustment-state")).toHaveText("draft");
  await expect(page.getByTestId("adjustment-history")).toContainText("created");
  await page
    .getByLabel("Adjustment action note")
    .fill("Submit independent source reconciliation.");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Submit adjustment", exact: true })
      .click(),
  );
  await expect(page.getByTestId("adjustment-state")).toHaveText("submitted");
  await page.getByLabel("Adjustment staff").selectOption("st-03");
  await page
    .getByLabel("Adjustment action note")
    .fill("Partner approves source-supported correction over $1,000.");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Approve adjustment", exact: true })
      .click(),
  );
  await expect(page.getByTestId("adjustment-state")).toHaveText("approved");
  await openReceipts(page);
  await page
    .getByLabel("Approved correction for resolution")
    .selectOption(adjustment.id);
  await page
    .getByLabel("Reconciliation decision status")
    .selectOption("resolved");
  await page
    .getByLabel("Reconciliation disposition")
    .selectOption("correction_linked");
  await page
    .getByLabel("Reconciliation notes", { exact: true })
    .fill(
      "Resolved by the explicitly linked, independently approved ledger adjustment.",
    );
  await page
    .getByLabel("Reconciliation authority", { exact: true })
    .fill("D14/D15/D21 reconciliation and Helen Strand partner approval.");
  await clickAction(page, async () =>
    page
      .getByRole("button", {
        name: "Save reconciliation decision",
        exact: true,
      })
      .click(),
  );
  await expect(page.getByTestId("reconciliation-review-status")).toHaveText(
    "resolved",
  );
  await page.reload();
  await openReceipts(page);
  await expect(page.getByTestId("reconciliation-review-status")).toHaveText(
    "resolved",
  );
  await expect(page.getByTestId("reconciliation-history")).toContainText(
    "independently approved ledger adjustment",
  );
  await expect(page.getByTestId("reconciliation-calculation")).toContainText(
    "163700",
  );
  expect(
    await (await request.get(`${API}/api/return-lines?version=v3`)).json(),
  ).toEqual(baseline);
});

test("unsupported tax calculations stay explicit and cannot create corrections", async ({
  page,
}) => {
  await page.goto("/");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Reconciliation Dashboard", exact: true })
      .click(),
  );
  await clickAction(page, async () =>
    page
      .getByText("All checks, including matches and unsupported calculations", {
        exact: true,
      })
      .click(),
  );
  await page
    .getByLabel("Select reconciliation check")
    .selectOption("california.amt");
  await expect(page.getByTestId("reconciliation-conclusion")).toHaveText(
    "unsupported",
  );
  await expect(page.getByTestId("reconciliation-expected")).toHaveText(
    "Unsupported / unknown",
  );
  await expect(
    page.getByRole("button", {
      name: "Create linked adjustment draft",
      exact: true,
    }),
  ).toBeDisabled();
  await expect(page.getByTestId("reconciliation-calculation")).toContainText(
    "explicitly not computed",
  );
  await page
    .getByLabel("Reconciliation jurisdiction")
    .selectOption("california");
  await expect(
    page.getByRole("button", {
      name: "Inspect reconciliation california.amt",
      exact: true,
    }),
  ).toBeVisible();
});

test("one mileage issue retains both the mileage and deduction computations", async ({
  page,
}) => {
  await page.goto("/");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Reconciliation Dashboard", exact: true })
      .click(),
  );
  await page.getByLabel("Find reconciliation issue").fill("vehicle");
  await expect(
    page.getByRole("button", {
      name: "Inspect reconciliation vehicle.miles",
      exact: true,
    }),
  ).toHaveCount(1);
  await expect(
    page.getByRole("button", {
      name: "Inspect reconciliation vehicle.deduction",
      exact: true,
    }),
  ).toHaveCount(0);
  await clickAction(page, async () =>
    page
      .getByRole("button", {
        name: "Inspect reconciliation vehicle.miles",
        exact: true,
      })
      .click(),
  );
  await expect(page.getByTestId("reconciliation-expected")).toHaveText("8100");
  await clickAction(page, async () =>
    page
      .getByText("All checks, including matches and unsupported calculations", {
        exact: true,
      })
      .click(),
  );
  await page
    .getByLabel("Select reconciliation check")
    .selectOption("vehicle.deduction");
  await expect(page.getByTestId("reconciliation-expected")).toHaveText("5670");
  await expect(page.getByTestId("reconciliation-difference")).toHaveText(
    "2590",
  );
  await expect(page.getByTestId("reconciliation-review")).toContainText(
    "recon:vehicle.miles",
  );
});
