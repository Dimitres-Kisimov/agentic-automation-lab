"""loop_guards.py — checks that run on EVERY tool call inside the agent loop.

  * unknown_tool  — the model asked for a tool that is not registered; the call
                    is blocked (never executed) and the model sees the rejection.
  * tool_budget   — hard cap on tool-call attempts per run; a runaway agent is
                    stopped even if max_steps is generous.
  * repeated_call — loop breaker: N identical consecutive calls (same tool, same
                    arguments) means the agent is stuck, so the run is broken
                    rather than burning the rest of the budget.

All three are pure functions of the call history, so they are trivially
unit-testable and the same code path serves the live loop and the eval.

Author: Dimitres Kisimov.
"""
from __future__ import annotations

from collections.abc import Collection, Sequence

from .verdict import BLOCK, BREAK, GuardVerdict, allow

DEFAULT_TOOL_BUDGET = 25
DEFAULT_REPEAT_LIMIT = 3

# A call-history entry is (tool_name, canonical_json_of_arguments).
HistoryEntry = tuple[str, str]


def unknown_tool(name: str, known: Collection[str]) -> GuardVerdict:
    """Reject calls to tools that are not registered for this agent."""
    if name not in known:
        return GuardVerdict("loop.unknown_tool", "loop", True, BLOCK,
                            f"tool {name!r} is not registered for this agent")
    return allow("loop.unknown_tool", "loop", f"{name!r} is a registered tool")


def tool_budget(n_prior_calls: int, budget: int = DEFAULT_TOOL_BUDGET) -> GuardVerdict:
    """Break the run once `budget` tool-call attempts have been made."""
    if n_prior_calls >= budget:
        return GuardVerdict("loop.tool_budget", "loop", True, BREAK,
                            f"tool-call budget of {budget} exhausted")
    return allow("loop.tool_budget", "loop", f"{n_prior_calls}/{budget} calls used")


def repeated_call(history: Sequence[HistoryEntry], name: str, args_json: str,
                  limit: int = DEFAULT_REPEAT_LIMIT) -> GuardVerdict:
    """Break the run when this call would be the `limit`-th identical
    consecutive call (same tool AND same arguments) — the classic stuck loop."""
    entry: HistoryEntry = (name, args_json)
    window = history[-(limit - 1):] if limit >= 2 else []
    if limit >= 2 and len(window) == limit - 1 and all(h == entry for h in window):
        return GuardVerdict("loop.repeated_call", "loop", True, BREAK,
                            f"identical call to {name!r} attempted {limit} times in a row")
    return allow("loop.repeated_call", "loop", "no identical-call loop detected")
