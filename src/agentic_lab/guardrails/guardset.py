"""guardset.py — the bundle of guards the agent loop consults at each stage.

The loop calls exactly three hooks:

    check_input(text)                      before the first LLM turn
    check_tool_call(name, args, known, h)  before EVERY tool execution
    check_output(final_text, state)        after the final answer

Each hook returns the verdicts of ALL its guards — triggered or not — and the
loop records every one of them in the run trace (`AgentRun.guard_events`).
That is what lets eval/agent_eval.py measure catch AND false-trigger rates.

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from . import input_guards, loop_guards, output_guards
from .loop_guards import HistoryEntry
from .verdict import GuardVerdict, allow

# The structured payload a finished RFQ run must contain (state["draft_quote"]).
QUOTE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["quote_id", "customer", "line_items", "total_eur"],
    "properties": {
        "quote_id": {"type": "string"},
        "customer": {"type": "string"},
        "line_items": {"type": "array", "items": {"type": "object"}},
        "total_eur": {"type": "number"},
    },
}


@dataclass
class GuardConfig:
    max_input_chars: int = input_guards.DEFAULT_MAX_INPUT_CHARS
    tool_budget: int = loop_guards.DEFAULT_TOOL_BUDGET
    repeat_limit: int = loop_guards.DEFAULT_REPEAT_LIMIT
    # When set, the final answer must have produced state[output_state_key]
    # matching output_schema — otherwise the schema guard flags the run.
    output_state_key: str | None = None
    output_schema: dict[str, Any] | None = None


class GuardSet:
    def __init__(self, config: GuardConfig | None = None) -> None:
        self.config = config or GuardConfig()

    def check_input(self, text: str) -> list[GuardVerdict]:
        c = self.config
        return [input_guards.max_length(text, c.max_input_chars),
                input_guards.injection_screen(text)]

    def check_tool_call(self, name: str, arguments: dict[str, Any],
                        known_tools: set[str],
                        history: list[HistoryEntry]) -> list[GuardVerdict]:
        c = self.config
        args_json = json.dumps(arguments, sort_keys=True, default=str)
        return [loop_guards.unknown_tool(name, known_tools),
                loop_guards.tool_budget(len(history), c.tool_budget),
                loop_guards.repeated_call(history, name, args_json, c.repeat_limit)]

    def check_output(self, final_text: str, state: dict[str, Any]) -> list[GuardVerdict]:
        c = self.config
        verdicts = [output_guards.refusal_detected(final_text)]
        if c.output_schema is not None and c.output_state_key:
            if verdicts[0].triggered:
                # A refusal legitimately carries no structured payload.
                verdicts.append(allow("output.schema", "output",
                                      "skipped: refusal answer carries no structured payload"))
            else:
                verdicts.append(output_guards.schema_guard(
                    state.get(c.output_state_key), c.output_schema, where=c.output_state_key))
        return verdicts


def default_guardset(usecase: str) -> GuardSet:
    """The guard configuration each use case ships with."""
    if usecase == "rfq_intake":
        return GuardSet(GuardConfig(output_state_key="draft_quote", output_schema=QUOTE_SCHEMA))
    return GuardSet()
