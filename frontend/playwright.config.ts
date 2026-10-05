import { defineConfig, devices } from "@playwright/test";

// Demo-flow test against the running stack (./netheal start): npm run e2e
export default defineConfig({
  testDir: "e2e",
  timeout: 180_000,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
