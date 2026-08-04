"""task_success.py — measured TASK-SUCCESS eval for the automation flows.

Distinct from the two evals already in the repo:

  * benchmarks/run_benchmark.py  measures *runtime* (steps/latency/tokens) and
    scores low-code vs full-code on judgement dimensions;
  * eval/agent_eval.py           measures the *guardrails* (catch rate on
    adversarial input, false-trigger rate on happy paths).

Neither answers "does the flow get the business task RIGHT?". This harness does:
it runs the EXISTING flows (agentic_lab.usecases.rfq_intake / product_enrichment)
over a bank of deterministic offline task fixtures (eval/tasks/*.json), reads the
business outcome the flow actually produced — the resolved SKUs, the quote total,
which lines it flagged for human review, the enrichment verdict — and checks each
against a hand-verified answer key. It reports per-task pass/fail with failure
reasons, an overall success rate, and writes a CSV + Markdown scorecard.

HONESTY — what this number is and is NOT.
The flows run against the DETERMINISTIC MOCK policy, not a live model. So this
harness measures ORCHESTRATION + TOOL correctness: given the standard tool plan,
does the flow resolve the right SKUs, do the arithmetic, flag off-catalog items,
and reach the right enrichment verdict? It is NOT a measurement of live-LLM task
success. Published end-to-end LLM computer-use lands around ~70% reliable and
carries prompt-injection risk (this repo's documented stance — see the README and
eval/agent_eval.py). The headline here is the CEILING the orchestration allows on
a fixed model, not what a real model would score end to end.

Determinism: no wall-clock, no RNG, no hash-derived ids (draft_quote's quote_id
is deliberately excluded) reach the committed outputs, so re-runs are byte-stable.

    python eval/task_success.py
        -> eval/task_results.json, eval/task_scorecard.md, eval/task_scorecard.csv

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
TASKS_DIR = Path(__file__).resolve().parent / "tasks"
RESULTS_JSON = Path(__file__).resolve().parent / "task_results.json"
SCORECARD_MD = Path(__file__).resolve().parent / "task_scorecard.md"
SCORECARD_CSV = Path(__file__).resolve().parent / "task_scorecard.csv"

from agentic_lab.usecases import product_enrichment, rfq_intake  # noqa: E402

USECASES = {"rfq_intake": rfq_intake, "product_enrichment": product_enrichment}

# Business-outcome fields checked per use case (only those present in a fixture's
# "expect" block are asserted).
OUTCOME_KEYS = {
    "rfq_intake": ["customer", "n_line_items", "skus", "flagged_count", "total_eur"],
    "product_enrichment": ["category", "valid", "missing_fields", "issues"],
}


# --------------------------------------------------------------------------- #
# Load a fixture's input (literal, file, or JSON record).
# --------------------------------------------------------------------------- #
def load_input(task: dict[str, Any]) -> str:
    if "input" in task:
        return task["input"]
    if "input_file" in task:
        return (ROOT / task["input_file"]).read_text(encoding="utf-8")
    if "input_json" in task:
        return json.dumps(task["input_json"])
    raise ValueError(f"task {task['id']!r} has no input/input_file/input_json")


# --------------------------------------------------------------------------- #
# Pull the business outcome out of a finished run (deterministic fields only —
# NEVER the hash-derived quote_id, latency or token counts).
# --------------------------------------------------------------------------- #
def extract_rfq(run: Any) -> dict[str, Any] | None:
    quote = run.state.get("draft_quote")
    if not isinstance(quote, dict) or "line_items" not in quote:
        return None
    lines = quote["line_items"]
    return {
        "customer": quote.get("customer"),
        "n_line_items": len(lines),
        "skus": [li.get("sku") for li in lines],
        "flagged_count": sum(1 for li in lines if not li.get("sku")),
        "total_eur": quote.get("total_eur"),
    }


def extract_enrichment(run: Any) -> dict[str, Any] | None:
    cls = run.state.get("classify_category")
    val = run.state.get("validate_record")
    if not isinstance(cls, dict) or not isinstance(val, dict):
        return None
    return {
        "category": cls.get("category"),
        "valid": val.get("valid"),
        "missing_fields": val.get("missing_fields"),
        "issues": val.get("issues"),
    }


EXTRACT = {"rfq_intake": extract_rfq, "product_enrichment": extract_enrichment}


def _matches(key: str, got: Any, want: Any) -> bool:
    if key == "total_eur":  # compare money at cent precision, not raw float bits
        try:
            return round(float(got), 2) == round(float(want), 2)
        except (TypeError, ValueError):
            return False
    return got == want


# --------------------------------------------------------------------------- #
# Run + score one task
# --------------------------------------------------------------------------- #
def run_task(task: dict[str, Any]) -> dict[str, Any]:
    uc = USECASES[task["usecase"]]
    run = uc.build_agent().run(load_input(task))
    exp = task["expect"]
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})

    if "stopped" in exp:
        ok = run.stopped == exp["stopped"]
        add("stopped", ok, "" if ok else f"expected {exp['stopped']!r}, got {run.stopped!r}")

    outcome = EXTRACT[task["usecase"]](run)
    if outcome is None:
        add("outcome_produced", False,
            "flow produced no business result (no quote / no validation record)")
    else:
        for key in OUTCOME_KEYS[task["usecase"]]:
            if key in exp:
                ok = _matches(key, outcome.get(key), exp[key])
                add(key, ok, "" if ok
                    else f"expected {exp[key]!r}, got {outcome.get(key)!r}")

    if "final_contains" in exp:
        want = exp["final_contains"]
        ok = want.lower() in (run.final or "").lower()
        add("final_contains", ok, "" if ok else f"{want!r} not found in final answer")

    failures = [f"{c['check']}: {c['detail']}" for c in checks if not c["ok"]]
    return {
        "id": task["id"],
        "usecase": task["usecase"],
        "title": task.get("title", ""),
        "stopped": run.stopped,
        "n_checks": len(checks),
        "n_passed": sum(1 for c in checks if c["ok"]),
        "passed": not failures,
        "failures": failures,
        "observed": outcome or {},
        "checks": checks,
    }


def evaluate() -> dict[str, Any]:
    paths = sorted(TASKS_DIR.glob("*.json"))
    tasks = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    rows = [run_task(t) for t in tasks]

    by_uc: dict[str, dict[str, int]] = {}
    for r in rows:
        b = by_uc.setdefault(r["usecase"], {"tasks": 0, "passed": 0})
        b["tasks"] += 1
        b["passed"] += int(r["passed"])

    n_pass = sum(1 for r in rows if r["passed"])
    summary = {
        "n_tasks": len(rows),
        "passed": n_pass,
        "failed": len(rows) - n_pass,
        "success_rate": round(n_pass / len(rows), 4) if rows else 0.0,
        "provider": "mock (deterministic)",
        "measures": "orchestration + tool correctness, not live-model task success",
    }
    return {"summary": summary, "by_usecase": by_uc, "tasks": rows}


# --------------------------------------------------------------------------- #
# Renderers — pure functions of the results, so outputs are byte-stable.
# --------------------------------------------------------------------------- #
def render_markdown(results: dict[str, Any]) -> str:
    s = results["summary"]
    out = [
        "# Task-success scorecard",
        "",
        f"**{s['passed']}/{s['n_tasks']} tasks passed "
        f"({100 * s['success_rate']:.1f}%)** — the existing flows run over "
        f"{s['n_tasks']} deterministic offline task fixtures (`eval/tasks/*.json`), "
        "scored on the business outcome they actually produced.",
        "",
        "> Measured against the **deterministic mock** policy, so this is "
        "orchestration + tool correctness (right SKUs, right totals, right "
        "off-catalog flags, right enrichment verdict) — **not** live-model task "
        "success. Published end-to-end LLM computer-use is ~70% reliable with "
        "prompt-injection risk; see the README and `eval/agent_eval.py`.",
        "",
        "| Task | Use case | Checks | Result | Notes |",
        "|---|---|:--:|:--:|---|",
    ]
    for r in results["tasks"]:
        notes = "; ".join(r["failures"]) if r["failures"] else "—"
        result = "PASS" if r["passed"] else "FAIL"
        out.append(f"| {r['title']} | {r['usecase']} | {r['n_passed']}/{r['n_checks']} "
                   f"| {result} | {notes} |")
    out += ["", "### By use case", ""]
    for uc, b in sorted(results["by_usecase"].items()):
        out.append(f"- **{uc}** — {b['passed']}/{b['tasks']} tasks passed")
    out += [
        "",
        "*Generated by `eval/task_success.py`. Deterministic: no wall-clock, RNG, "
        "or hash-derived ids in this file. © 2026 Dimitres Kisimov — proprietary, "
        "all rights reserved (see LICENSE).*",
        "",
    ]
    return "\n".join(out)


def render_csv(results: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["id", "usecase", "title", "checks_passed", "checks_total",
                "result", "notes"])
    for r in results["tasks"]:
        notes = "; ".join(r["failures"]) if r["failures"] else ""
        w.writerow([r["id"], r["usecase"], r["title"], r["n_passed"], r["n_checks"],
                    "PASS" if r["passed"] else "FAIL", notes])
    return buf.getvalue()


def _table(results: dict[str, Any]) -> str:
    header = ("+------------------------+--------------------+--------+--------+\n"
              "| task                   | use case           | checks | result |\n"
              "+------------------------+--------------------+--------+--------+")
    lines = [header]
    for r in results["tasks"]:
        lines.append(f"| {r['id']:<22} | {r['usecase']:<18} | "
                     f"{r['n_passed']}/{r['n_checks']:<4} | "
                     f"{'PASS' if r['passed'] else 'FAIL':<6} |")
    lines.append("+------------------------+--------------------+--------+--------+")
    return "\n".join(lines)


def main() -> int:
    results = evaluate()
    s = results["summary"]
    print("TASK-SUCCESS EVAL -- mock LLM, deterministic "
          f"({s['n_tasks']} offline task fixtures)\n")
    print(_table(results))
    print(f"\noverall task-success rate : {s['passed']}/{s['n_tasks']} "
          f"({100 * s['success_rate']:.1f}%)")
    for uc, b in sorted(results["by_usecase"].items()):
        print(f"  {uc:<20} {b['passed']}/{b['tasks']}")

    failures = [r for r in results["tasks"] if not r["passed"]]
    if failures:
        print("\nFAILURES:")
        for r in failures:
            print(f"  - {r['id']}: {'; '.join(r['failures'])}")

    print("\nNOTE: measured against the deterministic mock, so this is orchestration "
          "+ tool\n      correctness, not live-model task success. End-to-end LLM "
          "computer-use is\n      ~70% reliable with prompt-injection risk (see README "
          "/ eval/agent_eval.py).")

    RESULTS_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
    SCORECARD_MD.write_text(render_markdown(results), encoding="utf-8")
    SCORECARD_CSV.write_text(render_csv(results), encoding="utf-8")
    print(f"\n-> {RESULTS_JSON}\n-> {SCORECARD_MD}\n-> {SCORECARD_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
