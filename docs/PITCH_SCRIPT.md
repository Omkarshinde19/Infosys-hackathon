# NetHeal presentation script (Team Syntax Cartel, 7 Oct 2026)

Deck: `documents/NetHeal_Technical_Deck.pptx` (15 slides, dark, matches the app). Every slide's speaker notes hold the lines below.

| Slides | Speaker | Content |
|---|---|---|
| 1 to 2 | Abeer | Title, problem statement, six fault classes |
| 3 to 8 | Parth | Architecture, control loop, safety gate, event pipeline, AI layer, stack |
| 9 to 13 | Omkar | Live demo (slides play in the background while Omkar drives the website) |
| 14 to 15 | Abeer | Results, thank you, Q&A |

## Omkar: live demo (≈2:30)

Keep the deck on slides 9 to 13 behind you; move one slide per part. Pause a second after every click.

**1 · Control Room (slide 9, ≈25 s)** *Overview / Telemetry*
> This is the NetHeal Control Room. The sidebar is our mission control: telemetry, alerts, diagnosis and healing. Data is flowing normally: latency and loss for every flow, twice a second. Bottom left, Data status reads live and fresh: a stable baseline, every service inside its SLA.

**2 · Network (slide 10, ≈25 s)** *Click Network*
> Network is the live topology. It is not a static diagram: every switch, router and link is coloured by its current health, in 2D or 3D. If a link fails or congests, it changes here instantly, so we see the blast radius at a glance.

**3 · Fault Lab (slide 11, ≈25 s)** *Click Fault Lab → "Silent packet loss at the CS Lab"*
> Fault Lab lets us break the network safely: six fault types on any link or device. I'm injecting silent packet loss at the CS Lab now. The link stays up but drops packets, which routing cannot see. Let's watch NetHeal.

**4 · Detection and diagnosis (slide 12, ≈25 s)** *Click Alerts, then Diagnosis*
> In about two seconds the alert appears, raised only because several detectors agree. Diagnosis names the cause and the exact link, with a confidence score and the evidence behind it. No engineer digging through logs.

**5 · Healing and Ask NetHeal (slide 13, ≈40 s)** *Click Healing, then the incident report / Ask NetHeal*
> Healing shows the fix. The digital twin tested several reroutes, the safety policy passed them, and the best one was applied and verified: packet loss back to normal within seconds. At comfort level 2 it would wait on Approvals for a human, and a failed fix rolls back on its own. Finally, the incident report and Ask NetHeal: Llama 3.3 70B on Qualcomm Cloud AI writes the post mortem from the facts. NetHeal turns a reactive fire drill into a controlled, verified process.

Ask NetHeal: ask "What happened in the last incident and how was it fixed?" (verified on Qualcomm, ≈20 s). If it is slow, keep talking over slide 13.
If anything breaks: Fault Lab → Reset network, then "Hostel fibre cut".
