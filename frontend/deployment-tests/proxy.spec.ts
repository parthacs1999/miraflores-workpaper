import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createHash } from "node:crypto";
const ORIGIN = "https://localhost:3300";
function tokens(): Record<string, string> {
  return JSON.parse(
    readFileSync(join(process.env.PROXY_E2E_DIR!, "tokens.json"), "utf8"),
  );
}
async function login(page: Page, id = "st-01") {
  const assertion = tokens()[id];
  await page
    .context()
    .setExtraHTTPHeaders({ "Cf-Access-Jwt-Assertion": assertion });
  const pending = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/workflow/session") &&
      r.request().method() === "GET",
  );
  await page.goto("/");
  const session = await (await pending).json();
  await expect(page.getByTestId("current-session")).toContainText(id);
  await expect(page.locator(".firm-workspace")).toHaveAttribute(
    "data-loaded",
    "true",
  );
  return { assertion, csrf: session.csrf_token };
}
function headers(s: { assertion: string; csrf: string }) {
  return {
    "Cf-Access-Jwt-Assertion": s.assertion,
    Origin: ORIGIN,
    "X-CSRF-Token": s.csrf,
  };
}

test("actual rewrite blocks anonymous, forged identity and invalid sessions", async ({
  page,
}) => {
  expect((await page.request.get("/api/overview")).status()).toBe(401);
  expect(
    (
      await page.request.get("/api/workflow/session/staff", {
        headers: { "Cf-Access-Jwt-Assertion": "forged", "X-Staff-ID": "st-03" },
      })
    ).status(),
  ).toBe(401);
  await page
    .context()
    .addCookies([
      {
        name: "mf_session",
        value: "invalid",
        url: ORIGIN,
        httpOnly: true,
        secure: true,
        sameSite: "Strict",
      },
    ]);
  expect(
    (
      await page.request.get("/api/overview", {
        headers: { "Cf-Access-Jwt-Assertion": tokens()["st-01"] },
      })
    ).status(),
  ).toBe(401);
});

test("signed gateway login crosses the real HTTPS Next rewrite with a secure bound cookie", async ({
  page,
}) => {
  const s = await login(page);
  const cookies = await page.context().cookies();
  const cookie = cookies.find((c) => c.name === "mf_session");
  expect(cookie).toBeTruthy();
  expect(cookie!.secure && cookie!.httpOnly).toBe(true);
  expect(cookie!.sameSite).toBe("Strict");
  expect(cookie!.domain).toBe("localhost");
  await page.getByLabel("Switch staff session", { exact: true }).click();
  await expect(
    page.getByLabel("Session staff", { exact: true }),
  ).toBeDisabled();
  await expect(page.getByLabel("Session staff").locator("option")).toHaveCount(
    1,
  );
  expect(
    (
      await page.request.post("/api/workflow/session", {
        headers: headers(s),
        data: { staff_id: "st-03" },
      })
    ).status(),
  ).toBe(403);
  expect(
    (
      await page.request.get("/api/overview", {
        headers: { "Cf-Access-Jwt-Assertion": tokens()["st-02"] },
      })
    ).status(),
  ).toBe(401);
});

test("rewrite preserves CSRF, strict origins, masking and error sanitization", async ({
  page,
}) => {
  const s = await login(page);
  expect(
    (
      await page.request.post("/api/workflow/notes", {
        headers: { ...headers(s), "X-CSRF-Token": "" },
        data: {},
      })
    ).status(),
  ).toBe(403);
  expect(
    (
      await page.request.post("/api/workflow/notes", {
        headers: { ...headers(s), Origin: "https://evil.example" },
        data: {},
      })
    ).status(),
  ).toBe(403);
  const source = await page.request.get("/api/documents/D71");
  expect(source.status()).toBe(200);
  expect(await source.text()).not.toContain("666-41-2287");
  expect(source.headers()["cache-control"]).toContain("no-store");
  expect(source.headers()["x-content-type-options"]).toBe("nosniff");
  const failure = await page.request.post("/api/workflow/notes", {
    headers: headers(s),
    data: { title: { private: "do-not-echo-private-content" } },
  });
  expect(failure.status()).toBe(422);
  expect(await failure.text()).not.toContain("do-not-echo-private-content");
});

