"""End-to-end test of the guardrail eval harness: it must run all seeded cases
on the mock LLM, produce identical results on repeat runs (determinism), and
report the measured rates the README quotes."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_eval():
    spec = importlib.util.spec_from_file_location("agent_eval", ROOT / "eval" / "agent_eval.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_eval_runs_end_to_end_and_is_deterministic():
    ev = _load_eval()
    r1 = ev.evaluate()
    r2 = ev.evaluate()
    assert r1 == r2, "eval must be fully deterministic on the mock LLM"

    s = r1["summary"]
    assert s["n_cases"] >= 15
    modes = r1["modes"]
    # every catchable failure mode is caught...
    for mode in ("prompt_injection", "oversized_input", "tool_loop",
                 "call_budget", "unknown_tool", "malformed_output", "refusal_detection"):
        assert modes[mode]["caught"] == modes[mode]["catchable"] > 0, mode
    # ...the semantic injections are measured as missed (screen cannot see them)...
    assert modes["prompt_injection_semantic"]["catchable"] == 0
    assert modes["prompt_injection_semantic"]["caught"] == 0
    # ...and nothing false-triggers on the happy paths.
    assert s["happy_false_trigger_rate"] == 0.0
    assert s["task_correctness"] == 1.0
