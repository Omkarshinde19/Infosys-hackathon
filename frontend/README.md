# NetHeal dashboard

The dashboard shows the simulated campus, detection evidence, supported or uncertain diagnoses, guarded repair attempts, incident reports and saved evaluation artifacts. It uses Next.js, React, TypeScript and Tailwind; shared live state is in `src/lib/live.ts`.

## Run on Windows

Use the project-root launcher after dependencies are installed:

```powershell
.\netheal.ps1 start
```

Open http://localhost:3000/dashboard. The controller is http://localhost:8001 and its interactive API reference is `/docs`. Demo sign-in details are in `../config/DEMO_ACCOUNTS.md`. `.\netheal.ps1 status` reads controller health; `.\netheal.ps1 stop` stops only the recorded project processes. Logs are in `.cache/runtime` at the project root.

For manual development, start the controller separately and run these commands from this folder:

```powershell
$env:GATEWAY_URL = 'http://127.0.0.1:8001'
$env:NEXT_PUBLIC_GATEWAY_WS = 'ws://localhost:8001/ws/live'
npm ci
npm run dev
```

`GATEWAY_URL` is the server-side proxy target. `NEXT_PUBLIC_GATEWAY_WS` is compiled into the browser bundle; set it before `npm run build` and rebuild when its address changes.

## Data and control boundaries

- `/api/[...path]` proxies REST requests to the controller. The browser reads a coherent `/snapshot`, buffers live messages, and replays newer messages from the same generation.
- Generation/sequence checks reject duplicates and old state. Gaps trigger resynchronization; failed recovery or absent/stale telemetry shows an explicit unknown/learning/stale state.
- Fault injection and report generation require operator permission. Autonomy/backend changes require admin. Restored sessions are checked against `/auth/me`; server authorization remains authoritative.
- The topology defaults to 2D. The optional 3D renderer loads on demand. Charts register only required ECharts modules and dispose instances on cleanup.
- Reports show current repair outcomes and per-flow evidence. Assistant answers show captured snapshot provenance; its tools cannot change the live network.
- Evaluation reads the saved operational benchmark. Insights also contains historical model-training results, which have different tasks and denominators.

## Check the frontend

```powershell
npm run lint
npm run build
npx playwright test e2e/state-coherence.spec.ts
```

Playwright uses an installed Chrome channel when configured, or its normal browser runtime. Isolated state fixtures mock network responses; separate demo/interaction tests exercise the real running simulator. `AUDIT=1` enables the page/viewport/theme/role matrix. See the root README and `docs/DEMO.md` for full runtime prerequisites and the demo sequence.
