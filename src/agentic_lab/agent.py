"""agent.py — the agentic tool-use loop.

This is the "agentic" core the Würth role is about (Anthropic's definition:
*agents dynamically direct their own process and tool usage*, vs. workflows that
run predefined code paths). The loop:

    1. send the transcript + tool specs to the LLM
    2. if the LLM asks for a tool -> execute it, append the result, loop
    3. if the LLM answers in text -> stop and return the run

The same loop backs both use cases and both providers (mock / Claude). Every run
is fully instrumented (steps, tool calls, latency, tokens) so the benchmark can
compare it fairly against the n8n low-code build.

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .guardrails import GuardSet, GuardVerdict
from .llm import LLMProvider, LLMResponse, ToolSpec


# --------------------------------------------------------------------------- #
# Tool registry
# --------------------------------------------------------------------------- #
@dataclass
class Tool:
    spec: ToolSpec
    fn: Callable[..., Any]


class ToolRegistry:
    """Holds the tools an agent may call and dispatches by name."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, name: str, description: str, input_schema: dict[str, Any],
                 fn: Callable[..., Any]) -> None:
        self._tools[name] = Tool(ToolSpec(name, description, input_schema), fn)

    def tool(self, name: str, description: str, input_schema: dict[str, Any]):
        """Decorator form of register()."""
        def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.register(name, description, input_schema, fn)
            return fn
        return deco

    @property
    def specs(self) -> list[ToolSpec]:
        return [t.spec for t in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self._tools:
            return {"error": f"unknown tool {name!r}"}
        try:
            return self._tools[name].fn(**arguments)
        except Exception as exc:  # tools never crash the loop — the model sees the error
            return {"error": f"{type(exc).__name__}: {exc}"}


# --------------------------------------------------------------------------- #
# Run record — everything the benchmark needs
# --------------------------------------------------------------------------- #
@dataclass
class AgentRun:
    final: str
    messages: list[dict[str, Any]]
    steps: int                       # LLM turns taken
    tool_calls: list[str]            # tool names in call order
    latency_s: float
    input_tokens: int
    output_tokens: int
    stopped: str                     # "answered" | "max_steps" | "input_blocked" | "guard_break"
    state: dict[str, Any] = field(default_factory=dict)  # accumulated tool outputs
    guard_events: list[dict[str, Any]] = field(default_factory=list)  # every guard decision

    def summary(self) -> dict[str, Any]:
        return {
            "steps": self.steps, "tool_calls": self.tool_calls,
            "n_tool_calls": len(self.tool_calls), "latency_s": round(self.latency_s, 4),
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "stopped": self.stopped,
            "guards_triggered": sum(1 for e in self.guard_events if e["triggered"]),
        }


class Agent:
    """Runs the tool-use loop for a given provider + tool registry."""

    def __init__(self, provider: LLMProvider, registry: ToolRegistry,
                 system: str, max_steps: int = 12, guards: GuardSet | None = None) -> None:
        self.provider = provider
        self.registry = registry
        self.system = system
        self.max_steps = max_steps
        self.guards = guards  # optional — None keeps the loop exactly as before

    def run(self, user_input: str, on_event: Callable[[str, Any], None] | None = None) -> AgentRun:
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_input}]
        tool_calls: list[str] = []
        call_history: list[tuple[str, str]] = []   # (tool, canonical-args) per attempt
        guard_events: list[dict[str, Any]] = []
        state: dict[str, Any] = {}
        in_tok = out_tok = steps = 0
        t0 = time.perf_counter()
        emit = on_event or (lambda *_: None)

        def record(verdicts: list[GuardVerdict]) -> GuardVerdict | None:
            """Trace every guard decision; return the verdict to act on
            (break outranks block; allow/flag never interrupt)."""
            for v in verdicts:
                guard_events.append(v.as_dict())
                emit("guard", v.as_dict())
            for action in ("break", "block"):
                for v in verdicts:
                    if v.triggered and v.action == action:
                        return v
            return None

        def finish(final: str, stopped: str) -> AgentRun:
            return AgentRun(final=final, messages=messages, steps=steps,
                            tool_calls=tool_calls, latency_s=time.perf_counter() - t0,
                            input_tokens=in_tok, output_tokens=out_tok,
                            stopped=stopped, state=state, guard_events=guard_events)

        if self.guards is not None:
            hit = record(self.guards.check_input(user_input))
            if hit is not None:
                return finish(f"Input rejected by guard [{hit.guard}]: {hit.reason}. "
                              "Routed to human review.", "input_blocked")

        known_tools = {s.name for s in self.registry.specs}

        while steps < self.max_steps:
            steps += 1
            resp: LLMResponse = self.provider.complete(self.system, messages, self.registry.specs)
            in_tok += resp.input_tokens
            out_tok += resp.output_tokens

            if resp.tool_calls:
                messages.append({"role": "assistant", "content": resp.text,
                                 "tool_calls": resp.tool_calls})
                for tc in resp.tool_calls:
                    emit("tool_call", {"name": tc.name, "arguments": tc.arguments})
                    hit = None
                    if self.guards is not None:
                        hit = record(self.guards.check_tool_call(
                            tc.name, tc.arguments, known_tools, call_history))
                        call_history.append(
                            (tc.name, json.dumps(tc.arguments, sort_keys=True, default=str)))
                    if hit is not None and hit.action == "break":
                        return finish(f"(stopped by guard [{hit.guard}]: {hit.reason})",
                                      "guard_break")
                    if hit is not None:  # "block": refuse this call, let the model see why
                        result: Any = {"error": f"call rejected by guard [{hit.guard}]: {hit.reason}"}
                    else:
                        result = self.registry.execute(tc.name, tc.arguments)
                        state[tc.name] = result
                    tool_calls.append(tc.name)
                    emit("tool_result", {"name": tc.name, "result": result})
                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "name": tc.name, "content": json.dumps(result, default=str)})
                continue

            # No tool call -> the agent has answered.
            messages.append({"role": "assistant", "content": resp.text})
            if self.guards is not None:
                record(self.guards.check_output(resp.text or "", state))  # flags only
            emit("final", resp.text)
            return finish(resp.text or "", "answered")

        return finish("(stopped: reached max_steps)", "max_steps")


def last_tool_result(messages: list[dict[str, Any]], tool_name: str) -> Any:
    """Helper used by mock plans to thread a prior tool's output into the next
    tool's arguments — reads the transcript, so it works for any provider."""
    for m in reversed(messages):
        if m["role"] == "tool" and m.get("name") == tool_name:
            return json.loads(m["content"])
    return None
