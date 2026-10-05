"""Ask NetHeal: a read-only, tool-using assistant that cites its evidence.

The LLM (Llama-3.3-70B on Qualcomm Cloud AI) decides which tools to call. Every fact a tool
returns is registered as evidence with an ID (E1, E2, ...) and the answer must cite those IDs.
An answer without valid citations is sent back once for a rewrite; if it still has none (or
the AI is unreachable) a deterministic answer built from the evidence is returned instead.
No tool can change the network.
"""

import asyncio
import json
import re
from dataclasses import dataclass, field

from services.copilot.rag import DocIndex
from services.healer.whatif import what_if
from services.llm.reports import MODEL, entity_namer

MAX_ROUNDS = 4
TIMEOUT_S = 40

SYSTEM_PROMPT = """You are "Ask NetHeal", the assistant of NetHeal, a self-healing campus \
network platform. Answer questions about the live network, alerts, diagnoses, incidents, the \
audit log, how NetHeal works, and what-if scenarios.

Rules:
- Use the tools to look things up; never guess.
- Every factual sentence must cite evidence IDs exactly as the tools give them, like [E3].
  Never invent an ID.
- You are read-only. If asked to change the network, explain that an operator can do that
  in the Fault Lab or on the Approvals page.
- Plain English for a non-technical manager, at most 150 words. Use device names as given."""


def _tool(name: str, description: str, **params) -> dict:
    props = {k: {"type": t, "description": d} for k, (t, d) in params.items()}
    schema = {"type": "object", "properties": props, "required": list(params)}
    function = {"name": name, "description": description, "parameters": schema}
    return {"type": "function", "function": function}


TOOLS = [
    _tool("get_network_status", "Current health of every traffic flow and link."),
    _tool("get_active_alerts", "Alerts the detectors are raising right now."),
    _tool("get_diagnosis", "Current root-cause diagnosis with confidence and evidence."),
    _tool("list_incidents", "The most recent incidents NetHeal handled."),
    _tool(
        "get_incident",
        "Timeline, fix and results of one incident.",
        incident_id=("string", "Incident id or its first 8 characters"),
    ),  # fmt: skip
    _tool("get_audit_log", "Most recent entries of the tamper-evident audit log."),
    _tool(
        "search_docs",
        "Search NetHeal's documentation (how it works, ML, safety rules).",
        query=("string", "What to look for"),
    ),  # fmt: skip
    _tool(
        "what_if",
        "Simulate a fault on a digital twin (never the real network): impact + planned fix.",
        fault=(
            "string",
            "link_down | gray_failure | congestion | flapping | node_overload | misconfig",
        ),
        target=("string", "Link id (e.g. dist1-library), node id (e.g. core1) or flow id"),
    ),  # fmt: skip
]


@dataclass
class Context:
    """Read-only view of the engine's state."""

    net: object
    latest: dict
    detector: object
    rca: object
    incidents: object
    ledger: object
    healer: object
    docs: DocIndex
    evidence: dict = field(default_factory=dict)

    def cite(self, kind: str, text: str) -> str:
        eid = f"E{len(self.evidence) + 1}"
        self.evidence[eid] = {"kind": kind, "text": text}
        return eid


def _items(ctx: Context, kind: str, texts: list[str]) -> str:
    if not texts:
        texts = ["Nothing to report."]
    return json.dumps([{"id": ctx.cite(kind, t), "fact": t} for t in texts], ensure_ascii=False)


