
import { test, expect } from "@playwright/test";

test("MiraFlores workpaper end-to-end", async ({ page }) => {
    await page.goto("http://localhost:3000");

    await expect(
        page.getByRole("heading", {
            name: "Okafor–Lindqvist",
        })
    ).toBeVisible();

    await expect(
        page.getByText("Source documents", {
            exact: true,
        })
    ).toBeVisible();

    await expect(
        page.getByText("Extracted values", {
            exact: true,
        })
    ).toBeVisible();

    await expect(
        page.getByText("74", {
            exact: true,
        })
    ).toBeVisible();

    await expect(
        page.getByText("3012", {
            exact: true,
        })
    ).toBeVisible();

    const searchInput = page.getByPlaceholder(
        "Search by form, line, or description..."
    );

    await expect(searchInput).toBeVisible();

    await searchInput.fill("F1040.1a");

    const wagesLine = page.getByRole("button", {
        name: /F1040\.1a/,
    });

    await expect(wagesLine).toBeVisible();
    await wagesLine.click();

    await expect(
        page.getByRole("heading", {
            name: "Evidence Inspector",
        })
    ).toBeVisible();

    await expect(
        page.getByText("ev-0016", {
            exact: true,
        }).first()
    ).toBeVisible();

    await page.getByRole("button", {
        name: "Document Explorer",
    }).click();

    await expect(
        page.getByRole("heading", {
            name: "Source Documents",
            exact: true,
        })
    ).toBeVisible();

    const documentSearch = page.getByPlaceholder(
        "Search documents..."
    );

    await expect(documentSearch).toBeVisible();
    await documentSearch.fill("D09");

    const documentButton = page.getByRole("button", {
        name: /^D09\s/,
    });

    await expect(documentButton).toBeVisible();
    await documentButton.click();

    await expect(
        page.getByText("PAGE 1", {
            exact: true,
        }).first()
    ).toBeVisible();

    await page.getByRole("button", {
        name: "Review Findings",
    }).click();

    await expect(
        page.getByRole("heading", {
            name: "Independent Validation",
        })
    ).toBeVisible();

    await expect(
        page.getByRole("heading", {
            name: "CPA Review Queue",
        })
    ).toBeVisible();

    await expect(
        page.getByLabel("Demo role")
    ).toBeVisible();

    await expect(
        page.getByLabel("Reviewer name")
    ).toBeVisible();

    await page.getByLabel("Demo role").selectOption("preparer");

    await expect(
        page.getByLabel("Demo role")
    ).toHaveValue("preparer");

    await page.getByLabel("Demo role").selectOption("reviewer");

    await expect(
        page.getByLabel("Demo role")
    ).toHaveValue("reviewer");

    await page.getByLabel("Return version").selectOption("v2");

    await expect(
        page.getByRole("heading", {
            name: "CPA Review Queue",
        })
    ).toBeVisible();

    await page.getByRole("button", {
        name: "Tax Return",
    }).click();

    await expect(
        page.getByRole("heading", {
            name: "Tax Return Lines",
        })
    ).toBeVisible();

    await expect(
        page.getByPlaceholder(
            "Search by form, line, or description..."
        )
    ).toBeVisible();

    await page.getByLabel("Return version").selectOption("v3");

    await expect(
        page.getByRole("heading", {
            name: "Tax Return Lines",
        })
    ).toBeVisible();

    await expect(
        page.getByLabel("Return version")
    ).toHaveValue("v3");
});
