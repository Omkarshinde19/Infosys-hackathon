import { expect, test, type Page, type WebSocketRoute } from "@playwright/test";

// Browser contract fixtures: no gateway mutation, training assets or demo credentials required.
const measured = (loss = 0) => [
  { ts: "2026-01-01T00:00:10Z", entity_type: "node", entity_id: "n1", latency_ms: 1, loss_pct: 0, throughput_mbps: 100, cpu: 0.2, util: null, queue_len: null },
  { ts: "2026-01-01T00:00:10Z", entity_type: "node", entity_id: "n2", latency_ms: 1, loss_pct: 0, throughput_mbps: 100, cpu: 0.2, util: null, queue_len: null },
  { ts: "2026-01-01T00:00:10Z", entity_type: "link", entity_id: "l1", latency_ms: 5, loss_pct: loss, throughput_mbps: 100, cpu: null, util: 0.3, queue_len: 0 },
  { ts: "2026-01-01T00:00:10Z", entity_type: "flow", entity_id: "f1", latency_ms: 7, loss_pct: loss, throughput_mbps: 100, cpu: null, util: null, queue_len: null },
];
function baseline() {
  return {
    generation: "generation-a", sequence: 10,
    topology: { nodes: [{ id: "n1", name: "Core test", layer: "core" }, { id: "n2", name: "Building test", layer: "access" }], links: [{ id: "l1", a: "n1", b: "n2", capacity_mbps: 1000, base_latency_ms: 5 }], flows: [{ id: "f1", src: "n1", dst: "n2", demand_mbps: 100, route: ["n1", "n2"] }] },
    telemetry: measured(), detector: { ready: true, progress: 1 }, anomalies: [], diagnosis: [],
    incident: { incident: null as object | null, healer_status: "idle", awaiting: null, actions: [] as object[] },
    autonomy: { level: 2, levels: { "0": "Alert only: no actions", "1": "Recommend: human applies", "2": "Approval: human approves", "3": "Guarded: low risk only", "4": "Full simulation: verify every fix" } }, backend: { kind: "sim" },
  };
}

async function fixture(page: Page) {
  const control = {
    snapshot: baseline(), sequence: 10, sockets: [] as WebSocketRoute[], snapshots: 0,
    holdSnapshots: false, held: [] as (() => void)[], faults: 0, role: "admin", snapshotError: false,
    send(type: string, data: unknown, extra: object = {}) {
      this.sockets.at(-1)!.send(JSON.stringify({ generation: this.snapshot.generation, sequence: ++this.sequence, type, data, ...extra }));
    },
    release() { this.holdSnapshots = false; this.held.splice(0).forEach((resolve) => resolve()); },
  };
  await page.addInitScript(() => localStorage.setItem("netheal-session", JSON.stringify({ token: "fixture-only", username: "fixture-admin", role: "admin" })));
  await page.routeWebSocket(/\/ws\/live/, (socket) => { control.sockets.push(socket); });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/snapshot") {
      if (control.snapshotError) return route.fulfill({ status: 503, contentType: "text/html", body: "<h1>Unavailable</h1>" });
      ++control.snapshots;
      const json = JSON.stringify(control.snapshot); // capture state before any deliberate delay
      if (control.holdSnapshots) await new Promise<void>((resolve) => control.held.push(resolve));
      return route.fulfill({ contentType: "application/json", body: json });
    }
    if (path === "/api/auth/me") return route.fulfill({ json: { username: "fixture-admin", role: control.role } });
    if (path === "/api/fault") {
      ++control.faults;
      await new Promise((resolve) => setTimeout(resolve, 200));
      return route.fulfill({ json: { ok: true } });
    }
    if (path === "/api/autonomy") {
      const body = route.request().postDataJSON() as { level: number };
      control.snapshot.autonomy.level = body.level;
      return route.fulfill({ json: control.snapshot.autonomy });
    }
    return route.fulfill({ json: [] });
  });
  return control;
}

