"""End-to-end tests of the agentic loop (mock provider) for both use cases —
these are the 'it actually works' gates, key-free and deterministic."""
from agentic_lab.usecases import product_enrichment, rfq_intake


def test_rfq_intake_converges_and_quotes():
    run = rfq_intake.build_agent().run(rfq_intake.demo_input())
    assert run.stopped == "answered"
    # genuinely agentic: one lookup + one stock check per line item, then a quote
    assert run.tool_calls[0] == "parse_email"
    assert run.tool_calls.count("lookup_sku") == 5
    assert run.tool_calls.count("check_stock") == 5
    assert run.tool_calls[-1] == "draft_quote"
    quote = run.state["draft_quote"]
    assert quote["total_eur"] > 0
    assert "EUR" in run.final


def test_rfq_flags_off_catalog_item():
    email = ("From: x@y.de\nSubject: rfq\n\n"
             "5 x titanium coated left-handed drill bit 3mm\n10 x M8x40 hex bolts zinc")
    run = rfq_intake.build_agent().run(email)
    assert "manual review" in run.final.lower()


def test_product_enrichment_ready():
    run = product_enrichment.build_agent().run(product_enrichment.demo_input())
    assert run.stopped == "answered"
    assert run.tool_calls == ["classify_category", "normalize_fields", "validate_record"]
    assert "catalog-ready" in run.final.lower()


def test_agent_respects_max_steps():
    # A pathological policy that never finishes must stop cleanly, not hang.
    from agentic_lab.agent import Agent, ToolRegistry
    from agentic_lab.llm import LLMResponse, MockProvider, ToolCall

    reg = ToolRegistry()
    reg.register("noop", "does nothing", {"type": "object", "properties": {}}, lambda: {"ok": True})
    provider = MockProvider(policy=lambda *_: LLMResponse(
        tool_calls=[ToolCall("c", "noop", {})], stop_reason="tool_use"))
    run = Agent(provider, reg, "loop forever", max_steps=5).run("go")
    assert run.stopped == "max_steps"
    assert run.steps == 5
