# NetHeal pitch script (Team Syntax Cartel, 7 Oct 2026)

Deck: `documents/NetHeal_Syntax_Cartel_Presentation_v2.pptx` (13 slides + 3 backup; the same lines are in each slide's speaker notes).
Format: **5 min presentation + live demo**, then **5 min Q&A**. Read at a calm ≈145 words per minute; slow down on the bold numbers.

| Block | Speaker | Slides | Time |
|---|---|---|---|
| A · The why | **Abeer** | 1 to 5 | ≈ 1:05 |
| B · The product, Qualcomm AI, how we built it | **Omkar** (drives the laptop) | 6 to 9 + live demo | ≈ 2:20 |
| C · The system | **Parth** | 10 to 13 | ≈ 1:30 |

---

## A · Abeer (slides 1 to 5)

**Slide 1 · Title**
> We're Syntax Cartel from DIT Pimpri, and we took on NC-04: the self healing network.

**Slide 2 · Team** (3 seconds, just click on)

**Slide 3 · Networks fail quietly**
> Every organisation runs on a network nobody can see inside. When it breaks, one hour costs most large companies **over three hundred thousand dollars**, and the median fix takes **fifty one minutes**.
> The worst failures raise no alarm at all. A link shows "up" while it silently drops packets. The router sees nothing wrong, so it never reroutes. Users feel it; dashboards stay green.

**Slide 4 · Today's answers stop halfway**
> Today's tools stop halfway. Monitoring tells a human. Routing protocols only route around dead links: in our tests that recovered **twelve percent**. Vendor AI fixes things, but only on its own hardware. NetHeal finishes the job.

**Slide 5 · Measured, not promised**
> On 300 test scenarios NetHeal recovered **seventy two percent** of the faults that hurt users, against two percent without it: a verified fix in a median **four and a half seconds**, **zero false alarms**, and **seventy four percent less** time users were hurt. Omkar will show you how.

---

## B · Omkar (slides 6 to 9)

**Slide 6 · One loop, twelve live screens**
> NetHeal is one loop: watch, notice, diagnose, fix safely, explain. Twelve screens, all live. Let me show you.

**Live demo (≈ 70 s)**, signed in as operator, network reset beforehand:
1. Control Room, 3D map: "15 devices, 27 links, 9 traffic flows, measured twice a second."
2. Fault Lab → **Silent packet loss at the CS Lab**: point at the alert (≈2 s) → Diagnosis (gray failure, exact place, the GNN agrees) → Healing (fixes tested on the twin, safety "passed") → **Healed** (≈9 s).
3. Fault Lab → **Core router meltdown**: "Moving that much traffic breaks our blast radius rule, so NetHeal hands it to a human."
4. Round Ask NetHeal button → "Why didn't NetHeal fix the core router by itself?" Switch back to the slides while it thinks (≈14 s).

If something breaks: Fault Lab → Reset network, or play the backup video. Stay calm: an escalation *is* the safety story.

**Slide 7 · You decide how much it may do**
> You stay in control: five comfort levels, from "just tell me" to fully automatic. Every fix is tested on the twin in about a millisecond, checked by **eight safety rules**, and undone if it doesn't help within three seconds.

**Slide 8 · Qualcomm Cloud AI**
> The language AI runs on **Qualcomm Cloud AI 100 Ultra**: Llama 3.3 70B writes incident reports and powers Ask NetHeal with eight read only tools, and bge embeddings search our docs. It starts answering in **about a second and a half**; a full answer with tools and citations takes **about fourteen seconds**. It cites evidence for every claim and can never touch the network. If the cloud drops, a local model and then templates take over.

**Slide 9 · How we built it with Claude: six layers**
> We built this with Claude as our pair programmer, under six layers. **Purpose**: a production grade prototype, with us as architects and reviewers. **Date**: a dated plan, sixteen phases in three days. **Model**: Claude Opus 5.5 in Claude Code. **System**: written rules it must follow, from "think before coding" to "test first". **Trust**: every bug gets a failing test first, and CI runs on every push. **Impact**: over four hundred twenty small commits, every one verified. Parth will take you under the hood.

---

## C · Parth (slides 10 to 13)

**Slide 10 · Architecture: five pillars**
> Under the hood, NetHeal is five pillars. **One, the network**: either our digital twin, pure maths at a fifth of a millisecond per tick, or Mininet with Open vSwitch sending real packets. Both sit behind one interface, so the engine never knows which one it is talking to.
> **Two, the engine** runs the loop every half second. Two detectors must agree before an alert. Diagnosis combines fault signatures, path voting and a graph neural network. Every fix, from rules or from our reinforcement learning agent, is dry run on the twin and checked against eight policy rules, then verified flow by flow.
> **Three**, every event goes out on Redpanda to the live dashboard and TimescaleDB, and every action lands in a hash chained audit ledger. **Four**, the AI layer only reads. **Five**, the dashboard.

**Slide 11 · Why this stack**
> Each choice beat the obvious one. The in process twin tests a fix in a millisecond where packet simulators take minutes. Redpanda gives us the Kafka API without the JVM. TimescaleDB is just Postgres. OPA turns safety into rules a network team can read. And path voting alone found the right cause three percent of the time on a campus, so we combined it with signatures and a graph neural network.

**Slide 12 · What's next**
> Next: real device adapters, many sites in one view, and an RL agent that earns autonomy from operator approvals. It already runs on real packets in emulation; real campus hardware is the next proof.

**Slide 13 · Close** (leave it up during Q&A)
> So one question for you: the next time a link in your network starts quietly dropping packets, who finds it first: **your users, or your network?** Thank you.

---

## Q&A cheat sheet (who answers)

| Question | Who | Answer |
|---|---|---|
| Is it real or simulated? | Parth | A simulated campus twin, plus Mininet + Open vSwitch with real packets. Real hardware is the next step (slide 12). |
| Why do rules without guardrails recover more (74% vs 72%)? | Abeer | They ignore the blast radius rule. NetHeal hands those cases to a human on purpose (backup slide 14). |
| Doesn't OSPF already reroute? | Parth | Only for dead links. Not for links that are up but sick: 12% recovered in our test. |
| How accurate is the root cause? | Abeer | 84% right first guess in the full loop; the GNN alone scores 95% on its test set (backup slide 15). |
| Why not let the LLM decide? | Omkar | Hallucination, no determinism, no audit trail. It has no write tools at all (backup slide 16). |
| How fast is Qualcomm? | Omkar | Measured today: first word ≈1.5 s, ≈18 tokens/s, full Ask NetHeal answer ≈14 s. |
| Did AI write the code? | Omkar | Claude was our pair programmer; we set the rules, the phases and every decision. The `.claude/` folder logs every session. |
| What if a fix makes it worse? | Parth | Twin dry run, 8 OPA rules, a 3 s per flow check, automatic undo, all in the audit ledger. |

Numbers: `docs/EVALUATION.md` (policy `rl`, the live configuration). Qualcomm timings measured on 7 Oct (median of 3 runs; Ask NetHeal 13.5 s and 14.1 s through the engine).
