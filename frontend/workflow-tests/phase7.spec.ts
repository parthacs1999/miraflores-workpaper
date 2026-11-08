import { clickAction, navigate, openSessionMenu } from "../tests/ui-helpers";
import { test, expect, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
const API = "http://localhost:8200";
type Item = {
  id: string;
  revision: number;
  state: string;
  data: Record<string, unknown>;
};
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
async function product(page: Page, tab: string) {
  await navigate(
    page,
    (
      {
        "Evidence Attachments": "attachments",
        "Questions & Responses": "collaboration",
        "Bulk Actions": "bulk",
        "Firm Operations": "operations",
      } as Record<string, string>
    )[tab],
  );
}
async function save(page: Page, name: string, path: string): Promise<Item> {
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/product" + path) &&
      r.request().method() === "POST",
  );
  await clickAction(page, async () =>
    page
      .getByTestId("product-workspace")
      .getByRole("button", { name, exact: true })
      .click(),
  );
  const r = await response;
  expect(r.status(), await r.text()).toBe(200);
  return r.json();
}
async function rationale(
  page: Page,
  note = "Documented Phase 7 workpaper action",
) {
  await page.getByLabel("Product rationale").fill(note);
}
async function createQuestion(page: Page, title: string) {
  await product(page, "Questions & Responses");
  await page.getByLabel("Question title").fill(title);
  await rationale(
    page,
    "Explain source uncertainty before independent resolution",
  );
  await page.getByLabel("Product evidence references").fill("D14");
  return save(page, "Create workpaper question", "/questions");
}

async function markSeen(page: Page) {
  const saved = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/product/checkpoint") &&
      r.request().method() === "POST",
  );
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Mark displayed changes seen", exact: true })
      .click(),
  );
  const response = await saved;
  expect(response.status()).toBe(200);
  const cp = await response.json();
  await expect(page.getByTestId("live-updates")).toContainText(
    "Personal checkpoint: " + cp.cursor + ".",
  );
}

test("uploaded originals have hashes, audited downloads and independent support review", async ({
  page,
}) => {
  await page.goto("/");
  await select(page);
  await product(page, "Evidence Attachments");
  await rationale(
    page,
    "Supporting original, no extraction or tax result implied",
  );
  await page.getByLabel("Attachment title").fill("Phase7 receipts evidence");
  const contents = "Business receipts evidence supplied by client.\n";
  await page.getByLabel("Evidence file").setInputFiles({
    name: "phase7-source.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(contents),
  });
  const a = await save(page, "Upload supporting evidence", "/attachments");
  await expect(
    page.getByTestId("attachment-card").filter({ hasText: a.id }),
  ).toContainText("not_extracted");
  await select(page, "st-02");
  await product(page, "Evidence Attachments");
  await page
    .getByLabel("Attachment access purpose")
    .fill("Independently inspect supplied receipts evidence");
  const dl = page.waitForEvent("download");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Download original " + a.id, exact: true })
      .click(),
  );
  const downloaded = await dl;
  expect(await readFile((await downloaded.path())!, "utf8")).toBe(contents);
  await expect(
    page.getByTestId("product-workspace").getByRole("status"),
  ).toContainText("SHA-256 verified");
  await rationale(
    page,
    "Original inspected as support; this is not extraction",
  );
  await save(
    page,
    "Record independent support review " + a.id,
    "/attachments/" + a.id + "/actions",
  );
  await expect(
    page.getByTestId("attachment-card").filter({ hasText: a.id }),
  ).toContainText("manual_support_review_not_extraction");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Attachment history " + a.id, exact: true })
      .click(),
  );
  await expect(page.getByTestId("product-detail")).toContainText("uploaded");
  await expect(page.getByTestId("product-detail")).toContainText("review");
});

test("two staff contexts receive live changes, reconnect missed events and retain individual checkpoints", async ({
  page,
  browser,
}) => {
  await page.goto("/");
  await select(page, "st-02");
  await page
    .getByRole("button", {
      name: "Open activity and notifications",
      exact: true,
    })
    .click();
  await expect(page.getByTestId("live-connection")).toContainText("Live");
  await markSeen(page);
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Pause live updates", exact: true })
      .click(),
  );
  const otherContext = await browser.newContext();
  try {
    const other = await otherContext.newPage();
    await other.goto("/");
    await select(other);
    const q = await createQuestion(other, "Phase7 live reconnect question");
    await expect(page.getByTestId("live-updates")).not.toContainText(q.id);
    await clickAction(page, async () =>
      page
        .getByRole("button", { name: "Reconnect live updates", exact: true })
        .click(),
    );
    await expect(page.getByTestId("live-updates")).toContainText(q.id);
    await clickAction(page, async () =>
      page
        .getByTestId("live-updates")
        .getByText(/Change summaries/)
        .click(),
    );
    await expect(
      page.getByTestId("live-change").filter({ hasText: q.id }),
    ).toBeVisible();
    await markSeen(page);
    await page.reload();
    await page
      .getByRole("button", {
        name: "Open activity and notifications",
        exact: true,
      })
      .click();
    await expect(page.getByTestId("live-connection")).toContainText("Live");
    await expect(page.getByTestId("live-updates")).not.toContainText(q.id);
    const authorCheckpoint = await other.request.get(
      API + "/api/product/changes",
    );
    expect((await authorCheckpoint.json()).checkpoint.cursor).toBe(0);
  } finally {
    await otherContext.close();
  }
});

