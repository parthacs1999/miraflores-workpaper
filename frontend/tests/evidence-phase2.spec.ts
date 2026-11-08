import { test, expect, Page } from "@playwright/test";
const API = process.env.E2E_API_URL ?? "http://localhost:8000";

async function openWageEvidence(page: Page) {
  await page.goto("/");
  await page.getByPlaceholder("Search by form, line, or description...").fill("F1040.1a");
  await page.getByRole("button", { name: /F1040\.1a/ }).click();
  await page.getByRole("button", { name: "ev-0016", exact: true }).click();
  await expect(page.getByTestId("source-verification")).toBeVisible();
}

test("all documents have accountable dispositions and reverse tracing", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Document Accountability", exact: true }).click();
  const dashboard = page.getByTestId("document-accountability");
  await expect(dashboard.getByText("74 documents accounted for", { exact: true })).toBeVisible();
  await expect(dashboard.getByTestId(/^accountability-D/)).toHaveCount(74);
  await page.getByLabel("Document disposition").selectOption("superseded");
  await expect(page.getByTestId("accountability-D30")).toContainText("superseded");
  await expect(page.getByTestId("accountability-D30")).toContainText("unextracted");
  await page.getByLabel("Document disposition").selectOption("all");
  await page.getByLabel("Accountability document search").fill("D23");
  await expect(page.getByTestId("accountability-D23")).toContainText("Page 3 duplicates page 2");
  await page.getByLabel("Accountability document search").fill("D09");
  await page.getByRole("button", { name: "Inspect D09 document", exact: true }).click();
  const inspector = page.getByTestId("document-inspector");
  await inspector.getByText("Reverse document tracing", { exact: true }).click();
  await expect(inspector.getByRole("heading", { name: /Direct calculations/ })).toBeVisible();
  await expect(inspector.getByRole("heading", { name: /Indirect dependent calculations/ })).toBeVisible();
  await expect(inspector.getByRole("heading", { name: /Associated findings/ })).toBeVisible();
  await expect(inspector.getByRole("button", { name: /F1040\.1a · Wages/ })).toBeVisible();
  await expect(inspector.getByRole("button", { name: /F1040\.24 · Total tax/ })).toBeVisible();
  await inspector.getByRole("button", { name: /F1040\.1a · Wages/ }).click();
  await expect(page.getByRole("button", { name: "ev-0016", exact: true })).toBeVisible();
});

test("CPA field verification persists with exact source location and append-only history", async ({ page, request }) => {
  const automaticBefore = await (await request.get(`${API}/api/source-verification/ev-0016`)).json();
  await openWageEvidence(page);
  await expect(page.getByTestId("verification-status")).toHaveText("Supported");
  const human = page.getByTestId("field-verification");
  await expect(human.getByTestId("human-verification-status")).toHaveText("No human verification recorded");
  await page.getByLabel("Field verifier", { exact: true }).selectOption("st-02");
  await page.getByLabel("Specific source location").selectOption({ index: 1 });
  await expect(page.getByTestId("human-source-highlight")).toHaveText("104,600.00");
  await page.getByLabel("Field verification notes").fill("CPA inspected D08 Box 1, not another equal amount on the page.");
  await page.getByLabel("I reviewed the specific field and source").check();
  await page.getByRole("button", { name: "Record field verification", exact: true }).click();
  await expect(page.getByTestId("human-verification-status")).toContainText("confirmed · cpa_attestation · st-02");
  await expect(page.getByTestId("field-verification-history")).toContainText("CPA inspected D08 Box 1");
  await openWageEvidence(page);
  await expect(page.getByTestId("human-verification-status")).toContainText("confirmed · cpa_attestation · st-02");
  await page.getByLabel("Specific source location").selectOption({ index: 1 });
  await page.getByLabel("Verification outcome").selectOption("revoked");
  await page.getByLabel("Field verification notes").fill("Revoke this demonstration attestation while retaining the original history.");
  await page.getByLabel("I reviewed the specific field and source").check();
  await page.getByRole("button", { name: "Record field verification", exact: true }).click();
  await expect(page.getByTestId("human-verification-status")).toContainText("revoked");
  const audit = await (await request.get(`${API}/api/field-verifications/ev-0016`)).json();
  expect(audit.events.map((event: { status: string }) => event.status)).toEqual(["confirmed", "revoked"]);
  expect(audit.events.every((event: { currently_confirmed: boolean }) => !event.currently_confirmed)).toBeTruthy();
  expect(await (await request.get(`${API}/api/source-verification/ev-0016`)).json()).toEqual(automaticBefore);
});

test("ambiguous identical mileage values require a reviewed source occurrence", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Document Explorer", exact: true }).click();
  await page.getByPlaceholder("Search documents...").fill("D23");
  await page.getByRole("button", { name: /^D23\s/ }).click();
  const inspector = page.getByTestId("document-inspector");
  await inspector.getByText(/Extracted fields \(/).click();
  await inspector.getByRole("button", { name: /^ev-0169 ·/ }).click();
  await expect(page.getByTestId("automatic-field-assessment")).toContainText("ambiguous");
  await expect(page.getByTestId("verification-status")).toHaveText("Unverified");
  await expect(page.getByTestId("source-highlight")).toHaveCount(0);
  await expect(page.getByText(/Identical text occurs .* times/)).toBeVisible();
  await page.getByLabel("Field verification notes").fill("Reviewing repeated mileage amounts; must select the correct trip.");
  await page.getByLabel("I reviewed the specific field and source").check();
  await expect(page.getByRole("button", { name: "Record field verification", exact: true })).toBeDisabled();
  await page.getByLabel("Specific source location").selectOption({ index: 1 });
  await page.getByLabel("I reviewed the specific field and source").check();
  await expect(page.getByRole("button", { name: "Record field verification", exact: true })).toBeEnabled();
});

test("unified resolver exposes typed records and explicit unresolved reasons", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Evidence Resolver", exact: true }).click();
  await page.getByLabel("Evidence reference", { exact: true }).fill("ref:fx.SEK.2025_year_end");
  await page.getByRole("button", { name: "Resolve evidence", exact: true }).click();
  await expect(page.getByTestId("resolution-status")).toHaveText("resolved · fx_rate");
  await expect(page.getByTestId("evidence-resolver").locator("pre")).toHaveText("9.71");
  await page.getByLabel("Evidence reference", { exact: true }).fill("py:/missing-record");
  await page.getByRole("button", { name: "Resolve evidence", exact: true }).click();
  await expect(page.getByTestId("resolution-status")).toHaveText("unresolved · prior_year");
  await expect(page.getByTestId("evidence-resolver")).toContainText("missing_reference");
  await page.getByRole("button", { name: "Review Findings", exact: true }).click();
  await page.getByRole("button").filter({ hasText: "F1040.12:" }).first().click();
  await page.getByRole("button", { name: "Open reference py:/return_2024/lines/F1040.12", exact: true }).click();
  await expect(page.getByTestId("resolution-status")).toHaveText("resolved · prior_year");
});
