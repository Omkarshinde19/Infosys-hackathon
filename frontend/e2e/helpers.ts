import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, type Page } from "@playwright/test";

// Demo accounts live in config/DEMO_ACCOUNTS.md (never hard-coded here).
export function demoPassword(username: string): string {
  const accounts = readFileSync(join(__dirname, "..", "..", "config", "DEMO_ACCOUNTS.md"), "utf8");
  return accounts.match(new RegExp(`\\| \`${username}\` \\| \`([^\`]+)\` \\|`))![1];
}

/** The venue may have no internet: abort anything not served by this laptop, and record it. */
export async function blockInternet(page: Page): Promise<string[]> {
  const blocked: string[] = [];
  await page.context().route("**/*", (route) => {
    const { hostname } = new URL(route.request().url());
    if (["localhost", "127.0.0.1"].includes(hostname)) return route.continue();
    blocked.push(route.request().url());
    return route.abort();
  });
  return blocked;
}

export async function signIn(page: Page, username: string) {
  await page.goto("/login");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(demoPassword(username));
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

// Known and harmless; anything else is a finding.
export const IGNORED = [
  /THREE\.Clock: This module has been deprecated/, // inside @react-three/fiber 9.8 (latest), not our code
  /GL Driver Message|GPU stall due to ReadPixels/, // headless Chrome's software WebGL only
  /was preloaded using link preload but not used/, // Next.js prefetching the next page's CSS
  /\[Fast Refresh\]|Download the React DevTools/, // dev-server chatter
];