async def run_tool(ctx: Context, name: str, args: dict) -> str:
    name_of = entity_namer(ctx.net)
    if name == "get_network_status":
        facts = []
        for f in ctx.net.flows:
            s = ctx.latest.get(f)
            if s is None:
                continue
            state = "unreachable" if s.latency_ms is None else f"{s.latency_ms:.1f} ms latency"
            facts.append(f"{name_of(f)}: {state}, {s.loss_pct:.2f}% packet loss")
        down = [name_of(lid) for lid in ctx.net.links
                if ctx.latest.get(lid) and ctx.latest[lid].latency_ms is None]  # fmt: skip
        facts.append(f"Links down: {', '.join(down) if down else 'none'}")
        return _items(ctx, "status", facts)
    if name == "get_active_alerts":
        return _items(ctx, "alert", [
            f"{name_of(a.entity_id)}: {a.metric} {a.value:.2f} (normal {a.baseline:.2f}), "
            f"{a.severity}, detected by {', '.join(a.detectors)}"
            for a in ctx.detector.active.values()
        ])  # fmt: skip
    if name == "get_diagnosis":
        return _items(ctx, "diagnosis", [
            f"{h.cause} at {name_of(h.target)}, {h.confidence:.0%} confident. Evidence: "
            + "; ".join(e.description for e in h.evidence)
            for h in ctx.rca.hypotheses[:3]
        ])  # fmt: skip
    if name == "list_incidents":
        recent = [
            *ctx.incidents.history,
            *([ctx.incidents.current] if ctx.incidents.current else []),
        ]
        facts = []
        for inc in recent[::-1][:5]:
            top = ctx.incidents.context[inc.id]["diagnosis"][:1]
            what = f"{top[0].cause} at {name_of(top[0].target)}" if top else "undiagnosed"
            facts.append(f"Incident {inc.id[:8]} ({inc.opened_at:%H:%M:%S}): {what}, {inc.status}, "
                         f"detected in {inc.mttd_s}s, healed in {inc.mttr_s}s")  # fmt: skip
        return _items(ctx, "incident", facts)
    if name == "get_incident":
        key = str(args.get("incident_id", ""))[:8]
        inc = next((i for i in [ctx.incidents.current, *ctx.incidents.history]
                    if i and i.id.startswith(key)), None)  # fmt: skip
        if inc is None:
            return _items(ctx, "incident", [f"No incident matches {key!r}."])
        facts = [f"{e.stage} at {e.ts:%H:%M:%S}" for e in inc.timeline]
        for a in ctx.incidents.context[inc.id]["actions"]:
            if a["kind"] == "result":
                r = a["payload"]
                outcome = "verified" if r.verified else "rolled back"
                facts.append(
                    f"Fix {outcome}: latency {r.before['latency_ms']:.1f} → "
                    f"{r.after['latency_ms']:.1f} ms, loss {r.before['loss_pct']:.1f}% → "
                    f"{r.after['loss_pct']:.2f}%"
                )
        return _items(ctx, "incident", facts)
    if name == "get_audit_log":
        return _items(ctx, "audit", [
            f"#{e.seq} {e.ts:%H:%M:%S} {e.actor} {e.event_type} {json.dumps(e.payload)[:120]}"
            for e in ctx.ledger.entries[-10:]
        ])  # fmt: skip
    if name == "search_docs":
        found = await ctx.docs.search(str(args.get("query", "")))
        return _items(ctx, "doc", [f"[{d['source']}] {d['text'][:600]}" for d in found])
    if name == "what_if":
        try:
            r = what_if(ctx.net, ctx.healer, str(args.get("fault")), str(args.get("target")))
        except (ValueError, KeyError) as e:
            return _items(ctx, "what-if", [f"Can't simulate that: {e}"])
        facts = [
            f"What-if {args.get('fault')} on {name_of(str(args.get('target')))}: {r['verdict']}"
        ]
        facts += [f"{name_of(i['flow'])} would see {i['loss_during_pct']}% loss and "
                  f"{i['latency_during_ms']} ms latency" for i in r["impact"]]  # fmt: skip
        if r["best"]:
            facts.append(f"Planned fix: {r['best'].type} with twin-predicted "
                         f"{r['best'].twin_prediction.latency_ms:.1f} ms latency")  # fmt: skip
        return _items(ctx, "what-if", facts)
    return _items(ctx, "error", [f"Unknown tool {name}"])


def _cited(text: str, ctx: Context) -> set[str]:
    return set(re.findall(r"\[(E\d+)\]", text)) & ctx.evidence.keys()


async def fallback(ctx: Context, reason: str) -> dict:
    """No usable AI answer: state the facts directly, still with citations."""
    lines = []
    for tool in ("get_active_alerts", "get_diagnosis"):
        for item in json.loads(await run_tool(ctx, tool, {})):
            lines.append(f"- {item['fact']} [{item['id']}]")
    text = "Here is what NetHeal can see right now:\n\n" + "\n".join(lines)
    return {"answer": text, "evidence": ctx.evidence,
            "tools": ["get_active_alerts", "get_diagnosis"], "source": "template",
            "fallback_reason": reason}  # fmt: skip


async def ask(question: str, history: list[dict], ctx: Context, client, model: str = MODEL) -> dict:
    if client is None:
        return await fallback(ctx, "No AI credentials configured")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history[-6:],
                {"role": "user", "content": question}]  # fmt: skip
    used: list[str] = []
    try:
        for _ in range(MAX_ROUNDS):
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model, messages=messages, tools=TOOLS, max_tokens=500, temperature=0.1
                ),  # fmt: skip
                timeout=TIMEOUT_S,
            )
            msg = response.choices[0].message
            if not msg.tool_calls:
                break
            messages.append({"role": "assistant", "content": msg.content or "",
                             "tool_calls": [c.model_dump() for c in msg.tool_calls]})  # fmt: skip
            for call in msg.tool_calls:
                used.append(call.function.name)
                args = json.loads(call.function.arguments or "{}")
                result = await run_tool(ctx, call.function.name, args)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
        answer = (msg.content or "").strip()
        if ctx.evidence and not _cited(answer, ctx):  # one chance to fix missing citations
            messages += [{"role": "assistant", "content": answer},
                         {"role": "user", "content": "Rewrite that answer citing the evidence "
                          "IDs from the tool results in square brackets, like [E1]."}]  # fmt: skip
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model, messages=messages, max_tokens=500, temperature=0.1
                ),  # fmt: skip
                timeout=TIMEOUT_S,
            )
            answer = (response.choices[0].message.content or "").strip()
        if ctx.evidence and not _cited(answer, ctx):
            return await fallback(ctx, "AI answer did not cite its evidence")
    except Exception as e:  # network, auth, timeout, malformed tool call
        return await fallback(ctx, f"AI unavailable ({type(e).__name__})")
    cited = _cited(answer, ctx)
    return {"answer": answer, "evidence": {k: v for k, v in ctx.evidence.items() if k in cited},
            "tools": used, "source": f"llm:{model}", "fallback_reason": None}  # fmt: skip
