"""verdict.py — the one shape every guard returns.

Every guard is a pure function that returns a `GuardVerdict`. The agent loop
records ALL verdicts (triggered or not) in the run trace, so an eval can measure
both catch rate and false-trigger rate from the same data.

Actions, in order of severity:

    break — stop the whole agent run (runaway loop, exhausted budget)
    block — refuse this one thing (bad input, unknown tool) but keep going
            where recovery is possible
    flag  — record a finding without changing control flow (schema mismatch,
            refusal detection); a human or an eval decides what it means
    allow — the guard looked and found nothing

Author: Dimitres Kisimov.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ALLOW = "allow"
BLOCK = "block"
BREAK = "break"
FLAG = "flag"


@dataclass(frozen=True)
class GuardVerdict:
    guard: str      # dotted id, e.g. "input.injection_screen"
    stage: str      # "input" | "loop" | "output"
    triggered: bool
    action: str     # ALLOW | BLOCK | BREAK | FLAG
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"guard": self.guard, "stage": self.stage, "triggered": self.triggered,
                "action": self.action, "reason": self.reason}


def allow(guard: str, stage: str, reason: str = "") -> GuardVerdict:
    """Convenience constructor for the non-triggered case."""
    return GuardVerdict(guard=guard, stage=stage, triggered=False, action=ALLOW, reason=reason)