test("missing data never reports healthy; learning changes only after a measured ready tick", async ({ page }) => {
  const control = await fixture(page);
  control.snapshot.telemetry = [];
  control.snapshot.detector = { ready: false, progress: 0 };
  await page.goto("/dashboard");
  await expect(page.locator("#overview")).toContainText("Flow delivery quality · Unknown");
  await expect(page.getByText("All clear", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Inject fault", exact: true })).toBeDisabled();
  control.send("telemetry", measured(), { detector: { ready: false, progress: 0.5 } });
  await expect(page.locator("#overview")).toContainText("Flow delivery quality · Learning");
  control.send("telemetry", measured(), { detector: { ready: true, progress: 1 } });
  await expect(page.getByText("All clear", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Inject fault", exact: true })).toBeEnabled();
  await expect(page.getByText(/Level 2 · Switch to full simulated healing/)).toBeVisible();
});

test("a silent open socket becomes stale and stops claiming all clear", async ({ page }) => {
  await fixture(page);
  await page.goto("/dashboard");
  await expect(page.getByText("All clear", { exact: true })).toBeVisible();
  await expect(page.locator("#overview")).toContainText("Flow delivery quality · Stale", { timeout: 7000 });
  await expect(page.getByText("All clear", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Inject fault", exact: true })).toBeDisabled();
});

test("newer socket decisions survive a delayed bootstrap snapshot", async ({ page }) => {
  const control = await fixture(page);
  control.holdSnapshots = true;
  await page.goto("/dashboard");
  await expect.poll(() => control.held.length).toBeGreaterThan(0);
  const incident = { id: "coherence-test", status: "failed", opened_at: "2026-01-01T00:00:10Z", mttd_s: 1, mttr_s: null, timeline: [{ ts: "2026-01-01T00:00:11Z", stage: "detect", ref_id: null }] };
  control.send("incident", { incident, healer_status: "escalated", awaiting: null, actions: [{ kind: "escalated", payload: "Fixture escalation survived bootstrap" }] });
  control.release();
  await expect(page.getByText("Fixture escalation survived bootstrap")).toBeVisible();
});

test("sequence gaps recover a snapshot and old generations cannot overwrite it", async ({ page }) => {
  const control = await fixture(page);
  await page.goto("/dashboard");
  await expect(page.getByText("All clear", { exact: true })).toBeVisible();
  control.snapshot.sequence = 14;
  control.snapshot.telemetry = measured(8);
  control.sequence = 13;
  control.send("telemetry", measured(8));
  await expect.poll(() => control.snapshots).toBeGreaterThan(1);
  await expect(page.locator("#overview")).toContainText("Flow delivery quality · Critical");
  control.snapshot.generation = "generation-b";
  control.snapshot.sequence = 1;
  control.snapshot.telemetry = measured();
  control.sequence = 0;
  control.send("telemetry", measured());
  await expect(page.locator("#overview")).toContainText("Flow delivery quality · Healthy");
  control.sockets.at(-1)!.send(JSON.stringify({ generation: "generation-a", sequence: 99, type: "telemetry", data: measured(10) }));
  await expect(page.locator("#overview")).toContainText("Flow delivery quality · Healthy");
});

test("fault controls suppress duplicate requests while pending", async ({ page }) => {
  const control = await fixture(page);
  await page.goto("/dashboard");
  const button = page.getByRole("button", { name: "Inject fault", exact: true });
  await expect(button).toBeEnabled();
  await button.evaluate((element: HTMLButtonElement) => { element.click(); element.click(); });
  await expect.poll(() => control.faults).toBe(1);
  await expect(page.getByText("Injected link down on l1")).toBeVisible();
});

test("phone navigation contains focus, escapes and restores the opener", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await fixture(page);
  await page.goto("/dashboard");
  const opener = page.getByRole("button", { name: "Open menu", exact: true });
  await expect(page.locator("aside")).toHaveAttribute("inert", "");
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "Dashboard navigation" });
  await expect(dialog).toBeVisible();
  await expect(opener).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator("#dashboard-assistant")).toHaveAttribute("inert", "");
  await expect(page.getByRole("link", { name: "Ask NetHeal", exact: true })).toHaveCount(1); // drawer link; background shortcut is hidden
  for (let i = 0; i < 30; i++) {
    await page.keyboard.press("Tab");
    expect(await dialog.evaluate((element) => element.contains(document.activeElement))).toBeTruthy();
  }
  await page.keyboard.press("Escape");
  await expect(opener).toBeFocused();
  await expect(page.locator("aside")).toHaveAttribute("inert", "");
  await expect(page.locator("#dashboard-assistant")).not.toHaveAttribute("inert", "");
});

test("a forged stored admin role never grants controls after server validation as viewer", async ({ page }) => {
  const control = await fixture(page);
  control.role = "viewer";
  await page.goto("/dashboard");
  await expect(page.getByText("fixture-admin")).toBeVisible();
  await expect(page.getByRole("button", { name: "Inject fault", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: /Switch to full simulated healing/ })).toBeDisabled();
});

test("partial telemetry cannot claim all clear or a healthy network", async ({ page }) => {
  const control = await fixture(page);
  control.snapshot.telemetry = measured().filter((sample) => sample.entity_type === "flow");
  await page.goto("/dashboard");
  await expect(page.locator("#overview")).toContainText("Flow delivery quality · Unknown");
  await expect(page.getByText("All clear", { exact: true })).toHaveCount(0);
});

test("HTML proxy failures show a useful retry instead of an unhandled JSON error", async ({ page }) => {
  const control = await fixture(page);
  control.snapshotError = true;
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/dashboard");
  await expect(page.getByText(/Server unavailable \(503\)/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry snapshot", exact: true })).toBeEnabled();
  control.snapshotError = false;
  await page.getByRole("button", { name: "Retry snapshot", exact: true }).click();
  await expect(page.getByText("All clear", { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test("a failed sequence-gap recovery cannot promote recent cached telemetry to fresh", async ({ page }) => {
  const control = await fixture(page);
  await page.goto("/dashboard");
  await expect(page.getByText("All clear", { exact: true })).toBeVisible();
  control.snapshotError = true;
  control.sequence = 13;
  control.send("telemetry", measured());
  await expect(page.getByText(/Server unavailable \(503\)/)).toBeVisible();
  // A freshness timer must not undo the coherence failure while the old measurements are recent.
  await page.waitForTimeout(1300);
  await expect(page.getByText("All clear", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Inject fault", exact: true })).toBeDisabled();
  control.snapshotError = false;
  control.snapshot.sequence = control.sequence;
  await page.getByRole("button", { name: "Retry snapshot", exact: true }).click();
  await expect(page.getByText("All clear", { exact: true })).toBeVisible();
});

test("a relapse invalidates a locally generated report and current verification stage", async ({ page }) => {
  const control = await fixture(page);
  const incident = {
    id: "report-facts", status: "resolved", opened_at: "2026-01-01T00:00:10Z", mttd_s: 1, mttr_s: 4 as number | null,
    timeline: ["detect", "diagnose", "decide", "heal", "verify"].map((stage, i) => ({ stage, ts: `2026-01-01T00:00:${11 + i}Z`, ref_id: null })),
  };
  control.snapshot.incident.incident = incident;
  await page.route("**/api/incidents/report-facts**", (route) => {
    if (route.request().method() === "POST") return route.fulfill({ json: { markdown: "Old verified recovery explanation", source: "template", fallback_reason: "fixture", generated_at: "2026-01-01T00:00:20Z" } });
    return route.fulfill({ json: { incident: control.snapshot.incident.incident, anomalies: [], diagnosis: [], actions: control.snapshot.incident.actions, report: null } });
  });
  await page.goto("/dashboard/incidents/report-facts");
  await page.getByRole("button", { name: "Generate report", exact: true }).click();
  await expect(page.getByText("Old verified recovery explanation")).toBeVisible();
  incident.status = "healing";
  incident.mttr_s = null;
  incident.timeline.push({ stage: "decide", ts: "2026-01-01T00:00:21Z", ref_id: null });
  control.snapshot.incident.actions.push({ kind: "relapsed", payload: "Recovery stopped holding" });
  control.send("incident", { ...control.snapshot.incident, healer_status: "relapsed" });
  await expect(page.getByText("Old verified recovery explanation")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Generate report", exact: true })).toBeVisible();
  await expect(page.locator("ol > li").nth(4)).toContainText("…");
  await expect(page.locator("ol > li").nth(3)).toContainText("…");
});

test("assistant answers expose their captured snapshot and a logout discards conversation state", async ({ page }) => {
  await fixture(page);
  await page.route("**/api/copilot", (route) => route.fulfill({ json: {
    answer: "Captured network evidence [E1]", evidence: { E1: { kind: "telemetry", text: "Fixture snapshot" } }, tools: ["get_network_status"], source: "template", fallback_reason: "fixture",
    captured_at: "2026-10-07T06:00:00Z", observed_at: "2026-10-07T05:59:55Z", generation: "snapshot-a", snapshot_age_s: 5, stale: true, documentation_version: "docs-fixture",
  } }));
  await page.goto("/dashboard/copilot");
  await page.getByPlaceholder(/Ask about the network/).fill("What was observed?");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText(/Captured snapshot ·/)).toContainText("5.0 s old at capture · stale when captured");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByText(/Captured snapshot ·/)).toHaveCount(0);
  await expect(page.getByText("Sign in to ask questions.", { exact: false })).toBeVisible();
});
