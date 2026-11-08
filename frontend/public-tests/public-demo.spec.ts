import { test, expect } from "@playwright/test";

test("one URL opens a private fictional workpaper without credentials and offers simulated roles", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByTestId("current-session")).toContainText("st-01");
  await expect(page.locator(".firm-workspace")).toHaveAttribute(
    "data-loaded",
    "true",
  );
  await expect(page.getByTestId("public-demo-warning")).toContainText(
    "FILING BLOCKED",
  );
  await expect(page.getByLabel("Configured credential")).toHaveCount(0);
  await page.getByLabel("Switch simulated demo role", { exact: true }).click();
  await page
    .getByLabel("Simulated demo role", { exact: true })
    .selectOption("st-03");
  await expect(page.getByTestId("current-session")).toContainText("st-03");
  await expect(page.getByTestId("public-demo-warning")).toContainText(
    "not authenticated identities",
  );
  expect(errors).toEqual([]);
});

test("two independent visitors do not share notes, reviews, or role changes", async ({
  browser,
}) => {
  const a = await browser.newContext({
      ignoreHTTPSErrors: true,
      baseURL: "https://localhost:3300",
    }),
    b = await browser.newContext({
      ignoreHTTPSErrors: true,
      baseURL: "https://localhost:3300",
    });
  const ap = await a.newPage(),
    bp = await b.newPage();
  const initialSession = ap.waitForResponse(
    (r) =>
      r.url().endsWith("/api/workflow/session") &&
      r.request().method() === "GET",
  );
  await Promise.all([ap.goto("/"), bp.goto("/")]);
  await expect(ap.getByTestId("current-session")).toContainText("st-01");
  await expect(bp.getByTestId("current-session")).toContainText("st-01");
  const session = await (await initialSession).json();
  const response = await ap.request.post("/api/workflow/notes", {
    headers: {
      Origin: "https://localhost:3300",
      "X-CSRF-Token": session.csrf_token,
    },
    data: {
      area: "business",
      action: "create",
      title: "Only visitor A can see this",
      note: "Fictional isolated demonstration note",
      owner_id: "st-01",
      expected_revision: 0,
    },
  });
  expect(response.status()).toBe(200);
  expect(
    await (await ap.request.get("/api/workflow/overview")).text(),
  ).toContain("Only visitor A can see this");
  expect(
    await (await bp.request.get("/api/workflow/overview")).text(),
  ).not.toContain("Only visitor A can see this");
  await ap.getByLabel("Switch simulated demo role", { exact: true }).click();
  await ap
    .getByLabel("Simulated demo role", { exact: true })
    .selectOption("st-02");
  await expect(ap.getByTestId("current-session")).toContainText("st-02");
  await expect(bp.getByTestId("current-session")).toContainText("st-01");
  await a.close();
  await b.close();
});

test("unsafe actions stay blocked and private reset clears only this visitor", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByTestId("current-session")).toContainText("st-01");
  expect(
    (await page.request.post("/api/lifecycle/filings", { data: {} })).status(),
  ).toBe(403);
  expect(
    (
      await page.request.post("/api/workflow/assignments", { data: {} })
    ).status(),
  ).toBe(403);
  expect(
    (
      await page.request.post("/api/product/attachments", { data: {} })
    ).status(),
  ).toBe(403);
  expect(
    (
      await page.request.get("/api/documents/D71", {
        headers: { "X-Sensitive-Access": "reveal" },
      })
    ).status(),
  ).toBe(403);
  expect(
    (await (await page.request.get("/api/workflow/readiness")).json())
      .filing_ready,
  ).toBe(false);
  const old = (await page.context().cookies()).find(
    (c) => c.name === "mf_demo",
  )?.value;
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", { name: "Reset my demo", exact: true })
    .click();
  await expect(page.getByTestId("current-session")).toContainText("st-01");
  await expect
    .poll(
      async () =>
        (await page.context().cookies()).find((c) => c.name === "mf_demo")
          ?.value,
    )
    .not.toBe(old);
});
