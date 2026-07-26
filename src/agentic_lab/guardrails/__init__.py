"""guardrails — typed input/loop/output guards for the agent tool-use loop.

Three stages, each guard a pure function returning a `GuardVerdict`:

    input   max_length, injection_screen         (screen, not a guarantee)
    loop    unknown_tool, tool_budget, repeated_call (loop breaker)
    output  schema_guard, refusal_detected

`GuardSet` bundles them with a config; `Agent(..., guards=GuardSet(...))` makes
the loop consult them and record every decision in `AgentRun.guard_events`.
Measured behaviour (catch + false-trigger rates) lives in eval/agent_eval.py.

Author: Dimitres Kisimov.
"""
from .guardset import QUOTE_SCHEMA, GuardConfig, GuardSet, default_guardset
from .input_guards import INJECTION_PATTERNS, injection_screen, max_length
from .loop_guards import repeated_call, tool_budget, unknown_tool
from .output_guards import refusal_detected, schema_guard, validate_schema
from .verdict import ALLOW, BLOCK, BREAK, FLAG, GuardVerdict

__all__ = [
    "ALLOW", "BLOCK", "BREAK", "FLAG", "GuardVerdict",
    "INJECTION_PATTERNS", "injection_screen", "max_length",
    "repeated_call", "tool_budget", "unknown_tool",
    "refusal_detected", "schema_guard", "validate_schema",
    "GuardConfig", "GuardSet", "QUOTE_SCHEMA", "default_guardset",
]
