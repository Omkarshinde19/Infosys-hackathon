import asyncio
import json
from types import SimpleNamespace

from services.copilot.agent import TOOLS, Context, ask, run_tool
from services.copilot.rag import DocIndex
from tests.test_healer import Pipeline


def context() -> Context:
    p = Pipeline()
    p.inject("link_down", "dist1-library")
    p.run_until("healed", max_ticks=30)
    return Context(
        net=p.net, latest=p.latest, detector=p.det, rca=p.rca, incidents=p.incidents,
        ledger=SimpleNamespace(entries=[]), healer=p.healer, docs=DocIndex(None),
    )  # fmt: skip


def tool_call(name: str, args: dict | None = None, call_id: str = "c1"):
    fn = SimpleNamespace(name=name, arguments=json.dumps(args or {}))
    return SimpleNamespace(id=call_id, function=fn, model_dump=lambda: {"id": call_id})


class ScriptedLLM:
    """Replies with a fixed sequence of messages (tool calls or text)."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        content, calls = self.replies.pop(0)
        message = SimpleNamespace(content=content, tool_calls=calls)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def run(coro):
    return asyncio.run(coro)


def test_answer_uses_tools_and_cites_real_evidence():
    llm = ScriptedLLM(
        (None, [tool_call("get_diagnosis")]),
        ("The Library link failed [E1].", None),
    )
    result = run(ask("Why was the Library slow?", [], context(), llm, model="Llama-3.3-70B"))
    assert result["source"] == "llm:Llama-3.3-70B" and result["tools"] == ["get_diagnosis"]
    assert "E1" in result["evidence"] and "link_failure" in result["evidence"]["E1"]["text"]


def test_uncited_answer_is_rewritten_once():
    llm = ScriptedLLM(
        (None, [tool_call("get_active_alerts")]),
        ("Something broke.", None),
        ("The Library uplink is down [E1].", None),
    )
    result = run(ask("What's wrong?", [], context(), llm))
    assert result["source"].startswith("llm:") and "[E1]" in result["answer"]


def test_still_uncited_falls_back_to_evidence():
    llm = ScriptedLLM(
        (None, [tool_call("get_active_alerts")]),
        ("Something broke.", None),
        ("Still no sources.", None),
    )
    result = run(ask("What's wrong?", [], context(), llm))
    assert result["source"] == "template"
    assert result["fallback_reason"] == "AI answer did not cite its evidence"
    assert "[E" in result["answer"]


def test_offline_answer_still_cites_evidence():
    result = run(ask("Status?", [], context(), None))
    assert result["source"] == "template" and "Distribution North A ↔ Library" in result["answer"]


def test_what_if_tool_simulates_without_touching_the_network():
    ctx = context()
    routes = dict(ctx.net.routes)
    facts = json.loads(
        run(run_tool(ctx, "what_if", {"fault": "link_down", "target": "dist3-lab_cs"}))
    )
    assert any("automatically" in f["fact"] for f in facts)
    assert ctx.net.routes == routes


def test_docs_search_finds_how_detection_works():
    facts = json.loads(
        run(run_tool(context(), "search_docs", {"query": "isolation forest detector"}))
    )
    assert "Detection" in facts[0]["fact"]


def test_no_tool_can_change_the_network():
    names = {t["function"]["name"] for t in TOOLS}
    assert names.isdisjoint({"inject_fault", "reset", "approve", "set_autonomy", "set_route"})
