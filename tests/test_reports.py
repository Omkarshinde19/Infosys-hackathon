import asyncio
from types import SimpleNamespace

import pytest

from services.llm.reports import entity_namer, incident_facts, template_report, write_report
from tests.test_healer import Pipeline


@pytest.fixture(scope="module")
def facts():
    p = Pipeline()
    p.inject("link_down", "dist1-library")
    p.run_until("healed", max_ticks=30)
    inc = p.incidents.current
    return incident_facts(inc, p.incidents.context[inc.id], entity_namer(p.net))


class FakeLLM:
    """Stands in for the OpenAI-compatible client; records the prompt."""

    def __init__(self, reply: str | None = None, error: Exception | None = None):
        self.reply, self.error, self.messages = reply, error, None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.messages = kwargs["messages"]
        if self.error:
            raise self.error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))]
        )


def run(coro):
    return asyncio.run(coro)


def test_facts_use_names_and_real_numbers(facts):
    assert facts["root_cause"]["where"] == "Distribution North A ↔ Library"
    assert facts["root_cause"]["cause"].startswith("Link failure")
    assert facts["time_to_heal_s"] == 4.5
    assert facts["affected_traffic_before"]["latency_ms"] == "unreachable"
    assert facts["fix_verified"] and "Rerouted traffic around" in facts["fix_applied"]


def test_grounded_llm_report_is_used(facts):
    reply = "## Summary\nLink failure at Distribution North A ↔ Library, healed in 4.5 s."
    llm = FakeLLM(reply)
    report = run(write_report(facts, llm, model="Llama-3.3-70B"))
    assert report["source"] == "llm:Llama-3.3-70B" and report["markdown"] == reply
    assert "Distribution North A ↔ Library" in llm.messages[1]["content"]  # facts sent


def test_ungrounded_llm_report_falls_back_to_template(facts):
    report = run(write_report(facts, FakeLLM("## Summary\nA router in Mumbai failed.")))
    assert report["source"] == "template"
    assert report["fallback_reason"] == "AI draft failed the grounding check"


def test_llm_error_falls_back_to_template(facts):
    report = run(write_report(facts, FakeLLM(error=ConnectionError("offline"))))
    assert report["source"] == "template"
    assert "ConnectionError" in report["fallback_reason"]


def test_no_credentials_uses_template(facts):
    report = run(write_report(facts, None))
    assert report["source"] == "template"
    md = report["markdown"]
    assert "Distribution North A ↔ Library" in md and "4.5 s" in md
    assert "| Latency (ms) | unreachable |" in md


def test_template_covers_every_section(facts):
    md = template_report(facts)
    for section in [
        "Summary",
        "Impact",
        "Root cause",
        "What NetHeal did",
        "Results",
        "Recommendations",
    ]:
        assert f"## {section}" in md


def test_grounding_accepts_paraphrased_names_but_needs_cause_and_mttr(facts):
    paraphrase = (
        "Link failure on the link between Distribution North A and Library; "
        "NetHeal healed it in 4.5 seconds."
    )
    assert run(write_report(facts, FakeLLM(paraphrase)))["source"].startswith("llm:")
    wrong_cause = "Congestion between Distribution North A and Library, healed in 4.5 seconds."
    assert run(write_report(facts, FakeLLM(wrong_cause)))["source"] == "template"
    wrong_time = "Link failure between Distribution North A and Library, healed in 9 seconds."
    assert run(write_report(facts, FakeLLM(wrong_time)))["source"] == "template"
