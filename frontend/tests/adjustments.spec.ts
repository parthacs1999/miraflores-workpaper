import { clickAction } from "./ui-helpers";
import { test, expect } from "@playwright/test";
const API = process.env.E2E_API_URL ?? "http://localhost:8000";

// This primary scenario proves persistence, partner policy, API controls and reversal.
test("business receipts adjustment has independent partner approval and audited reversal", async ({
  page,
  request,
}) => {
  const baseline = await (
    await request.get(`${API}/api/return-lines?version=v3`)
  ).json();
  await page.goto("/");
  await clickAction(page, async () =>
    page.getByRole("button", { name: "Tax Adjustments", exact: true }).click(),
  );
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Load business receipts example" })
      .click(),
  );
  await expect(page.getByLabel("Proposed value", { exact: true })).toHaveValue(
    "151300.00",
  );
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Save adjustment draft", exact: true })
      .click(),
  );
  await expect(page.getByTestId("adjustment-state")).toHaveText("draft");
  await expect(page.getByTestId("approved-summary")).toContainText(
    "0 currently approved adjustments",
  );
  await expect(
    page.getByText("Engine 163700.00 → proposed 151300.00 · change -12400.00"),
  ).toBeVisible();
  await page
    .getByLabel("Adjustment action note")
    .fill("Reconciled books and Paywell receipts to D15.");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Submit adjustment", exact: true })
      .click(),
  );
  await expect(page.getByTestId("adjustment-state")).toHaveText("submitted");
  await expect(
    page.getByRole("button", { name: "Approve adjustment", exact: true }),
  ).toBeDisabled();
  const list = await (await request.get(`${API}/api/adjustments`)).json();
  const item = list.adjustments.find(
    (a: { state: string }) => a.state === "submitted",
  );
  expect(item).toBeDefined();
  const denied = await request.post(
    `${API}/api/adjustments/${item.id}/actions`,
    {
      data: {
        actor_id: "st-02",
        expected_sequence: item.sequence,
        action: "approve",
        note: "Attempt reviewer approval",
      },
    },
  );
  expect(denied.status()).toBe(403);
  expect((await denied.json()).detail).toContain("Partner approval required");
  await page.getByLabel("Adjustment staff").selectOption("st-02");
  await page
    .getByLabel("Adjustment action note")
    .fill("Reviewer checked reconciliation.");
  await expect(
    page.getByRole("button", { name: "Approve adjustment", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Adjustment staff").selectOption("st-03");
  await page
    .getByLabel("Adjustment action note")
    .fill("Independent partner approved duplicated receipt correction.");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Approve adjustment", exact: true })
      .click(),
  );
  await expect(page.getByTestId("adjustment-state")).toHaveText("approved");
  await expect(page.getByTestId("federal-effect")).toHaveText("-4402.00");
  await expect(page.getByTestId("california-effect")).toHaveText("-384.40");
  await expect(page.getByTestId("adjustment-history")).toContainText(
    "approve · st-03 (partner)",
  );
  await page.reload();
  await clickAction(page, async () =>
    page.getByRole("button", { name: "Tax Adjustments", exact: true }).click(),
  );
  await clickAction(page, async () =>
    page.getByRole("button", { name: new RegExp(item.id) }).click(),
  );
  await expect(page.getByTestId("adjustment-state")).toHaveText("approved");
  await expect(page.getByTestId("adjustment-history")).toContainText(
    "Independent partner approved duplicated receipt correction.",
  );
  await page.getByLabel("Adjustment staff").selectOption("st-03");
  await page
    .getByLabel("Adjustment action note")
    .fill("Reverse demonstration adjustment; retain full audit trail.");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Reverse adjustment", exact: true })
      .click(),
  );
  await expect(page.getByTestId("adjustment-state")).toHaveText("reversed");
  await expect(page.getByTestId("federal-effect")).toHaveText("0.00");
  await expect(page.getByTestId("adjustment-history")).toContainText(
    "reverse · st-03 (partner)",
  );
  const after = await (
    await request.get(`${API}/api/return-lines?version=v3`)
  ).json();
  expect(after).toEqual(baseline);
});

