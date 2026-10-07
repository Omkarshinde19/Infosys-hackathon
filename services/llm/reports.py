"""Plain-language incident reports.

The LLM (Qualcomm Cloud AI Inference Suite via Cirrascale, OpenAI-compatible API) only
*explains*: it receives a fact sheet built from the incident and must write from those
facts alone. If there is no API key, the call fails or times out, or the draft doesn't
mention the real root cause and MTTR (grounding check), a deterministic template
writes the report instead, so a report is always available offline.
"""

import asyncio
import json
import os
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx2
from dotenv import load_dotenv
from openai import AsyncOpenAI

from contracts.models import Incident
from services.netsim.engine import Network

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MODEL = os.getenv("LLM_MODEL", "Llama-3.3-70B")
TIMEOUT_S = 25
PROVIDER_TIMEOUT_S = 10

CAUSES = {
    "link_failure": "Link failure (the connection went down completely)",
    "gray_failure": "Gray failure (the link stayed up but silently dropped packets)",
    "congestion": "Congestion (more traffic than the link could carry)",
    "node_overload": "Device overload (a switch/router ran out of CPU)",
    "misconfig": "Misconfiguration (a forwarding rule sent traffic nowhere)",
    "flapping": "Flapping link (the link kept going up and down)",
}

SYSTEM_PROMPT = """You are NetHeal's incident writer. Write an incident report in Markdown \
for a non-technical IT manager, using ONLY the facts in the JSON you are given. Never \
invent numbers, devices, causes or actions. Use the device names exactly as given.

Sections, in this order:
## Summary (2-3 sentences: what broke, where, how fast NetHeal fixed it)
## Impact (which traffic suffered and how badly)
## Root cause (the cause, where, confidence and the evidence)
## What NetHeal did (detection, diagnosis, the fix chosen and why it was safe)
## Results (a Markdown table: metric | before | after | normal)
## Recommendations (2-3 short bullets for the IT team)

Keep it under 300 words. Plain English, no jargon without a short explanation.
Use per-flow reachability and measurements for recovery evidence. An aggregate latency
containing unreachable traffic uses a simulation sentinel, not measured round-trip time.
Root cause refers to the latest repair attempt; earlier causes belong to incident history."""


CLOUD = "Qualcomm Cloud AI (Cirrascale)"
LOCAL = "Ollama on this laptop"
LOCAL_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")


class Failover:
    """OpenAI-compatible client that tries each (client, model, label) in order: the cloud
    model first, then the local Ollama one, so the assistant and reports keep working
    without internet. Each response is stamped with the model and provider that answered."""

    def __init__(self, providers: list[tuple]):
        self.providers = providers
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.cloud = next((c for c, _, label in providers if label == CLOUD), None)  # embeddings

    async def create(self, model: str | None = None, **kwargs):
        error = None
        for client, name, label in self.providers:
            try:
                response = await asyncio.wait_for(
                    client.chat.completions.create(model=name, **kwargs),
                    timeout=PROVIDER_TIMEOUT_S,
                )
            except Exception as e:  # offline, timeout, auth: try the next provider
                error = e
                continue
            response.model, response.provider = name, label
            return response
        raise error or ConnectionError("No explanation provider is available")


def make_client() -> Failover | None:
    providers = []
    key, endpoint = os.getenv("INFERENCE_CLOUD_API_KEY"), os.getenv("INFERENCE_CLOUD_ENDPOINT")
    if key and key != "your-api-key" and endpoint:
        timeout = httpx2.Timeout(PROVIDER_TIMEOUT_S, connect=3.0)
        cloud = AsyncOpenAI(api_key=key, base_url=endpoint, timeout=timeout, max_retries=0)
        providers.append((cloud, MODEL, CLOUD))
    if url := os.getenv("OLLAMA_URL"):  # e.g. http://localhost:11434/v1 (./netheal ollama)
        providers.append(
            (
                AsyncOpenAI(
                    api_key="ollama", base_url=url, timeout=PROVIDER_TIMEOUT_S, max_retries=0
                ),
                LOCAL_MODEL,
                LOCAL,
            )
        )
    return Failover(providers) if providers else None


def entity_namer(net: Network) -> Callable[[str], str]:
    """'dist1-library' -> 'Distribution North A ↔ Library', flows as 'A → B'."""

    def node(n: str) -> str:
        return net.graph.nodes[n]["name"] if n in net.graph else n

    def name(entity: str) -> str:
        if entity in net.links:
            a, b = net.links[entity]
            return f"{node(a)} ↔ {node(b)}"
        if entity in net.flows:
            f = net.flows[entity]
            return f"{node(f['src'])} → {node(f['dst'])}"
        return node(entity)

    return name


