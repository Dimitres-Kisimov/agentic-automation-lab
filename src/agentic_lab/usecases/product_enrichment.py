"""product_enrichment.py — SECONDARY agentic use case: clean a messy product
record for the catalog (PIM).

Given a raw supplier record with missing/inconsistent fields, the agent decides
which fixes it needs: classify the category from the description, normalise the
fields, then validate the result against the catalog's required-field rules —
reporting anything a human still has to resolve.

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import json
from typing import Any

from .. import tools
from ..agent import Agent, ToolRegistry
from ..guardrails import GuardSet
from ..llm import LLMProvider, LLMResponse, ToolCall, make_provider

SYSTEM = (
    "You are a product-data steward for a distributor's catalog. Given a raw product "
    "record, determine its category, normalise its fields to house style, and validate "
    "it against the required fields. Use tools; do not guess values you can derive. "
    "Report clearly whether the record is catalog-ready or needs human review."
)


def build_registry() -> ToolRegistry:
    r = ToolRegistry()
    r.register("classify_category",
               "Assign a catalog category to a product from its description.",
               {"type": "object", "properties": {"description": {"type": "string"}},
                "required": ["description"]},
               tools.classify_category)
    r.register("normalize_fields",
               "Standardise a raw product record (casing, units, price format).",
               {"type": "object", "properties": {"record": {"type": "object"}},
                "required": ["record"]},
               tools.normalize_fields)
    r.register("validate_record",
               "Check a record against required fields and sanity rules.",
               {"type": "object", "properties": {"record": {"type": "object"}},
                "required": ["record"]},
               tools.validate_record)
    return r


def _results(messages: list[dict[str, Any]], name: str) -> list[Any]:
    return [json.loads(m["content"]) for m in messages
            if m["role"] == "tool" and m.get("name") == name]


def _record(messages: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        return json.loads(messages[0]["content"])
    except (json.JSONDecodeError, TypeError):
        return {"description": messages[0]["content"]}


def mock_policy(messages: list[dict[str, Any]], _tools: Any) -> LLMResponse:
    rec = _record(messages)
    cls = _results(messages, "classify_category")
    if not cls:
        desc = rec.get("description") or rec.get("name") or ""
        return LLMResponse(tool_calls=[ToolCall("c_cls", "classify_category",
                           {"description": desc})], stop_reason="tool_use")
    norm = _results(messages, "normalize_fields")
    if not norm:
        merged = dict(rec, category=cls[0]["category"])
        return LLMResponse(tool_calls=[ToolCall("c_norm", "normalize_fields",
                           {"record": merged})], stop_reason="tool_use")
    val = _results(messages, "validate_record")
    if not val:
        return LLMResponse(tool_calls=[ToolCall("c_val", "validate_record",
                           {"record": norm[0]["normalized"]})], stop_reason="tool_use")
    v = val[0]
    if v["valid"]:
        return LLMResponse(text=f"Record is catalog-ready (category: {cls[0]['category']}).",
                           stop_reason="end")
    problems = v["missing_fields"] + v["issues"]
    return LLMResponse(text=f"Record needs human review: {'; '.join(problems)}.", stop_reason="end")


def build_agent(provider: LLMProvider | None = None, max_steps: int = 12,
                guards: GuardSet | None = None) -> Agent:
    provider = provider or make_provider("mock", policy=mock_policy)
    return Agent(provider, build_registry(), SYSTEM, max_steps=max_steps, guards=guards)


def demo_input() -> str:
    return json.dumps({
        "name": "  m8x40   HEX bolt  zinc ", "brand": "wuerth", "uom": "pieces",
        "unit_price_eur": "0,89 EUR",
        "description": "M8x40 hex head bolt, zinc plated, DIN 933",
    })
