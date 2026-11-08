import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createHash } from "node:crypto";
function tokens(): Record<string, string> {
  return JSON.parse(
    readFileSync(join(process.env.PROXY_E2E_DIR!, "tokens.json"), "utf8"),
  );
}
async function login(page: import("@playwright/test").Page, staff = "st-01") {
  await page.goto("/");
  await expect(page.getByTestId("assignment-demo-warning")).toBeVisible();
  await page.getByLabel("Session staff", { exact: true }).selectOption(staff);
  await page
    .getByLabel("Configured credential", { exact: true })
    .fill(tokens()[staff]);
  await page
    .getByRole("button", { name: "Start / switch session", exact: true })
    .click();
  await expect(page.getByTestId("current-session")).toContainText(staff);
  await expect(page.locator(".firm-workspace")).toHaveAttribute(
    "data-loaded",
    "true",
  );
}
test("assignment HTTPS login labels state loss, preserves role selection boundaries and clears on logout", async ({
  page,
}) => {
  expect((await page.request.get("/api/documents")).status()).toBe(401);
  await login(page);
  await page
    .getByLabel("Switch staff session", { exact: true })
    .click();
  await expect(
    page.getByLabel("Session staff", { exact: true }),
  ).toBeDisabled();
  await expect(page.getByTestId("assignment-demo-warning")).toContainText(
    "disappear",
  );
  const cookie = (await page.context().cookies()).find(
    (c) => c.name === "mf_session",
  );
  expect(cookie?.secure && cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Strict");
  await page.getByRole("button", { name: "End session", exact: true }).click();
  await expect(page.locator(".firm-workspace")).toHaveCount(0);
  expect((await page.request.get("/api/documents")).status()).toBe(401);
});
test("assignment proxy preserves CSRF, masking, maximum synthetic upload and long polling", async ({
  page,
}) => {
  await login(page);
  const session = await (
    await page.request.get("/api/workflow/session")
  ).json();
  const headers = {
    Origin: "https://localhost:3300",
    "X-CSRF-Token": session.csrf_token,
  };
  expect(
    (await page.request.post("/api/workflow/notes", { data: {} })).status(),
  ).toBe(403);
  expect(
    (
      await page.request.post("/api/workflow/notes", {
        headers: { ...headers, Origin: "https://evil.example" },
        data: {},
      })
    ).status(),
  ).toBe(403);
  expect(
    await (await page.request.get("/api/documents/D71")).text(),
  ).not.toContain("666-41-2287");
  const content = Buffer.alloc(5 * 1024 * 1024, "b");
  const response = await page.request.post("/api/product/attachments", {
    headers,
    data: {
      area: "business",
      title: "Synthetic assignment transport fixture",
      note: "Synthetic text only",
      filename: "assignment-source.txt",
      media_type: "text/plain",
      content_base64: content.toString("base64"),
      links: [{ kind: "document", id: "D14" }],
    },
  });
  expect(response.status(), await response.text()).toBe(200);
  const uploaded = await response.json();
  expect(uploaded.data.sha256).toBe(
    createHash("sha256").update(content).digest("hex"),
  );
  expect(
    (
      await page.request.get(
        "/api/product/attachments/" + uploaded.id + "/download",
        {
          headers: {
            "X-Sensitive-Access": "reveal",
            "X-Access-Purpose": "Attempt prohibited original",
          },
        },
      )
    ).status(),
  ).toBe(403);
  const first = await (
    await page.request.get("/api/product/changes?wait_seconds=0")
  ).json();
  const started = Date.now();
  const poll = await page.request.get(
    "/api/product/changes?wait_seconds=2&after=" + first.cursor,
  );
  expect(poll.status()).toBe(200);
  expect(Date.now() - started).toBeGreaterThanOrEqual(1500);
  expect(poll.headers()["cache-control"]).toContain("no-store");
  const readiness = await (
    await page.request.get("/api/workflow/readiness")
  ).json();
  expect(readiness.filing_ready).toBe(false);
});
test("assignment rejects incorrect tokens and administrator tax-detail access", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Configured credential").fill("invalid");
  await page
    .getByRole("button", { name: "Start / switch session", exact: true })
    .click();
  await expect(page.locator("p[role=alert]")).toContainText("Session request rejected; check identity");
  expect((await page.request.get("/api/documents")).status()).toBe(401);
  await login(page, "st-05");
  expect(
    (await page.request.get("/api/return-lines?version=v3")).status(),
  ).toBe(403);
});