test("existing 5 MiB upload and audited original download survive proxy payload handling", async ({
  page,
}) => {
  const s = await login(page);
  const content = Buffer.alloc(5 * 1024 * 1024, "a");
  const digest = createHash("sha256").update(content).digest("hex");
  const response = await page.request.post("/api/product/attachments", {
    headers: headers(s),
    data: {
      area: "business",
      title: "Isolated maximum-size transport fixture",
      note: "Transport test only, not extracted evidence",
      filename: "maximum-source.txt",
      media_type: "text/plain",
      content_base64: content.toString("base64"),
      links: [{ kind: "document", id: "D14" }],
    },
  });
  expect(response.status(), await response.text()).toBe(200);
  const attachment = await response.json();
  expect(attachment.data.sha256).toBe(digest);
  expect(attachment.data.size).toBe(content.length);
  expect(
    (
      await page.request.get(
        "/api/product/attachments/" + attachment.id + "/download",
      )
    ).status(),
  ).toBe(403);
  const reviewer = await login(page, "st-02");
  const original = await page.request.get(
    "/api/product/attachments/" + attachment.id + "/download",
    {
      headers: {
        ...headers(reviewer),
        "X-Sensitive-Access": "reveal",
        "X-Access-Purpose": "Inspect maximum-size transport fixture original",
      },
    },
  );
  expect(original.status()).toBe(200);
  const downloaded = await original.json();
  expect(
    createHash("sha256")
      .update(Buffer.from(downloaded.content_base64, "base64"))
      .digest("hex"),
  ).toBe(digest);
  const partner = await login(page, "st-03");
  const audit = await page.request.get("/api/workflow/access-history", {
    headers: headers(partner),
  });
  expect(await audit.text()).toContain(
    "Inspect maximum-size transport fixture original",
  );
});

test("bounded long polling and no-store headers survive the native rewrite", async ({
  page,
}) => {
  const s = await login(page);
  const first = await (
    await page.request.get("/api/product/changes?wait_seconds=0", {
      headers: headers(s),
    })
  ).json();
  const start = Date.now();
  const next = await page.request.get(
    "/api/product/changes?wait_seconds=2&after=" + first.cursor,
    { headers: headers(s) },
  );
  expect(next.status()).toBe(200);
  expect(Date.now() - start).toBeGreaterThanOrEqual(1500);
  expect(next.headers()["cache-control"]).toContain("no-store");
  expect((await next.json()).events).toEqual([]);
});

test("administrator is authenticated but cannot enter tax detail and real packet remains blocked", async ({
  page,
}) => {
  await login(page, "st-05");
  expect(
    (await page.request.get("/api/return-lines?version=v3")).status(),
  ).toBe(403);
  expect(
    (
      await page.request.get("/api/product/attachments/missing/download")
    ).status(),
  ).toBe(403);
  await login(page, "st-01");
  const readiness = await (
    await page.request.get("/api/workflow/readiness")
  ).json();
  expect(readiness.filing_ready).toBe(false);
  expect(readiness.blockers.map((b: { code: string }) => b.code)).toContain(
    "FINAL_RETURN_AND_CLIENT_AUTHORIZATION_UNVERIFIED",
  );
});

test("browser expiry clears rendered protected workpaper state without waiting for another poll", async ({
  page,
}) => {
  await login(page);
  await page.route("**/api/workflow/session", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({
      response,
      json: { ...body, expires_at: new Date(Date.now() + 1500).toISOString() },
    });
  });
  await page.reload();
  await expect(page.getByTestId("current-session")).toContainText("st-01");
  await expect(
    page.getByText(
      "Session expired. Reload to reauthenticate through the configured session provider.",
    ),
  ).toBeVisible();
  await expect(page.locator(".firm-workspace")).toHaveCount(0);
});
