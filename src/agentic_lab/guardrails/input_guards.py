"""input_guards.py — checks that run on the raw user input BEFORE the loop starts.

Two guards:

  * max_length        — hard cap on input size; oversized inputs go to a human.
  * injection_screen  — a small, honest PATTERN SCREEN for prompt-injection
                        boilerplate in document text.

HONESTY NOTE on the injection screen: this is a screen, NOT a security
guarantee. It catches the well-known literal phrasings ("ignore previous
instructions", role overrides, spoofed tool output). It structurally cannot
catch semantic attacks — social-engineering phrased in ordinary language,
non-English phrasings, or trivially obfuscated text — because a fixed pattern
list has no understanding of intent. The eval harness (eval/agent_eval.py)
measures exactly that boundary instead of pretending it isn't there. Real
deployments layer model-level defenses and human review on top.

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import re

from .verdict import BLOCK, GuardVerdict, allow

DEFAULT_MAX_INPUT_CHARS = 20_000

# (label, pattern) — deliberately small and literal. Every pattern here is a
# known prompt-injection idiom; anything cleverer is out of scope by design.
INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ignore-previous",
     re.compile(r"\bignore\s+(?:all\s+|any\s+)?(?:previous|prior|above|earlier)\s+"
                r"(?:instructions|prompts|directions|rules)", re.IGNORECASE)),
    ("disregard-instructions",
     re.compile(r"\bdisregard\s+(?:(?:the|your|all|any)\s+)?(?:(?:previous|prior|system)\s+)?"
                r"(?:instructions|prompt|rules)", re.IGNORECASE)),
    ("role-override",
     re.compile(r"\byou\s+are\s+now\s+(?:a|an|the)\b", re.IGNORECASE)),
    ("new-instructions",
     re.compile(r"\bnew\s+(?:system\s+)?(?:instructions|prompt)\s*:", re.IGNORECASE)),
    ("system-prompt-probe",
     re.compile(r"\b(?:reveal|print|show|repeat|output)\s+(?:your\s+|the\s+)?system\s+prompt",
                re.IGNORECASE)),
    ("tool-spoof",  # document text pretending to be tool output / transcript
     re.compile(r"(?:<tool_result>|\bTOOL\s+(?:RESULT|OUTPUT)\s*:|\"role\"\s*:\s*\"tool\")",
                re.IGNORECASE)),
]


def max_length(text: str, limit: int = DEFAULT_MAX_INPUT_CHARS) -> GuardVerdict:
    """Block inputs over `limit` characters (context flooding / cost abuse)."""
    n = len(text or "")
    if n > limit:
        return GuardVerdict("input.max_length", "input", True, BLOCK,
                            f"input is {n} chars, over the {limit}-char limit")
    return allow("input.max_length", "input", f"{n} chars, within the {limit}-char limit")


def injection_screen(text: str) -> GuardVerdict:
    """Screen the input against the literal injection-idiom pattern list."""
    hits = [label for label, pat in INJECTION_PATTERNS if pat.search(text or "")]
    if hits:
        return GuardVerdict("input.injection_screen", "input", True, BLOCK,
                            f"matched injection pattern(s): {', '.join(hits)}")
    return allow("input.injection_screen", "input", "no known injection pattern matched")
