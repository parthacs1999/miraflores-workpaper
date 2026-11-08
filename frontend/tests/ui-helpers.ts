import { expect, type Page } from "@playwright/test";
const groups: Record<string, string> = {
  dashboard: "Overview",
  readiness: "Overview",
  tasks: "Overview",
  return: "Tax Workpaper",
  documents: "Tax Workpaper",
  reconciliation: "Tax Workpaper",
  adjustments: "Tax Workpaper",
  diligence: "Review & Collaboration",
  notes: "Review & Collaboration",
  signoffs: "Review & Collaboration",
  collaboration: "Review & Collaboration",
  attachments: "Review & Collaboration",
  bulk: "Review & Collaboration",
  version: "Analysis",
  whatif: "Analysis",
  replay: "Analysis",
  impact: "Analysis",
  finalization: "Filing",
  filing: "Filing",
  extensions: "Filing",
  authorization: "Filing",
  amendments: "Filing",
  notices: "Filing",
  carryovers: "Filing",
  assignments: "Firm",
  operations: "Firm",
  security: "Firm",
};
export async function navigate(page: Page, view: string) {
  if (
    view === "bulk" &&
    (await page.getByTestId("current-session").textContent())?.includes(
      "firm_administrator",
    )
  ) {
    await navigate(page, "operations");
    await page
      .getByRole("navigation", { name: "Collaboration sections" })
      .getByRole("button", { name: "Bulk Actions", exact: true })
      .click();
    return;
  }
  const activeDrawer = page.getByRole("dialog", {
    name: "Activity & notifications",
    exact: true,
  });
  if (await activeDrawer.isVisible())
    await activeDrawer
      .getByRole("button", {
        name: "Close Activity & notifications",
        exact: true,
      })
      .click();
  const mobile = page.getByRole("button", {
    name: "Open navigation",
    exact: true,
  });
  if (await mobile.isVisible()) await mobile.click();
  await expect(page.locator(".firm-workspace")).toHaveAttribute(
    "data-loaded",
    "true",
  );
  const item = page.locator(`.sidebar-link[data-view="${view}"]`);
  if (!(await item.isVisible())) {
    const group = page.getByRole("button", { name: groups[view], exact: true });
    if ((await group.getAttribute("aria-expanded")) === "false")
      await group.click();
  }
  await item.click();
  await expect(page.locator("#main-content")).toBeVisible();
}
export async function openSessionMenu(page: Page) {
  if (!(await page.getByLabel("Session staff", { exact: true }).isVisible())) {
    const activity = page.getByRole("dialog", {
      name: "Activity & notifications",
      exact: true,
    });
    if (await activity.isVisible())
      await page
        .getByRole("button", {
          name: "Close Activity & notifications",
          exact: true,
        })
        .click();
    await page.getByLabel("Switch staff session", { exact: true }).click();
  }
}
/** Accept the actual visible confirmation dialog; assertions and server checks remain unchanged. */
export async function clickAction(page: Page, click: () => Promise<unknown>) {
  await click();
  const dialog = page.getByRole("alertdialog", {
    name: "Confirm workpaper action",
    exact: true,
  });
  await dialog.waitFor({ state: "visible", timeout: 250 }).catch(() => {});
  if (await dialog.isVisible())
    await dialog
      .getByRole("button", { name: "Confirm action", exact: true })
      .click();
}
