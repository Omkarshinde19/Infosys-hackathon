import { writeFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { demoPassword, IGNORED } from "./helpers";

// UI audit: every page x screen size x theme x signed-in state. Collects console errors and
// warnings, uncaught exceptions, failed requests, broken internal links, horizontal overflow
// and serious accessibility violations. ./netheal ui-check (AUDIT=1).
test.skip(!process.env.AUDIT, "only for ./netheal ui-check");
test.setTimeout(900_000);

const SIZES = { desktop: [1440, 900], projector: [1024, 768], phone: [390, 844] } as const;
const THEMES = ["dark", "light"] as const;
type Finding = { page: string; size: string; theme: string; user: string; kind: string; detail: string };

async function pagesToVisit(page: Page): Promise<string[]> {
  const incidents = await (await page.request.get("/api/incidents")).json();
  return [
    "/", "/login", "/dashboard", "/dashboard/copilot", "/dashboard/whatif", "/dashboard/incidents",
    ...(incidents.length ? [`/dashboard/incidents/${incidents[0].incident.id}`] : []),
    "/dashboard/approvals", "/dashboard/insights", "/dashboard/evaluation", "/dashboard/audit",
    "/dashboard/settings",
  ];
}

async function signInAs(page: Page, username: string) {
  const res = await page.request.post("/api/auth/login", { data: { username, password: demoPassword(username) } });
  const session = await res.json();
  await page.addInitScript((s) => localStorage.setItem("netheal-session", JSON.stringify(s)), session);
}

test("UI audit", async ({ browser }) => {
  const findings: Finding[] = [];
  const links = new Set<string>();
  for (const user of ["signed-out", "admin"]) {
    for (const theme of THEMES) {
      for (const [size, [width, height]] of Object.entries(SIZES)) {
        const context = await browser.newContext({ viewport: { width, height } });
        const page = await context.newPage();
        await page.addInitScript((t) => localStorage.setItem("theme", t), theme);
        if (user === "admin") await signInAs(page, "admin");
        let where = "";
        const note = (kind: string, detail: string) =>
          IGNORED.some((re) => re.test(detail)) ||
          findings.push({ page: where, size, theme, user, kind, detail: detail.slice(0, 300) });
        page.on("console", (m) => (m.type() === "error" || m.type() === "warning") && note(`console.${m.type()}`, m.text()));
        page.on("pageerror", (e) => note("exception", e.message));
        page.on("response", (r) => r.status() >= 400 && note("http", `${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`));
        page.on("requestfailed", (r) => !r.url().includes("_rsc") && note("request-failed", `${r.failure()?.errorText} ${r.url()}`));

        for (const path of await pagesToVisit(page)) {
          where = path;
          await page.goto(path);
          await page.waitForTimeout(2500);
          const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
          if (overflow > 1) note("overflow", `${overflow}px wider than the screen`);
          for (const href of await page.locator("a[href^='/']").evaluateAll((as) => as.map((a) => a.getAttribute("href")!))) {
            links.add(href.split("#")[0]);
          }
          if (size === "desktop") {
            const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
            for (const v of axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical")) {
              note(`a11y.${v.id}`, `${v.help} (${v.nodes.length}x) e.g. ${v.nodes[0]?.target.join(" ")}`);
            }
          }
        }
        await context.close();
      }
    }
  }
  const page = await browser.newPage();
  for (const href of links) {
    const status = (await page.request.get(href)).status();
    if (status >= 400) findings.push({ page: href, size: "-", theme: "-", user: "-", kind: "broken-link", detail: `${status}` });
  }
  writeFileSync("test-results/ui-audit.json", JSON.stringify(findings, null, 1));
  const counts = new Map<string, number>();
  for (const f of findings) counts.set(`${f.kind} | ${f.page} | ${f.detail}`, (counts.get(`${f.kind} | ${f.page} | ${f.detail}`) ?? 0) + 1);
  console.log(`\n${findings.length} findings, ${counts.size} distinct:`);
  for (const [k, n] of [...counts].sort()) console.log(`  ${n}x ${k}`);
  expect(findings).toEqual([]);
});