def incident_facts(incident: Incident, ctx: dict, name: Callable[[str], str]) -> dict:
    applied = [p for a in ctx["actions"] if a["kind"] == "applied" for p in [a["payload"]]]
    diagnosis = ctx["diagnosis"]
    top = diagnosis[0] if diagnosis else None
    # A later repair can address a different cause while the original fault remains
    # visible on an unused resource. Explain the repair actually applied most recently.
    if applied:
        latest = applied[-1]
        target = (
            latest.params.get("flow")
            if latest.type == "rollback_config"
            else next(iter(latest.params.get("avoid", [])), None)
        )
        top = next((h for h in diagnosis if h.target == target and h.supported), None)
    results = [a["payload"] for a in ctx["actions"] if a["kind"] == "result"]
    last_result = results[-1] if results else None
    verified = (
        last_result
        if last_result and last_result.verified and incident.status == "resolved"
        else None
    )
    why_no_fix = ("escalated", "no_action", "alert_only")
    notes = [a["payload"] for a in ctx["actions"] if a["kind"] in why_no_fix]
    proposed = [c for a in ctx["actions"] if a["kind"] == "proposed" for c in a["payload"]]

    def describe(c) -> str:
        if c.type == "rollback_config":
            return f"Rolled back the forwarding rules of {name(c.params['flow'])}"
        flows = [name(f) for f in c.params["routes"]]
        via = " → ".join(name(n) for n in next(iter(c.params["routes"].values()))[1:-1])
        verb = "Drained traffic off" if c.type == "drain_node" else "Rerouted traffic around"
        return f"{verb} {name(c.params['avoid'][0])} for {', '.join(flows)} (new path via {via})"

    def alert(a) -> str:
        if a.metric == "reachability":
            return f"{name(a.entity_id)}: unreachable"
        return f"{name(a.entity_id)}: {a.metric} {a.value:.2f} (normal {a.baseline:.2f})"

    return {
        "incident_id": incident.id,
        "status": incident.status,
        "confidence_kind": "heuristic ranking score; not a calibrated probability",
        "fault_started_at": incident.opened_at.isoformat(timespec="seconds"),
        "time_to_detect_s": incident.mttd_s,
        "time_to_heal_s": incident.mttr_s,
        "alerts": [alert(a) for a in ctx["anomalies"].values()],
        "root_cause": top
        and {
            "cause": CAUSES[top.cause],
            "where": name(top.target),
            "confidence_pct": round(top.confidence * 100),
            "evidence": [e.description for e in top.evidence],
        },
        "fixes_considered_on_digital_twin": len(proposed),
        "fixes_blocked_by_safety_checks": sum(c.opa_decision == "deny" for c in proposed),
        "fix_applied": describe(applied[-1]) if applied else None,
        "fixes_rolled_back": sum(r.rolled_back for r in results),
        "fix_verified": verified is not None,
        "affected_traffic_before": verified and _rounded(verified.before),
        "affected_traffic_after": verified and _rounded(verified.after),
        "per_flow_before": verified and verified.per_flow_before,
        "per_flow_after": verified and verified.per_flow_after,
        "flow_names": {fid: name(fid) for fid in (verified.per_flow_before if verified else {})},
        "metric_note": "Aggregate latency substitutes 1000 ms for unreachable flows; "
        "it is a simulation scoring sentinel, not a measured delay. Per-flow reachability "
        "and post-action measurements determine verification.",
        "latest_result": last_result and last_result.model_dump(mode="json"),
        "notes": notes,
    }


def _rounded(d: dict) -> dict:
    out = {k: round(v, 2) for k, v in d.items()}
    if d.get("loss_pct", 0) >= 99:
        out["latency_ms"] = "unreachable"
    return out


async def write_report(facts: dict, client: AsyncOpenAI | None, model: str = MODEL) -> dict:
    """Markdown report; falls back to the template when the LLM can't be used or trusted."""
    reason = "No AI credentials configured"
    if client is not None:
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": json.dumps(facts, indent=2, default=str, ensure_ascii=False),
                        },
                    ],
                    max_tokens=700,
                    temperature=0.2,
                ),
                timeout=TIMEOUT_S,
            )
            text = response.choices[0].message.content.strip()
            if _grounded(text, facts):
                return _report(text, f"llm:{getattr(response, 'model', None) or model}",
                               provider=getattr(response, "provider", CLOUD))  # fmt: skip
            reason = "AI draft failed the grounding check"
        except Exception as e:  # network, auth, timeout: the demo must go on
            reason = f"AI unavailable ({type(e).__name__})"
    return _report(template_report(facts), "template", reason)