test("rejected adjustment can be revised and unsupported methods block approval", async ({
  page,
  request,
}) => {
  const meta = await (
    await request.get(`${API}/api/adjustment-metadata`)
  ).json();
  const created = await request.post(`${API}/api/adjustments`, {
    data: {
      ...meta.demo,
      target: "F8606.18",
      proposed_value: "1000",
      actor_id: "st-01",
    },
  });
  expect(created.status()).toBe(201);
  const item = await created.json();
  await page.goto("/");
  await clickAction(page, async () =>
    page.getByRole("button", { name: "Tax Adjustments", exact: true }).click(),
  );
  await clickAction(page, async () =>
    page.getByRole("button", { name: new RegExp(item.id) }).click(),
  );
  await expect(
    page.getByText("Manual review required. Approval blocked.", {
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByLabel("Adjustment action note")
    .fill("Submit for review of missing calculation method.");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Submit adjustment", exact: true })
      .click(),
  );
  await page.getByLabel("Adjustment staff").selectOption("st-03");
  await page
    .getByLabel("Adjustment action note")
    .fill("Unsupported computation; revise target and evidence.");
  await expect(
    page.getByRole("button", { name: "Approve adjustment", exact: true }),
  ).toBeDisabled();
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Reject adjustment", exact: true })
      .click(),
  );
  await expect(page.getByTestId("adjustment-state")).toHaveText("rejected");
  await page.getByLabel("Adjustment staff").selectOption("st-01");
  await clickAction(page, async () =>
    page.getByRole("button", { name: "Edit revision", exact: true }).click(),
  );
  await page.getByLabel("Proposed value", { exact: true }).fill("2000");
  await clickAction(page, async () =>
    page.getByRole("button", { name: "Save revision", exact: true }).click(),
  );
  await expect(page.getByTestId("adjustment-state")).toHaveText("draft");
  await expect(page.getByTestId("adjustment-history")).toContainText(
    "revised · st-01 (preparer) · revision 2",
  );
});

test("overlap is blocked and supersession removes the previous approved contribution", async ({
  page,
  request,
}) => {
  const meta = await (
    await request.get(`${API}/api/adjustment-metadata`)
  ).json();
  const create = async () => {
    const response = await request.post(`${API}/api/adjustments`, {
      data: { ...meta.demo, actor_id: "st-01" },
    });
    expect(response.status()).toBe(201);
    return response.json();
  };
  const first = await create();
  const submit = await request.post(
    `${API}/api/adjustments/${first.id}/actions`,
    {
      data: {
        actor_id: "st-01",
        expected_sequence: 1,
        action: "submit",
        note: "Submitted reconciliation",
      },
    },
  );
  expect(submit.ok()).toBeTruthy();
  const second = await create();
  await page.goto("/");
  await clickAction(page, async () =>
    page.getByRole("button", { name: "Tax Adjustments", exact: true }).click(),
  );
  await clickAction(page, async () =>
    page.getByRole("button", { name: new RegExp(second.id) }).click(),
  );
  await page
    .getByLabel("Adjustment action note")
    .fill("Attempt overlapping correction.");
  await expect(page.getByText(/Conflicting adjustments:/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Submit adjustment", exact: true }),
  ).toBeDisabled();
  const approved = await request.post(
    `${API}/api/adjustments/${first.id}/actions`,
    {
      data: {
        actor_id: "st-03",
        expected_sequence: 2,
        action: "approve",
        note: "Independent partner approval",
      },
    },
  );
  expect(approved.ok()).toBeTruthy();
  await clickAction(page, async () =>
    page.getByRole("button", { name: new RegExp(first.id) }).click(),
  );
  await expect(page.getByTestId("adjustment-state")).toHaveText("approved");
  await page.getByLabel("Adjustment staff").selectOption("st-03");
  await page
    .getByLabel("Adjustment action note")
    .fill("Replace approved correction with a fresh draft.");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Supersede with new draft", exact: true })
      .click(),
  );
  await expect(page.getByTestId("adjustment-state")).toHaveText("draft");
  await expect(page.getByTestId("federal-effect")).toHaveText("0.00");
  const detail = await (
    await request.get(`${API}/api/adjustments/${first.id}`)
  ).json();
  expect(detail.state).toBe("superseded");
  await page.getByLabel("Adjustment staff").selectOption("st-01");
  await page
    .getByLabel("Adjustment action note")
    .fill("Submit replacement for independent approval.");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Submit adjustment", exact: true })
      .click(),
  );
  await page.getByLabel("Adjustment staff").selectOption("st-03");
  await page
    .getByLabel("Adjustment action note")
    .fill("Fresh partner approval for replacement.");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Approve adjustment", exact: true })
      .click(),
  );
  await expect(page.getByTestId("federal-effect")).toHaveText("-4402.00");
  await page
    .getByLabel("Adjustment action note")
    .fill("Reverse final test correction.");
  await clickAction(page, async () =>
    page
      .getByRole("button", { name: "Reverse adjustment", exact: true })
      .click(),
  );
  await expect(page.getByTestId("federal-effect")).toHaveText("0.00");
});
