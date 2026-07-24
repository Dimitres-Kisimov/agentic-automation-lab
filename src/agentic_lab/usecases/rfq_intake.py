"""rfq_intake.py — FLAGSHIP agentic use case: RFQ / order-email -> quote.

A distributor like Würth receives thousands of unstructured order/RFQ emails.
This agent reads one, and then *decides on its own* which tools to call, in what
order, and how many times:

    parse the email  ->  look up each line item in the catalog  ->
    check stock for each  ->  draft a customer quote  ->  summarise.

The number of lookup/stock calls depends on how many items the email contains —
so this is genuinely *agentic* (the model drives control flow), not a fixed
pipeline. The deterministic mock policy below reproduces exactly that behaviour
without an API key, so it runs anywhere and is unit-testable.

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .. import tools
from ..agent import Agent, ToolRegistry
from ..llm import LLMProvider, LLMResponse, ToolCall, make_provider

SYSTEM = (
    "You are an order-intake agent for an industrial distributor. Given a customer "
    "RFQ email, resolve every requested line item to a catalog SKU, check stock, and "
    "produce a priced quote. Call tools one step at a time; never invent SKUs or "
    "prices — always look them up. When the quote is drafted, summarise it briefly."
)

_SAMPLE = Path(__file__).resolve().parents[3] / "data" / "sample_emails" / "rfq_01.txt"


def build_registry() -> ToolRegistry:
    r = ToolRegistry()
    r.register("parse_email",
               "Extract the customer and requested line items (description + qty) from a raw RFQ email.",
               {"type": "object", "properties": {"raw_email": {"type": "string"}},
                "required": ["raw_email"]},
               tools.parse_email)
    r.register("lookup_sku",
               "Resolve one free-text line item to the best-matching catalog SKU (with price).",
               {"type": "object", "properties": {"description": {"type": "string"}},
                "required": ["description"]},
               tools.lookup_sku)
    r.register("check_stock",
               "Check availability and lead time for a SKU at a requested quantity.",
               {"type": "object", "properties": {"sku": {"type": "string"},
                                                 "qty": {"type": "integer"}},
                "required": ["sku"]},
               tools.check_stock)
    r.register("draft_quote",
               "Build a priced customer quote from resolved line items.",
               {"type": "object", "properties": {
                   "customer": {"type": "string"},
                   "line_items": {"type": "array", "items": {"type": "object"}}},
                "required": ["customer", "line_items"]},
               tools.draft_quote)
    return r


def _results(messages: list[dict[str, Any]], name: str) -> list[Any]:
    return [json.loads(m["content"]) for m in messages
            if m["role"] == "tool" and m.get("name") == name]


def mock_policy(messages: list[dict[str, Any]], _tools: Any) -> LLMResponse:
    """Deterministic reproduction of the agent's decisions — reads the transcript
    and returns the next tool call (or the final summary)."""
    parsed = _results(messages, "parse_email")
    if not parsed:
        raw = messages[0]["content"]
        return LLMResponse(tool_calls=[ToolCall("c_parse", "parse_email", {"raw_email": raw})],
                           stop_reason="tool_use")
    info = parsed[0]
    items = info.get("items", [])
    lookups = _results(messages, "lookup_sku")
    if len(lookups) < len(items):
        i = len(lookups)
        return LLMResponse(tool_calls=[ToolCall(f"c_look{i}", "lookup_sku",
                           {"description": items[i]["description"]})], stop_reason="tool_use")
    stocks = _results(messages, "check_stock")
    if len(stocks) < len(items):
        i = len(stocks)
        sku = lookups[i].get("sku") if lookups[i].get("matched") else None
        return LLMResponse(tool_calls=[ToolCall(f"c_stock{i}", "check_stock",
                           {"sku": sku or "MISSING", "qty": items[i]["qty"]})],
                           stop_reason="tool_use")
    quotes = _results(messages, "draft_quote")
    if not quotes:
        line_items = [{"sku": lookups[i].get("sku"), "description": items[i]["description"],
                       "qty": items[i]["qty"], "unit_price_eur": lookups[i].get("unit_price_eur", 0.0)}
                      for i in range(len(items))]
        return LLMResponse(tool_calls=[ToolCall("c_quote", "draft_quote",
                           {"customer": info.get("customer", "unknown"), "line_items": line_items})],
                           stop_reason="tool_use")
    q = quotes[0]
    unmatched = [ln["description"] for ln in q["line_items"] if not ln.get("sku")]
    note = f" ({len(unmatched)} item(s) need manual review: {', '.join(unmatched)})" if unmatched else ""
    return LLMResponse(
        text=(f"Quote {q['quote_id']} drafted for {q['customer']}: {len(q['line_items'])} line "
              f"item(s), total {q['total_eur']:.2f} EUR excl. VAT.{note}"),
        stop_reason="end")


def build_agent(provider: LLMProvider | None = None, max_steps: int = 20) -> Agent:
    provider = provider or make_provider("mock", policy=mock_policy)
    return Agent(provider, build_registry(), SYSTEM, max_steps=max_steps)


def demo_input() -> str:
    if _SAMPLE.exists():
        return _SAMPLE.read_text(encoding="utf-8")
    return ("From: procurement@acme-bau.de\nSubject: RFQ spring order\n\n"
            "Hello, please quote:\n10 x M8x40 hex bolts zinc\n4 x cordless impact driver 18V\n"
            "20 x cut-resistant gloves size L\nBest regards, ACME Bau")
