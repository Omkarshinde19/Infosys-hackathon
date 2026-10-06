import { defineConfig, devices } from "@playwright/test";

// Demo-flow test against the running stack (./netheal start): npm run e2e
export default defineConfig({
  testDir: "e2e",
  timeout: 180_000,
  workers: 1, // every test drives the same live network: never run two at once
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
