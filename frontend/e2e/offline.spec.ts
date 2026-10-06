import { expect, test } from "@playwright/test";
import { blockInternet, signIn } from "./helpers";

const PAGES = [
  ["/dashboard", "Control Room"],
  ["/dashboard/copilot", "How can I help you today?"],
  ["/dashboard/whatif", "What If"],
  ["/dashboard/incidents", "Incidents"],
  ["/dashboard/approvals", "Approvals"],
  ["/dashboard/insights", "Performance"],
  ["/dashboard/evaluation", "Evaluation"],
  ["/dashboard/audit", "Audit"],
  ["/dashboard/settings", "Settings"],
] as const;

test("every page works without internet and without errors", async ({ page }) => {
  const blocked = await blockInternet(page);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`${new URL(page.url()).pathname}: ${e.message.slice(0, 60)}`));

  await page.goto("/");
  await expect(page.locator("h1").first()).toBeVisible();
  await signIn(page, "admin");
  for (const [path, text] of PAGES) {
    await page.goto(path);
    await expect(page.getByText(text).first(), path).toBeVisible({ timeout: 15_000 });
  }
  expect(blocked, "requests that need the internet").toEqual([]);
  expect(errors, "uncaught page errors").toEqual([]);
});
