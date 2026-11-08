import { clickAction } from "./ui-helpers";

import { test, expect } from "@playwright/test";

test("CPA can inspect extracted evidence against printed source", async ({
  page,
}) => {
  await page.goto(process.env.E2E_BASE_URL ?? "http://localhost:3000");

  await page.getByLabel("Return version").selectOption("v3");

  const search = page.getByPlaceholder(
    "Search by form, line, or description...",
  );

  await expect(search).toBeVisible();
  await search.fill("F1040.1a");

  const wagesLine = page.getByRole("button", {
    name: /F1040\.1a/,
  });

  await expect(wagesLine).toBeVisible();
  await clickAction(page, async () => wagesLine.click());

  const evidence = page.getByRole("button", {
    name: "ev-0016",
    exact: true,
  });

  await expect(evidence).toBeVisible();
  await clickAction(page, async () => evidence.click());

  const verification = page.getByTestId("source-verification");

  await expect(verification).toBeVisible();

  await expect(
    verification.getByText("ev-0016", {
      exact: true,
    }),
  ).toBeVisible();

  await expect(
    verification.getByText("Extracted value", {
      exact: true,
    }),
  ).toBeVisible();

  await expect(
    verification.getByText("Simulated printed source"),
  ).toBeVisible();

  await expect(page.getByTestId("verification-status")).toHaveText(
    /Supported|Unverified|Missing Source/,
  );

  const status = await page.getByTestId("verification-status").innerText();

  if (status.trim() === "Supported") {
    await expect(page.getByTestId("source-highlight")).toBeVisible();
  }

  await clickAction(page, async () =>
    page
      .getByRole("button", {
        name: "Back to lineage",
      })
      .click(),
  );

  await expect(
    page.getByRole("button", {
      name: "ev-0016",
      exact: true,
    }),
  ).toBeVisible();
});
