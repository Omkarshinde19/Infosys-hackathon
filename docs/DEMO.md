# Demo playbook

Everything needed to run the 5-minute NetHeal demo, with or without venue internet. The script follows [PLAN.md](PLAN.md) §9, updated to what is actually built.

## The day before (online)

```bash
./netheal start      # builds and pulls every image
./netheal ollama     # offline AI model (qwen2.5:7b, ~4.7 GB once)
./netheal rehearse   # pre-flight checks + the demo 5x in a row with the internet blocked
./netheal record     # fresh backup video -> demo/netheal-demo.webm
```

Then **turn Wi-Fi off and run `./netheal rehearse` once more.** The browser test already blocks the internet, but only a real Wi-Fi-off run proves the engine side too (Ask NetHeal and reports switch to the local model automatically).

## Right before going on stage

1. `./netheal status`: every line green.
2. `./netheal reset`: fresh incidents, the detector re-learns for 30 s.
3. Browser at http://localhost:3000, signed in as `operator` (password: `config/DEMO_ACCOUNTS.md`), zoom 100%, other tabs closed.
4. The emulator is **off** unless you will show it (`./netheal emu` uses ~10 CPU cores).
5. `demo/netheal-demo.webm` open in a second window, just in case.

## The 5 minutes

| Time | Show | Say |
|---|---|---|
| 0:00–0:40 | Landing page | Campus outages take 30–60 min of manual troubleshooting, and nobody can safely test a fix on production. NetHeal detects, diagnoses and fixes faults itself, testing every fix on a digital twin first. |
| 0:40–1:20 | Architecture slide | Detect → diagnose → decide → heal → verify. Statistics + 3 ML detectors, rules + GNN for root cause, twin dry runs, OPA safety rules. The AI explains but never acts. |
| 1:20–1:40 | **Control Room**: health score, map (flip to 3D for a second) | A live campus: 15 devices, 27 links, 9 traffic flows, measured twice a second. |
| 1:40–2:40 | **Fault Lab → "Silent packet loss at the CS Lab"** | A gray failure: the link is "up" but quietly drops packets, which OSPF can't see. Point at: alert (≈2.5 s) → **Diagnosis** (gray failure on the Distribution South A ↔ CS Lab link, with the GNN's opinion) → **Healing** table (candidates tested on the twin, OPA "passed", sometimes an "RL agent" proposal) → "Healed" (≈9 s), before/after numbers. |
| 2:40–3:10 | Click **Incident · report** → Generate report | The language model writes the report from the incident's facts only; it is checked against them before it is shown. |
| 3:10–3:40 | **Fault Lab → "Core router meltdown"** | Not every fix is safe. Moving that much traffic breaks the blast-radius rule, so NetHeal escalates to a human instead of acting. |
| 3:40–4:00 | **Ask NetHeal**: "Why didn't NetHeal fix the core router by itself?" | Read-only tools, every sentence cites evidence (hover the chips). |
| 4:00–4:30 | **Evaluation** page | 300 faults it never trained on. Without healing, 0% recover; with NetHeal 85%, in a median 4.5 s, with 0 false alarms. Users hurt 865 s instead of 5,625 s. |
| 4:30–5:00 | Roadmap slide | Real devices (gNMI/SNMP in, NETCONF/SDN out), the emulated network with real packets (Settings → Network backend), multi-campus, RL policy graduating behind the guardrails. |

Numbers above are from `docs/EVALUATION.md` (policy `rl`, the live configuration). Re-check them after any `./netheal eval`.

## If something goes wrong

| Problem | Do this |
|---|---|
| Venue internet down | Nothing: the stack runs locally, Ask NetHeal and reports use the local model (answers say "Ollama on this laptop"). |
| Ask NetHeal is slow | It answers within 75 s or falls back to a template answer. Talk over it, or skip to the Evaluation page. |
| Stray alert / "All clear" doesn't appear | Fault Lab → **Reset network**. If still stuck: `./netheal reset` (30 s). |
| A drill escalates unexpectedly | That is the safety story: say so, then use "Hostel fibre cut" (the most reliable drill). |
| Dashboard won't load | `./netheal status`, then `./netheal restart` (≈1 min). Meanwhile play the backup video. |
| Laptop dies | Second laptop with a clone, same `./netheal start` the day before. Or the backup video from a USB stick. |

## Likely judge questions

| Question | Answer |
|---|---|
| Why not let the LLM decide? | Hallucination, no determinism, no audit trail. It gets read-only tools and must cite evidence IDs; fixes come from the healer, the twin and OPA. |
| Doesn't OSPF already reroute? | For hard failures, yes. Not for gray failures, congestion or overloaded devices: links that are up but sick. |
| What if a fix makes it worse? | Twin dry run first, OPA blast-radius rules, a 3 s verify window, automatic rollback, all recorded in the tamper-evident ledger. If a verified fix stops holding later, NetHeal plans once more or escalates. |
| Where does training data come from? | Our own simulator: 3,000 labelled fault scenarios for the GNN, forecaster and autoencoder; 300,000 healing decisions for the RL agent. |
| Is the RL agent better than rules? | Slightly (80.0% vs 77.3% of decisions fixed), all on overloaded access switches where the rules have no option. It only proposes; the twin picks. |
| Why do "reactive rules" recover more faults in your table? | They ignore the blast-radius rule. NetHeal hands those cases to a human on purpose. |
| Real networks? | Swap the backend adapter. We already run the same loop on Mininet + Open vSwitch with real packets: detected in 1.5 s, healed in 4.5 s. |