test("multi-select submission retries idempotently and undo compensates without erasing history", async ({
  page,
}) => {
  await page.goto("/");
  await select(page);
  const records: Item[] = [];
  for (const title of ["Phase7 bulk source A", "Phase7 bulk source B"]) {
    await navigate(page, "diligence");
    await page.getByLabel("Record title").fill(title);
    await page
      .getByLabel("Record answer")
      .fill("Compared supplied receipts sources");
    await page.getByLabel("Record authority").fill("Supplied packet sources");
    await page.getByLabel("Record references").fill("D14");
    const saved = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/workflow/records") &&
        r.request().method() === "POST",
    );
    await clickAction(page, async () =>
      page
        .getByRole("button", { name: "Create workflow record", exact: true })
        .click(),
    );
    const r = await saved;
    expect(r.status()).toBe(200);
    records.push(await r.json());
  }
  await product(page, "Bulk Actions");
  await page.getByLabel("Bulk operation").selectOption("submit_records");
  await page.getByLabel("Search bulk items").fill("Phase7 bulk source");
  await expect(page.getByLabel("Select " + records[0].id)).toBeVisible();
  for (const r of records)
    await page.getByLabel("Select " + r.id, { exact: true }).check();
  await rationale(page, "Submit both related preparations atomically");
  let dropped = false;
  await page.route("**/api/product/bulk", async (route) => {
    if (!dropped) {
      dropped = true;
      await route.fetch();
      await route.abort("failed");
    } else await route.continue();
  });
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Apply atomic bulk action", exact: true })
      .click(),
  );
  await expect(
    page.getByRole("button", {
      name: "Retry identical bulk request",
      exact: true,
    }),
  ).toBeVisible();
  const b = await save(page, "Retry identical bulk request", "/bulk");
  await page.unroute("**/api/product/bulk");
  await expect(
    page.getByTestId("bulk-record").filter({ hasText: b.id }),
  ).toContainText("applied");
  await rationale(page, "Compensate the submission; preserve review history");
  await save(page, "Undo with compensation " + b.id, "/bulk/" + b.id + "/undo");
  await expect(
    page.getByTestId("bulk-record").filter({ hasText: b.id }),
  ).toContainText("undone");
  await expect(
    page.getByLabel("Select " + records[0].id, { exact: true }),
  ).toBeVisible();
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Bulk history " + b.id, exact: true })
      .click(),
  );
  await expect(page.getByTestId("product-detail")).toContainText("compensated");
});

test("threaded client and colleague responses persist and require independent resolution", async ({
  page,
}) => {
  await page.goto("/");
  await select(page);
  const q = await createQuestion(page, "Phase7 blocking client question");
  await page.getByLabel("Declared response source").selectOption("cu-01");
  await page
    .getByLabel("Discussion response")
    .fill("Client says duplicated scan does not represent additional receipts");
  const m = await save(
    page,
    "Record response " + q.id,
    "/questions/" + q.id + "/messages",
  );
  await expect(
    page.getByTestId("question-card").filter({ hasText: q.id }),
  ).toContainText("staff_mediated_client_demo_not_authenticated");
  await select(page, "st-02");
  await product(page, "Questions & Responses");
  await page
    .getByLabel("Discussion response")
    .fill("Colleague compared the source ledger with the client explanation");
  await page.getByLabel("Reply parent ID").fill(m.id);
  await page.getByLabel("Product evidence references").fill("D14");
  await save(
    page,
    "Record response " + q.id,
    "/questions/" + q.id + "/messages",
  );
  await rationale(page, "Response prepared for independent clearance");
  await save(
    page,
    "request resolution " + q.id,
    "/questions/" + q.id + "/actions",
  );
  await clickAction(page, async () =>
    page.getByRole("button", { name: "resolve " + q.id, exact: true }).click(),
  );
  await expect(
    page.getByTestId("product-workspace").getByRole("alert"),
  ).toContainText("cannot review or sign off their own work");
  await select(page, "st-03");
  await product(page, "Questions & Responses");
  await rationale(
    page,
    "Independently reviewed evidence and resolved the professional question",
  );
  await save(page, "resolve " + q.id, "/questions/" + q.id + "/actions");
  await expect(
    page.getByTestId("question-card").filter({ hasText: q.id }),
  ).toContainText("resolved");
  await page.reload();
  await product(page, "Questions & Responses");
  await expect(
    page.getByTestId("question-card").filter({ hasText: q.id }),
  ).toContainText("Colleague compared");
  await expect(
    page.getByTestId("question-card").filter({ hasText: q.id }),
  ).toContainText("resolved");
});

