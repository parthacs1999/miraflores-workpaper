
import { test, expect } from "@playwright/test";

test("review finding opens corresponding calculation evidence", async ({
    page,
}) => {
    await page.goto(process.env.E2E_BASE_URL ?? "http://localhost:3000");

    await page.getByLabel("Return version").selectOption("v3");

    await page.getByRole("button", {
        name: "Review Findings",
    }).click();

    await expect(
        page.getByRole("heading", {
            name: "CPA Review Queue",
        })
    ).toBeVisible();

    const finding = page
        .getByRole("button")
        .filter({
            hasText: "F1040.12:",
        })
        .first();

    await expect(finding).toBeVisible();
    await finding.click();

    const inspector = page
        .getByRole("heading", {
            name: "Evidence Inspector",
        })
        .locator("..")
        .locator("..");

    await expect(
        inspector.getByText("F1040.12", {
            exact: true,
        }).first()
    ).toBeVisible();
});
