import { test, expect } from "@playwright/test";
import { navigate, clickAction } from "../tests/ui-helpers";

test("UI creates a review note and retrieves its audit history only through same-origin FastAPI", async ({
  page,
}) => {
  const calls: { method: string; url: string }[] = [];
  page.on("request", (request) => {
    if (["fetch", "xhr"].includes(request.resourceType()))
      calls.push({ method: request.method(), url: request.url() });
  });
  await page.goto("/");
  await expect(page.getByTestId("current-session")).toContainText("st-01");
  await navigate(page, "notes");
  await page.getByLabel("Note title").fill("FastAPI integration note");
  await page
    .getByLabel("Review note", { exact: true })
    .fill(
      "Resolve the fictional receipts discrepancy before simulated approval.",
    );
  const created = page.waitForResponse(
    (r) =>
      r.request().method() === "POST" &&
      new URL(r.url()).pathname === "/api/workflow/notes",
  );
  await clickAction(page, () =>
    page
      .getByRole("button", { name: "Create blocking note", exact: true })
      .click(),
  );
  const response = await created;
  expect(response.status()).toBe(200);
  expect(response.request().postDataJSON()).toMatchObject({
    action: "create",
    title: "FastAPI integration note",
    expected_revision: 0,
  });
  const entity = await response.json();
  expect(entity).toMatchObject({ kind: "note", state: "open" });
  const history = page.waitForResponse(
    (r) =>
      new URL(r.url()).pathname === "/api/workflow/history" &&
      new URL(r.url()).searchParams.get("entity_id") === entity.id,
  );
  await page
    .getByRole("button", { name: "Note history", exact: true })
    .last()
    .click();
  const audit = await history;
  expect(audit.status()).toBe(200);
  expect((await audit.json()).events.length).toBeGreaterThan(0);
  await expect(page.getByTestId("workflow-audit")).toContainText(
    "FastAPI integration note",
  );
  await page.reload();
  await expect(
    page.getByText("FastAPI integration note", { exact: true }),
  ).toBeVisible();
  for (const call of calls) {
    const url = new URL(call.url);
    expect(url.origin).toBe("https://localhost:3300");
    expect(url.pathname).toMatch(/^\/api\//);
  }
  expect(
    calls.some(
      (c) =>
        c.method === "POST" &&
        new URL(c.url).pathname === "/api/workflow/notes",
    ),
  ).toBe(true);
  expect(
    calls.some(
      (c) =>
        c.method === "GET" &&
        new URL(c.url).pathname === "/api/workflow/history",
    ),
  ).toBe(true);
});

test("actual finding-review UI uses the supported PATCH alias in the public sandbox", async ({
  page,
}) => {
  const listing = page.waitForResponse(
    (r) =>
      new URL(r.url()).pathname === "/api/reviews" &&
      r.request().method() === "GET",
  );
  await page.goto("/?view=findings");
  await expect(page.getByTestId("current-session")).toContainText("st-01");
  const firstFinding = (await (await listing).json()).findings[0];
  await page
    .locator("#main-content")
    .getByRole("button")
    .filter({ hasText: firstFinding.title })
    .first()
    .click();
  await page
    .getByLabel("Review status", { exact: true })
    .selectOption("in_review");
  await page
    .getByLabel("Reviewer note", { exact: true })
    .fill("Public finding review saved through FastAPI.");
  const saved = page.waitForResponse(
    (r) =>
      r.request().method() === "PATCH" &&
      new URL(r.url()).pathname === "/api/review-decision",
  );
  await page.getByRole("button", { name: "Save Review", exact: true }).click();
  const response = await saved;
  expect(response.status()).toBe(200);
  expect(response.request().postDataJSON()).toMatchObject({
    status: "in_review",
    note: "Public finding review saved through FastAPI.",
    actor_role: "preparer",
  });
  await expect(
    page
      .getByText("Public finding review saved through FastAPI.", {
        exact: false,
      })
      .last(),
  ).toBeVisible();
});
