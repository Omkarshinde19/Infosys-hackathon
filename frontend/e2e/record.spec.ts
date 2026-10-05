import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

// Backup video of the live demo, for when the venue setup fails: ./netheal record
// (RECORD=1). Paced for a viewer, 1280x720 like most projectors.
test.skip(!process.env.RECORD, "only when recording: ./netheal record");
test.use({ viewport: { width: 1280, height: 720 }, video: { mode: "on", size: { width: 1280, height: 720 } } });
test.setTimeout(420_000);

const pause = (page: import("@playwright/test").Page, s: number) => page.waitForTimeout(s * 1000);
const show = (page: import("@playwright/test").Page, id: string) =>
  page.locator(`#${id}`).scrollIntoViewIfNeeded();

test("backup demo video", async ({ page }) => {
  await page.goto("/");
  await pause(page, 4);
  await page.mouse.wheel(0, 900);
  await pause(page, 3);

  await signIn(page, "operator");
  await page.getByRole("button", { name: "Reset network" }).click();
  await show(page, "overview");
  await expect(page.getByText("All clear")).toBeVisible({ timeout: 90_000 });
  await pause(page, 3);

  // Live demo: cut a fibre, watch detect -> diagnose -> heal -> verify.
  await show(page, "faults");
  await pause(page, 2);
  await page.getByRole("button", { name: "Hostel fibre cut" }).click();
  await show(page, "alerts");
  await pause(page, 3);
  await show(page, "diagnosis");
  await pause(page, 4);
  await show(page, "healing");
  await expect(page.getByText(/^Healed: traffic is back to normal/)).toBeVisible({ timeout: 60_000 });
  await pause(page, 6);
  await show(page, "network");
  await pause(page, 4);

  // The safety story: a fix the guardrails block.
  await show(page, "faults");
  await page.getByRole("button", { name: "Reset network" }).click();
  await pause(page, 4);
  await page.getByRole("button", { name: /Core router meltdown/ }).click();
  await show(page, "healing");
  await expect(page.getByText(/^Escalated/)).toBeVisible({ timeout: 60_000 });
  await pause(page, 6);

  // Report for the healed incident, then the proof and the assistant.
  await page.goto("/dashboard/incidents");
  await pause(page, 2);
  await page.locator("main").getByRole("link", { name: /link failure/i }).first().click();
  await page.getByRole("button", { name: "Generate report" }).click();
  await expect(page.getByText(/Written by|built-in template/)).toBeVisible({ timeout: 60_000 });
  await pause(page, 6);

  await page.goto("/dashboard/evaluation");
  await pause(page, 5);
  await page.mouse.wheel(0, 700);
  await pause(page, 5);

  await page.goto("/dashboard/copilot");
  await page.getByPlaceholder(/Ask about the network/).fill("Why did the Hostel A connection fail and what did NetHeal do?");
  await page.getByLabel("Send").click();
  await expect(page.getByText(/evidence cited/)).toBeVisible({ timeout: 90_000 });
  await pause(page, 8);
});
