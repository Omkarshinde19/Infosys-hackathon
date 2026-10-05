import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";

// Demo accounts live in config/DEMO_ACCOUNTS.md (never hard-coded here).
function demoPassword(username: string): string {
  const accounts = readFileSync(join(__dirname, "..", "..", "config", "DEMO_ACCOUNTS.md"), "utf8");
  return accounts.match(new RegExp(`\\| \`${username}\` \\| \`([^\`]+)\` \\|`))![1];
}

test("demo: sign in, cut a fibre, watch NetHeal heal it, open the incident", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill("operator");
  await page.getByLabel("Password").fill(demoPassword("operator"));
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // The detector learns the healthy baseline for 30 s after the engine starts.
  await expect(page.getByText("All clear")).toBeVisible({ timeout: 90_000 });

  await page.getByRole("button", { name: "Hostel fibre cut" }).click();
  await expect(page.getByText(/^Healed: traffic is back to normal/)).toBeVisible({ timeout: 60_000 });

  await page.getByRole("link", { name: /report/ }).click();
  await expect(page).toHaveURL(/\/dashboard\/incidents\/.+/);
  await expect(page.getByText(/link down|link failure/i).first()).toBeVisible();
});