def _grounded(text: str, facts: dict) -> bool:
    """Check identities, timing, numeric evidence and current outcome.

    This deterministic check cannot prove semantic entailment of arbitrary prose.
    The UI retains the authoritative evidence alongside any explanatory AI draft.
    """
    root, lower = facts["root_cause"], text.lower()
    if root:
        cause = root["cause"].split(" (")[0].lower()  # "Link failure (...)" -> "link failure"
        devices = re.split(" ↔ | → ", root["where"])
        if cause not in lower or any(d.lower() not in lower for d in devices):
            return False
    mttr = facts["time_to_heal_s"]
    if mttr is not None and not (f"{mttr:g}" in text or f"{mttr:.1f}" in text):
        return False
    # An accurate cause/MTTR alone must not allow an invented 99.9% recovery metric.
    number = r"(?<![\w])\d+(?:\.\d+)?"
    known = {float(n) for n in re.findall(number, json.dumps(facts, default=str))}
    if any(float(n) not in known for n in re.findall(number, text)):
        return False
    # A past successful attempt must not turn a currently failed incident into a success.
    if not facts["fix_verified"]:
        affirmative = re.sub(
            r"\b(?:not|never|no longer)\s+(?:successfully\s+)?(?:healed|restored|recovered)",
            "",
            lower,
        )
        if re.search(
            r"\b(?:successfully healed|traffic (?:was )?restored|service (?:was )?recovered)\b",
            affirmative,
        ):
            return False
    return True


def _report(
    markdown: str, source: str, fallback_reason: str | None = None, provider: str | None = None
) -> dict:
    return {
        "markdown": markdown,
        "source": source,
        "provider": provider,
        "fallback_reason": fallback_reason,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def template_report(f: dict) -> str:
    root = f["root_cause"]
    before, after = f["affected_traffic_before"], f["affected_traffic_after"]
    recovery = (
        f"Verified recovery in {f['time_to_heal_s']:g} s."
        if f["fix_verified"] and f["time_to_heal_s"] is not None
        else "Recovery has not been verified for the current service state."
    )
    detection = (
        f"Detected in {f['time_to_detect_s']:g} s."
        if f["time_to_detect_s"] is not None
        else "Fault onset is unknown."
    )
    cause = root["cause"] if root else "A network problem"
    where = root["where"] if root else "the affected device"
    verified = "yes" if f["fix_verified"] else "no"
    lines = [
        "## Summary",
        f"{cause} at **{where}**. "
        f"{detection} {recovery} Status: {f['status']}.",
        "",
        "## Impact",
        *[f"- {a}" for a in f["alerts"]],
        "",
        "## Root cause",
    ]  # fmt: skip
    if root:
        lines += [
            f"{root['cause']} at **{root['where']}** "
            f"(ranking score {root['confidence_pct']}%; not a calibrated probability).",
            *[f"- {e}" for e in root["evidence"]],
        ]
    lines += [
        "",
        "## What NetHeal did",
        f"- Tested {f['fixes_considered_on_digital_twin']} candidate fixes on the digital twin "
        f"({f['fixes_blocked_by_safety_checks']} blocked by safety checks).",
        f"- {f['fix_applied'] or 'No fix applied.'}",
        f"- Fixes rolled back: {f['fixes_rolled_back']}. Verified: {verified}.",
        *[f"- {n}" for n in f["notes"]],
    ]  # fmt: skip
    if before and after:
        lines += [
            "",
            "## Results",
            "| Metric | Before | After | Normal |",
            "|---|---|---|---|",
            f"| Latency (ms) | {before['latency_ms']} | {after['latency_ms']} "
            f"| {after['baseline_latency_ms']} |",
            f"| Packet loss (%) | {before['loss_pct']} | {after['loss_pct']} | <1 |",
        ]  # fmt: skip
        lines += ["", f["metric_note"]]
        per_before, per_after = f.get("per_flow_before") or {}, f.get("per_flow_after") or {}
        if per_before and per_after:
            lines += [
                "",
                "### Flow evidence",
                "| Flow | Before latency / loss | After latency / loss | After delivered Mbps |",
                "|---|---|---|---|",
            ]
            for fid, row in per_after.items():
                previous = per_before.get(fid, {})

                def latency(sample):
                    return (
                        f"{sample['latency_ms']:.2f} ms"
                        if sample.get("reachable") and "latency_ms" in sample
                        else "unreachable"
                    )

                label = f.get("flow_names", {}).get(fid, fid).replace("|", "\\|")
                lines.append(
                    f"| {label} | {latency(previous)} / {previous.get('loss_pct', 0):.2f}% "
                    f"| {latency(row)} / {row.get('loss_pct', 0):.2f}% "
                    f"| {row.get('throughput_mbps', 0):.2f} |"
                )
    lines += [
        "",
        "## Recommendations",
        f"- Send a technician to inspect **{where}**.",
        ("- Keep the verified route while the physical fault is investigated."
         if f["fix_verified"] and f["fix_applied"] else
         "- Review the evidence and safety constraints before approving another action."),
    ]  # fmt: skip
    return "\n".join(lines)
