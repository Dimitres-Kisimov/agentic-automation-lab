"""llm.py — provider-agnostic LLM interface for the agentic tool-use loop.

Two providers implement the same tiny contract:

  * MockProvider     — deterministic, stdlib-only. Drives the agent loop from a
                       scripted plan so the whole system runs, tests and CI stay
                       key-free, and behaviour is reproducible. (default)
  * AnthropicProvider — real Claude tool-use. Optional; needs ANTHROPIC_API_KEY.

The point of the abstraction: the AGENT (agent.py) never knows which provider it
is talking to. Swapping mock <-> Claude is one env var. This is also what makes
the low-code/full-code benchmark fair — both sides call the same model contract.

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


# --------------------------------------------------------------------------- #
# Wire types — a minimal, provider-neutral shape for tools and responses.
# --------------------------------------------------------------------------- #
@dataclass
class ToolSpec:
    """A tool the model may call. `input_schema` is JSON Schema."""
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """One turn from the model: either free text, or one/more tool calls."""
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end"          # "tool_use" | "end"
    input_tokens: int = 0
    output_tokens: int = 0


class LLMProvider(Protocol):
    def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]
    ) -> LLMResponse: ...


# --------------------------------------------------------------------------- #
# Mock provider — deterministic agentic behaviour from a scripted plan.
# --------------------------------------------------------------------------- #
@dataclass
class MockStep:
    """One planned tool call. `args` builds arguments from the running history,
    so the mock threads real values (parsed emails, SKU hits) between steps —
    exactly like a real agent would, but reproducibly."""
    tool: str
    args: Callable[[list[dict[str, Any]]], dict[str, Any]]


class MockProvider:
    """Deterministic stand-in for an agentic model. Two modes:

    * `policy(messages, tools) -> LLMResponse` — a full decision function that
      reads the transcript and returns the next action (tool call or final).
      Use this when the number/order of tool calls depends on the data (e.g.
      one SKU lookup per parsed line item) — the genuinely agentic case.
    * `plan` + `finalize` — a fixed ordered list of tool calls followed by a
      summary. Use this for stable, known step structures.

    Either way the provider is a pure function of the message history, so runs
    are reproducible and unit-testable without any API key."""

    def __init__(
        self,
        plan: list[MockStep] | None = None,
        finalize: Callable[[list[dict[str, Any]]], str] | None = None,
        policy: Callable[[list[dict[str, Any]], list[ToolSpec]], LLMResponse] | None = None,
    ) -> None:
        self.plan = plan or []
        self.finalize = finalize or (lambda _hist: "Done.")
        self.policy = policy

    def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]
    ) -> LLMResponse:
        if self.policy is not None:
            resp = self.policy(messages, tools)
            if resp.tool_calls:
                valid = {t.name for t in tools}
                for tc in resp.tool_calls:
                    if tc.name not in valid:
                        raise ValueError(f"mock policy called unknown tool {tc.name!r}")
            if not resp.input_tokens:
                resp.input_tokens = sum(len(json.dumps(m, default=str)) for m in messages) // 4
            if not resp.output_tokens:
                resp.output_tokens = 40 if resp.tool_calls else len(resp.text or "") // 4
            return resp

        done = sum(1 for m in messages if m["role"] == "assistant" and m.get("tool_calls"))
        if done < len(self.plan):
            step = self.plan[done]
            valid = {t.name for t in tools}
            if step.tool not in valid:
                raise ValueError(f"mock plan calls unknown tool {step.tool!r}")
            call = ToolCall(id=f"call_{done}", name=step.tool, arguments=step.args(messages))
            ctx = sum(len(json.dumps(m, default=str)) for m in messages)
            return LLMResponse(tool_calls=[call], stop_reason="tool_use",
                               input_tokens=ctx // 4, output_tokens=40)
        text = self.finalize(messages)
        return LLMResponse(text=text, stop_reason="end",
                           input_tokens=200, output_tokens=len(text) // 4)


# --------------------------------------------------------------------------- #
# Anthropic provider — real Claude tool-use (optional).
# --------------------------------------------------------------------------- #
class AnthropicProvider:
    """Thin wrapper over the Anthropic Messages API tool-use loop. Imported
    lazily so the package installs and tests run without the SDK or a key."""

    def __init__(self, model: str | None = None) -> None:
        try:
            import anthropic  # noqa: F401
        except ImportError as e:  # pragma: no cover - only hit without the extra
            raise RuntimeError(
                "anthropic not installed. `pip install anthropic` or use LLM_PROVIDER=mock"
            ) from e
        import anthropic
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]
    ) -> LLMResponse:  # pragma: no cover - exercised only with a live key
        api_msgs = _to_anthropic(messages)
        api_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]
        resp = self._client.messages.create(
            model=self.model, system=system, tools=api_tools,
            messages=api_msgs, max_tokens=1024,
        )
        calls, text = [], None
        for block in resp.content:
            if block.type == "text":
                text = (text or "") + block.text
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input)))
        return LLMResponse(
            text=text, tool_calls=calls,
            stop_reason="tool_use" if calls else "end",
            input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens,
        )


def _to_anthropic(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:  # pragma: no cover
    """Translate our neutral transcript into Anthropic content blocks."""
    out: list[dict[str, Any]] = []
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            content: list[dict[str, Any]] = []
            if m.get("content"):
                content.append({"type": "text", "text": m["content"]})
            for tc in m.get("tool_calls", []):
                content.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments})
            out.append({"role": "assistant", "content": content})
        elif m["role"] == "tool":
            out.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
            ]})
    return out


def make_provider(name: str | None = None, **kw: Any) -> LLMProvider:
    """Factory driven by LLM_PROVIDER (or an explicit name). Mock is the default
    so nothing external is required to run the lab."""
    name = (name or os.environ.get("LLM_PROVIDER", "mock")).lower()
    if name == "anthropic":
        return AnthropicProvider(**kw)
    if name == "mock":
        return MockProvider(plan=kw.get("plan"), finalize=kw.get("finalize"),
                            policy=kw.get("policy"))
    raise ValueError(f"unknown LLM provider {name!r} (use 'mock' or 'anthropic')")
