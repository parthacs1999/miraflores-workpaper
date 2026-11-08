
import { test, expect } from "@playwright/test";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";

type Finding = {
    id: string;
    title: string;
    status: string;
    review_note: string;
};

type ReviewsResponse = {
    findings: Finding[];
};

test("CPA review decisions persist after refresh", async ({
    page,
    request,
}) => {
    const response = await request.get(
        `${API}/api/reviews?version=v3`
    );

    expect(response.ok()).toBeTruthy();

    const data = (await response.json()) as ReviewsResponse;

    test.skip(
        data.findings.length === 0,
        "No real validation findings are available in v3"
    );

    const finding = data.findings[0];
    const uniqueNote = `Playwright verification ${Date.now()}`;

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

    await page.getByLabel("Demo role").selectOption("reviewer");

    await page.getByLabel("Reviewer name").fill(
        "Playwright Reviewer"
    );

    const findingButton = page
        .getByRole("button")
        .filter({ hasText: finding.title })
        .first();

    await expect(findingButton).toBeVisible();
    await findingButton.click();

    await expect(
        page.getByLabel("Review status")
    ).toBeVisible();

    await page.getByLabel("Review status").selectOption(
        "in_review"
    );

    await page.getByLabel("Reviewer note").fill(uniqueNote);

    await page.getByRole("button", {
        name: "Save Review",
    }).click();

    await expect(
        page.getByRole("status").getByText(
            "Review saved successfully."
        )
    ).toBeVisible();

    const savedResponse = await request.get(
        `${API}/api/reviews?version=v3`
    );

    expect(savedResponse.ok()).toBeTruthy();

    const savedData =
        (await savedResponse.json()) as ReviewsResponse;

    const savedFinding = savedData.findings.find(
        (item) => item.id === finding.id
    );

    expect(savedFinding).toBeDefined();
    expect(savedFinding?.status).toBe("in_review");
    expect(savedFinding?.review_note).toBe(uniqueNote);

    await page.reload();

    await page.getByRole("button", {
        name: "Review Findings",
    }).click();

    await expect(
        page.getByRole("heading", {
            name: "CPA Review Queue",
        })
    ).toBeVisible();

    const findingAfterReload = page
        .getByRole("button")
        .filter({ hasText: finding.title })
        .first();

    await expect(findingAfterReload).toBeVisible();
    await findingAfterReload.click();

    await expect(
        page.getByLabel("Review status")
    ).toHaveValue("in_review");

    await expect(
        page.getByLabel("Reviewer note")
    ).toHaveValue(uniqueNote);

    await expect(
        page.getByText(uniqueNote, {
            exact: true,
        }).last()
    ).toBeVisible();

    await page.getByLabel("Demo role").selectOption(
        "preparer"
    );

    await expect(
        page.getByLabel("Review status").locator(
            'option[value="resolved"]'
        )
    ).toHaveCount(0);
});
