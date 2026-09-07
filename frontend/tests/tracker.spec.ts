import { test, expect, Page } from "@playwright/test";

const password = "Unique-browser-pass-853!";
async function register(page: Page, prefix: string) {
  const username = prefix + Date.now() + Math.floor(Math.random() * 10000);
  await page.goto("/register");
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page.getByText("Credit your first salary to start tracking expenses.")).toBeVisible();
  return username;
}
async function salary(page: Page, value: string) {
  await page.getByLabel("Salary amount", { exact: true }).fill(value);
  await page.getByRole("button", { name: "Credit salary", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Salary credited." })).toBeVisible();
  await expect(page.getByLabel("Expense amount", { exact: true })).toBeEnabled();
}
async function expense(page: Page, amount: string, description: string) {
  await page.getByLabel("Expense amount", { exact: true }).fill(amount);
  await page.getByLabel("Description", { exact: true }).fill(description);
  await page.getByRole("button", { name: "Add expense", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Expense added." })).toBeVisible();
  await expect(page.getByText(description, { exact: true })).toBeVisible();
}

test("salary lifecycle, backend validation, confirmations, history and mobile layout", async ({ page }) => {
  await register(page, "flow");
  await expect(page.getByRole("button", { name: "Add expense", exact: true })).toBeDisabled();
  await salary(page, "100");
  await expect(page.getByRole("button", { name: "Credit salary", exact: true })).toBeDisabled();
  await page.getByLabel("Expense amount", { exact: true }).fill("101");
  await page.getByLabel("Description", { exact: true }).fill("too much");
  await page.getByRole("button", { name: "Add expense", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("remaining balance");
  await expense(page, "25", "lunch - at Restaurant");
  await expense(page, "75", "travel - office");
  await expect(page.getByText("Cycle complete. You can now credit your next salary.")).toBeVisible();
  await salary(page, "200");
  await expect(page.getByText("lunch - at Restaurant", { exact: true })).toHaveCount(0);
  await expense(page, "20", "grocery - vegetables");
  await page.getByRole("button", { name: "Delete grocery - vegetables", exact: true }).click();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByText("grocery - vegetables", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Delete grocery - vegetables", exact: true }).click();
  await page.getByRole("button", { name: "Delete expense", exact: true }).click();
  await expect(page.getByText("grocery - vegetables", { exact: true })).toHaveCount(0);
  await expense(page, "25", "lunch - fresh cycle");
  await page.screenshot({ path: "test-results/dashboard-desktop.png", fullPage: true });
  await page.getByRole("link", { name: "History", exact: true }).click();
  const cycles = page.locator(".cycle-section");
  await expect(cycles).toHaveCount(2);
  await expect(cycles.nth(0)).toContainText("175.00");
  await expect(cycles.nth(1)).toContainText("lunch - at Restaurant");
  await cycles.nth(1).getByRole("button", { name: "Delete all expenses", exact: true }).click();
  await expect(page.getByRole("dialog").getByRole("button", { name: "Delete all expenses", exact: true })).toBeDisabled();
  await page.getByLabel("Type DELETE to confirm").fill("DELETE");
  await page.getByRole("dialog").getByRole("button", { name: "Delete all expenses", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(cycles.nth(1)).toContainText("No expenses in this cycle yet.");
  await expect(cycles.nth(0)).toContainText("175.00");
  await expect(cycles.nth(1)).toContainText("historical");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "test-results/history-mobile.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/history");
  await expect(page).toHaveURL(/\/login$/);
});

test("separate browser sessions cannot read or delete another account's data", async ({ browser }) => {
  const aliceContext = await browser.newContext();
  const bobContext = await browser.newContext();
  const alice = await aliceContext.newPage();
  const bob = await bobContext.newPage();
  await register(alice, "alice");
  await salary(alice, "50");
  await expense(alice, "10", "private - Alice only");
  const data = await alice.evaluate(async () => (await fetch("/api/dashboard/")).json());
  const cycleId = data.cycle.id;
  const expenseId = data.recent_expenses[0].id;
  await register(bob, "bob");
  const result = await bob.evaluate(async ({ cycleId, expenseId }) => {
    const csrf = await (await fetch("/api/auth/csrf/")).json();
    const cycle = await fetch(`/api/cycles/${cycleId}/`);
    const deletion = await fetch(`/api/expenses/${expenseId}/`, { method: "DELETE",
      headers: { "X-CSRFToken": csrf.csrfToken } });
    const bulk = await fetch(`/api/cycles/${cycleId}/expenses/`, { method: "DELETE",
      headers: { "X-CSRFToken": csrf.csrfToken } });
    return [cycle.status, deletion.status, bulk.status];
  }, { cycleId, expenseId });
  expect(result).toEqual([404, 404, 404]);
  await alice.reload();
  await expect(alice.getByText("private - Alice only", { exact: true })).toBeVisible();
  await aliceContext.close(); await bobContext.close();
});
