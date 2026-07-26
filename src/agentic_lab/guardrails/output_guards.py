"""output_guards.py — checks that run on the agent's FINAL answer.

  * schema_guard     — validates the run's structured payload (e.g. the drafted
                       quote) against a JSON-Schema subset; a final answer with
                       a missing or malformed payload is flagged.
  * refusal_detected — detects refusal-to-answer phrasing in the final text.
                       This is detection, not judgement: for an out-of-scope
                       request a refusal is the CORRECT outcome, and the eval
                       scores it that way.

The schema validator is a deliberately small stdlib subset (type / required /
properties / items) — enough to reject malformed answers deterministically
without a jsonschema dependency.

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import re
from typing import Any

from .verdict import FLAG, GuardVerdict, allow

_TYPES: dict[str, type | tuple[type, ...]] = {
    "object": dict, "array": list, "string": str, "integer": int,
    "number": (int, float), "boolean": bool, "null": type(None),
}

REFUSAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bI\s+can(?:'t|not)\s+(?:help|assist|comply|do|process|answer)", re.IGNORECASE),
    re.compile(r"\b(?:unable|not\s+able)\s+to\s+(?:help|assist|comply|process)", re.IGNORECASE),
    re.compile(r"\bI\s+(?:must|will)\s+(?:decline|refuse)\b", re.IGNORECASE),
    re.compile(r"\bI\s+refuse\b", re.IGNORECASE),
    re.compile(r"\bI\s+won't\s+(?:help|assist|do|produce)\b", re.IGNORECASE),
]


def validate_schema(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Return a list of human-readable violations (empty list == valid)."""
    errors: list[str] = []
    t = schema.get("type")
    if t is not None:
        expected = _TYPES.get(t)
        if expected is not None:
            ok = isinstance(instance, expected)
            if t in ("integer", "number") and isinstance(instance, bool):
                ok = False  # bool is an int subclass in Python; not in JSON
            if not ok:
                return [f"{path}: expected {t}, got {type(instance).__name__}"]
    if t == "object":
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{path}.{req}: required field missing")
        for key, sub in schema.get("properties", {}).items():
            if key in instance:
                errors.extend(validate_schema(instance[key], sub, f"{path}.{key}"))
    elif t == "array" and "items" in schema:
        for i, item in enumerate(instance):
            errors.extend(validate_schema(item, schema["items"], f"{path}[{i}]"))
    return errors


def schema_guard(payload: Any, schema: dict[str, Any], where: str = "final") -> GuardVerdict:
    """Flag a final answer whose structured payload is missing or malformed."""
    if payload is None:
        return GuardVerdict("output.schema", "output", True, FLAG,
                            f"structured answer {where!r} missing from the run")
    errors = validate_schema(payload, schema)
    if errors:
        return GuardVerdict("output.schema", "output", True, FLAG,
                            f"{where!r} failed schema validation: " + "; ".join(errors[:5]))
    return allow("output.schema", "output", f"{where!r} matches the expected schema")


def refusal_detected(text: str) -> GuardVerdict:
    """Flag refusal-to-answer phrasing in the final text (detection only)."""
    for pat in REFUSAL_PATTERNS:
        m = pat.search(text or "")
        if m:
            return GuardVerdict("output.refusal", "output", True, FLAG,
                                f"refusal phrasing detected: {m.group(0)!r}")
    return allow("output.refusal", "output", "no refusal phrasing detected")
