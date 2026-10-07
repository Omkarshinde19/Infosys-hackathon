import { expect, test, type Page } from "@playwright/test";
import { IGNORED, signIn } from "./helpers";

// Every user flow, per role, failing on any console error, exception or server error.
// ./netheal ui-check (AUDIT=1); drives the live network, so it runs after the page audit.
test.skip(!process.env.AUDIT, "only for ./netheal ui-check");
test.setTimeout(420_000);

function watch(page: Page): string[] {
  const errors: string[] = [];
  const add = (e: string) => IGNORED.some((re) => re.test(e)) || errors.push(`${new URL(page.url()).pathname}: ${e.slice(0, 200)}`);
  page.on("console", (m) => m.type() === "error" && add(m.text()));
  page.on("pageerror", (e) => add(`exception ${e.message}`));
  page.on("response", (r) => r.status() >= 500 && add(`${r.status()} ${new URL(r.url()).pathname}`));
  return errors;
}

async function healthy(page: Page) {
  await page.goto("/dashboard");
  await page.getByRole("button", { name: "Reset network" }).click();
  await expect(page.getByText("All clear")).toBeVisible({ timeout: 90_000 });
}

test("signed out and viewer: can watch, cannot act", async ({ page }) => {
  const errors = watch(page);
  await page.goto("/dashboard");
  await expect(page.getByText("Sign in to take actions")).toBeVisible();
  await expect(page.getByRole("button", { name: "Inject fault" })).toBeDisabled();
  await signIn(page, "viewer");
  await expect(page.getByRole("button", { name: "Inject fault" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Reset network" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Hostel fibre cut" })).toBeDisabled();
  await page.goto("/dashboard/approvals");
  await expect(page.getByText("Only an admin can change the comfort level.")).toBeVisible();
  await page.goto("/dashboard/settings");
  await expect(page.getByRole("button", { name: /Emulated/ })).toBeDisabled();
  expect(errors).toEqual([]);
});

test("operator: theme, 3D, custom fault, what-if, report, assistant", async ({ page }) => {
  const errors = watch(page);
  await signIn(page, "operator");
  await healthy(page);

  const before = await page.locator("html").getAttribute("data-theme");
  await page.getByRole("button", { name: /Switch to (light|dark) theme/ }).first().click();
  await expect(page.locator("html")).not.toHaveAttribute("data-theme", before!);
  await page.getByRole("button", { name: /Switch to (light|dark) theme/ }).first().click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", before!);

  await page.getByRole("button", { name: "3d", exact: true }).click();
  await expect(page.locator("#network canvas")).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: "2d", exact: true }).click();

  await page.getByRole("button", { name: /Gray failure/ }).first().click();
  await page.getByRole("button", { name: "Inject fault" }).click();
  await expect(page.getByText("All clear")).toBeHidden({ timeout: 30_000 });
  await page.getByRole("button", { name: "Reset network" }).click();

  await page.goto("/dashboard/whatif");
  await page.getByRole("button", { name: "Simulate on the twin" }).click();
  await expect(page.getByRole("button", { name: "Simulate on the twin" })).toBeEnabled({ timeout: 60_000 });
  await expect(page.locator("p.glass.text-critical")).toHaveCount(0); // the error box, not "Blocked:" reasons

  await page.goto("/dashboard/incidents");
  await page.locator("main a[href^='/dashboard/incidents/']").first().click();
  await page.getByRole("button", { name: /Generate report|Regenerate/ }).first().click();
  await expect(page.getByText(/Written by|own template/)).toBeVisible({ timeout: 60_000 });
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: /\.md/ }).click();
  expect((await download).suggestedFilename()).toMatch(/^netheal-incident-.+\.md$/);

  await page.goto("/dashboard/copilot");
  await expect(async () => {
    await page.getByPlaceholder(/Ask about the network/).fill("Is the network healthy right now?");
    await expect(page.getByLabel("Send")).toBeEnabled({ timeout: 1000 });
  }).toPass();
  await page.getByLabel("Send").click();
  await expect(page.getByText(/evidence cited/)).toBeVisible({ timeout: 150_000 });
  expect(errors).toEqual([]);
});

test("admin: approve a fix at comfort level 2, settings, sign out", async ({ page }) => {
  const errors = watch(page);
  await signIn(page, "admin");
  await healthy(page);
  await page.goto("/dashboard/approvals");
  await page.getByRole("button", { name: /Level 2/ }).click();
  try {
    await page.goto("/dashboard");
    await page.getByRole("button", { name: "Hostel fibre cut" }).click();
    await page.goto("/dashboard/approvals");
    await page.getByRole("button", { name: /Approve/ }).click({ timeout: 60_000 });
    await expect(page.getByText("Nothing is waiting.")).toBeVisible({ timeout: 30_000 });
  } finally {
    await page.goto("/dashboard/approvals");
    await page.getByRole("button", { name: /Level 4/ }).click();
  }
  await page.goto("/dashboard/settings");
  await expect(page.getByRole("button", { name: /Simulated/ })).toBeEnabled();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByText("Sign in to take actions")).toBeVisible();
  expect(errors).toEqual([]);
});

test("in-app navigation: every sidebar page from the live dashboard and back", async ({ page }) => {
  // Leaving the dashboard unmounts the 3D map; that used to throw and could leave the URL behind.
  const errors = watch(page);
  await page.goto("/dashboard");
  await page.getByRole("button", { name: "3d", exact: true }).click();
  await expect(page.locator("#network canvas")).toBeVisible({ timeout: 15_000 });
  for (const href of ["/dashboard/copilot", "/dashboard/whatif", "/dashboard/incidents", "/dashboard/approvals",
                      "/dashboard/insights", "/dashboard/evaluation", "/dashboard/audit", "/dashboard/settings"]) {
    await page.locator(`aside nav a[href="${href}"]`).click();
    await expect(page).toHaveURL(new RegExp(`${href}$`), { timeout: 15_000 });
    await page.locator("aside nav a[href^='/dashboard#']").first().click();
    await expect(page).toHaveURL(/\/dashboard(#.*)?$/, { timeout: 15_000 });
    await page.getByRole("button", { name: "3d", exact: true }).click();
    await expect(page.locator("#network canvas")).toBeVisible({ timeout: 15_000 });
  }
  expect(errors).toEqual([]);
});