test("firm operations uses packet budgets, actual time and audited assignment undo", async ({
  page,
}) => {
  await page.goto("/");
  await select(page);
  await product(page, "Firm Operations");
  await rationale(page, "Actual time spent comparing source receipts");
  await page.getByLabel("Time minutes").fill("95");
  await save(page, "Record actual time", "/time");
  await expect(page.getByTestId("operations-totals")).toContainText(
    "actual 95 minutes",
  );
  await page.getByLabel("Engagement search").fill("nonexistent household");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Search engagements", exact: true })
      .click(),
  );
  await expect(
    page.getByText("No matching supplied engagements.", { exact: true }),
  ).toBeVisible();
  await select(page, "st-05");
  await navigate(page, "operations");
  await expect(page.getByTestId("operations-totals")).toContainText(
    "actual 95 minutes",
  );
  await rationale(page, "Revise budget while preserving original packet hours");
  await page.getByLabel("Budget hours").fill("1.25");
  await save(page, "Save budget revision", "/budgets");
  await expect(
    page
      .getByRole("table", { name: /Budget versus actual/ })
      .getByRole("row")
      .filter({ hasText: "business" }),
  ).toContainText("OVER BUDGET");
  await navigate(page, "bulk");
  await clickAction(page, async () =>
    page.getByRole("button", { name: "Select this page", exact: true }).click(),
  );
  await page.getByLabel("Bulk assignee").selectOption("st-01");
  await rationale(page, "Assign visible deadlines as one atomic operation");
  const b = await save(page, "Apply atomic bulk action", "/bulk");
  await rationale(page, "Compensate assignment change without deleting it");
  await save(page, "Undo with compensation " + b.id, "/bulk/" + b.id + "/undo");
  await expect(
    page.getByTestId("bulk-record").filter({ hasText: b.id }),
  ).toContainText("undone");
});

test("attachment signatures, area restrictions and uncleared downloads fail closed", async ({
  page,
}) => {
  await page.goto("/");
  await select(page);
  await product(page, "Evidence Attachments");
  await rationale(page, "Invalid file must be rejected");
  await page.getByLabel("Evidence file").setInputFiles({
    name: "not-a-real.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("This is plain text, not a PDF"),
  });
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Upload supporting evidence", exact: true })
      .click(),
  );
  await expect(
    page.getByTestId("product-workspace").getByRole("alert"),
  ).toContainText("Invalid PDF");
  const all = await page.request.get(API + "/api/product/overview");
  const attachment = (await all.json()).items.find((r: Item) =>
    r.id.startsWith("attachment:"),
  );
  await select(page, "st-04");
  await product(page, "Evidence Attachments");
  await expect(
    page.getByRole("button", {
      name: "Download original " + attachment.id,
      exact: true,
    }),
  ).toHaveCount(0);
  expect(
    (
      await page.request.get(
        API + "/api/product/attachments/" + attachment.id + "/download",
      )
    ).status(),
  ).toBe(403);
  expect((await page.request.get(API + "/api/return-lines")).status()).toBe(
    403,
  );
  await select(page, "st-05");
  expect((await page.request.get(API + "/api/product/overview")).status()).toBe(
    403,
  );
  expect((await page.request.get(API + "/api/product/changes")).status()).toBe(
    403,
  );
});

test("new supporting questions invalidate related signoffs and never clear real readiness", async ({
  page,
}) => {
  await page.goto("/");
  await select(page);
  await navigate(page, "diligence");
  await page.getByLabel("Record area").selectOption("vehicle");
  await page
    .getByLabel("Record title")
    .fill("Phase7 vehicle preparation attribution");
  await page
    .getByLabel("Record answer")
    .fill(
      "Compared supplied vehicle inputs; unsupported eligibility remains open",
    );
  await page.getByLabel("Record authority").fill("Supplied packet");
  await page.getByLabel("Record references").fill("D18");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Create workflow record", exact: true })
      .click(),
  );
  await expect(page.getByRole("status")).toContainText("Saved");
  await select(page, "st-02");
  await navigate(page, "signoffs");
  await page.getByLabel("Sign-off area").selectOption("vehicle");
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
  await select(page);
  await product(page, "Questions & Responses");
  await page.getByLabel("Product area").selectOption("vehicle");
  await page
    .getByLabel("Question title")
    .fill("Phase7 new vehicle evidence uncertainty");
  await page.getByLabel("Product evidence references").fill("D18");
  await rationale(
    page,
    "Blocking vehicle question introduced after prior review",
  );
  await save(page, "Create workpaper question", "/questions");
  await navigate(page, "signoffs");
  await expect(
    page
      .locator("article")
      .filter({ hasText: /vehicle · reviewer/ })
      .last(),
  ).toContainText("invalidated");
  await navigate(page, "readiness");
  await expect(page.getByTestId("filing-readiness")).toHaveText(
    "FILING BLOCKED",
  );
  await expect(page.getByText(/OPEN_BLOCKING_QUESTION/)).toBeVisible();
});
