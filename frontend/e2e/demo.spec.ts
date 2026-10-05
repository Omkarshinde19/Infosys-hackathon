import { expect, test } from "@playwright/test";
import { blockInternet, signIn } from "./helpers";

test("demo: sign in, cut a fibre, watch NetHeal heal it, open the incident (no internet)", async ({ page }) => {
  const blocked = await blockInternet(page);
  await signIn(page, "operator");

  // Start from a healthy network (after a cold start the detector learns for 30 s first).
  await page.getByRole("button", { name: "Reset network" }).click();
  await expect(page.getByText("All clear")).toBeVisible({ timeout: 90_000 });

  await page.getByRole("button", { name: "Hostel fibre cut" }).click();
  await expect(page.getByText(/^Healed: traffic is back to normal/)).toBeVisible({ timeout: 60_000 });

  await page.getByRole("link", { name: /^Incident .* report$/ }).click();
  await expect(page).toHaveURL(/\/dashboard\/incidents\/.+/);
  await expect(page.getByText(/link down|link failure/i).first()).toBeVisible();
  expect(blocked).toEqual([]);
});

test("demo script drills: gray failure heals, core router meltdown escalates (no internet)", async ({ page }) => {
  const blocked = await blockInternet(page);
  await signIn(page, "operator");
  await page.getByRole("button", { name: "Reset network" }).click();
  await expect(page.getByText("All clear")).toBeVisible({ timeout: 90_000 });

  await page.getByRole("button", { name: "Silent packet loss at the CS Lab" }).click();
  await expect(page.getByText(/^Healed: traffic is back to normal/)).toBeVisible({ timeout: 60_000 });

  await page.getByRole("button", { name: "Reset network" }).click();
  await expect(page.getByText("All clear")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: /Core router meltdown/ }).click();
  await expect(page.getByText(/^Escalated/)).toBeVisible({ timeout: 60_000 });
  expect(blocked).toEqual([]);
});
