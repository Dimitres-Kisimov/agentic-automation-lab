"""cost_model.py — deterministic TOKEN & COST model for the automation flows.

The fourth eval in the repo, and deliberately distinct from the other three:

  * benchmarks/run_benchmark.py  measures *runtime* (steps/latency/tokens) on the
    two demo inputs and scores low-code vs full-code on judgement dimensions;
  * eval/agent_eval.py           measures the *guardrails* (catch / false-trigger);
  * eval/task_success.py         measures *task correctness* (right SKUs/total/verdict).

None of them answers "what does running this automation actually COST?". This does:
it runs the EXISTING flows (agentic_lab.usecases.rfq_intake / product_enrichment)
over the SAME offline task bank (eval/tasks/*.json), reads the token counts the
agent already instruments, applies a dated per-model price sheet (eval/pricing.json),
and derives the unit economics — cost per quote, cost per enriched record, cost per
1,000 runs, and an annual projection at the business-case volume. Outputs a
byte-stable JSON + Markdown + CSV.

HONESTY — what these numbers are and are NOT.

  * TOKENS are the DETERMINISTIC MOCK estimate: a chars/4 heuristic in llm.py, not a
    real tokenizer. They model the *shape* of the loop (how context grows per turn),
    not Claude's true tokenization. Real token counts — and therefore real cost —
    only appear under LLM_PROVIDER=anthropic with count_tokens; treat everything here
    as an order-of-magnitude planning model, not a bill.
  * NO PROMPT CACHING is modelled. The agent resends the full transcript every turn,
    so the input tokens reflect an *uncached* loop — the expensive case, on purpose.
    Prompt caching bills cached input at ~0.1x and would cut the input cost of the
    RFQ flow materially; it is a documented lever applied by real deployments, not by
    this model.
  * LATENCY is excluded — it is non-deterministic (wall clock). Loop latency is
    measured separately in benchmarks/run_benchmark.py.
  * PRICES are published list prices as of a dated snapshot (eval/pricing.json);
    they change, and partner platforms price differently.

Determinism: token counts are a pure function of the fixture (verified byte-stable
even under PYTHONHASHSEED=random — draft_quote's hash-derived id has constant length,
so it never shifts a char count). No wall clock, RNG, or hash-derived value reaches
these outputs, so re-runs are byte-identical.

    python eval/cost_model.py
        -> eval/cost_results.json, eval/cost_scorecard.md, eval/cost_scorecard.csv

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
PRICING_PATH = Path(__file__).resolve().parent / "pricing.json"
RESULTS_JSON = Path(__file__).resolve().parent / "cost_results.json"
SCORECARD_MD = Path(__file__).resolve().parent / "cost_scorecard.md"
SCORECARD_CSV = Path(__file__).resolve().parent / "cost_scorecard.csv"

from agentic_lab.usecases import product_enrichment, rfq_intake  # noqa: E402

USECASES = {"rfq_intake": rfq_intake, "product_enrichment": product_enrichment}

# Business volume for the annual projection — grounded, not invented. Only the RFQ
# flow has a stated volume (README business case: ~2,000 RFQ/order emails per week);
# product enrichment is reported as unit economics only (no annual claim).
WORKLOAD = {
    "rfq_intake": {
        "runs_per_week": 2000,
        "runs_per_year": 104000,  # 2000 * 52
        "unit": "RFQ/order email -> quote",
        "basis": "README business case: ~2,000 RFQ/order emails a week (~104,000/year).",
    }
}


# --------------------------------------------------------------------------- #
# Load a fixture's input (literal, file, or JSON record) — same three shapes the
# task bank uses.
# --------------------------------------------------------------------------- #
def load_input(task: dict[str, Any]) -> str:
    if "input" in task:
        return task["input"]
    if "input_file" in task:
        return (ROOT / task["input_file"]).read_text(encoding="utf-8")
    if "input_json" in task:
        return json.dumps(task["input_json"])
    raise ValueError(f"task {task['id']!r} has no input/input_file/input_json")


def load_pricing(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or PRICING_PATH).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Pure cost arithmetic — the only place tokens turn into money.
# --------------------------------------------------------------------------- #
def _cost(input_tokens: int, output_tokens: int, model: dict[str, Any]) -> dict[str, float]:
    """Cost in the price sheet's currency for one run on one model. Prices are
    per 1,000,000 tokens. Rounded to micro-currency so the output is byte-stable."""
    cin = input_tokens / 1_000_000 * model["input"]
    cout = output_tokens / 1_000_000 * model["output"]
    return {
        "input": round(cin, 6),
        "output": round(cout, 6),
        "total": round(cin + cout, 6),
    }


def run_task(task: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
    uc = USECASES[task["usecase"]]
    run = uc.build_agent().run(load_input(task))
    return {
        "id": task["id"],
        "usecase": task["usecase"],
        "title": task.get("title", ""),
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "tool_calls": len(run.tool_calls),
        "steps": run.steps,
        "cost_per_run": {m["id"]: _cost(run.input_tokens, run.output_tokens, m)
                         for m in models},
    }


def evaluate(pricing: dict[str, Any] | None = None) -> dict[str, Any]:
    pricing = pricing or load_pricing()
    models = pricing["models"]
    paths = sorted(TASKS_DIR.glob("*.json"))
    tasks = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    rows = [run_task(t, models) for t in tasks]

    # Per-flow unit economics: mean tokens and mean cost/run, cost per 1,000 runs.
    by_uc: dict[str, Any] = {}
    for uc_name in sorted({r["usecase"] for r in rows}):
        group = [r for r in rows if r["usecase"] == uc_name]
        n = len(group)
        in_tok = sum(r["input_tokens"] for r in group)
        out_tok = sum(r["output_tokens"] for r in group)
        mean_cost = {
            m["id"]: round(sum(r["cost_per_run"][m["id"]]["total"] for r in group) / n, 6)
            for m in models
        }
        by_uc[uc_name] = {
            "runs": n,
            "mean_input_tokens": round(in_tok / n, 1),
            "mean_output_tokens": round(out_tok / n, 1),
            "total_input_tokens": in_tok,
            "total_output_tokens": out_tok,
            "mean_cost_per_run": mean_cost,
            "cost_per_1000_runs": {mid: round(c * 1000, 4) for mid, c in mean_cost.items()},
        }

    # Annual projection — only for flows with a grounded volume.
    projections = []
    for uc_name, wl in WORKLOAD.items():
        if uc_name not in by_uc:
            continue
        mean_cost = by_uc[uc_name]["mean_cost_per_run"]
        projections.append({
            "usecase": uc_name,
            "runs_per_week": wl["runs_per_week"],
            "runs_per_year": wl["runs_per_year"],
            "basis": wl["basis"],
            "annual_cost": {mid: round(c * wl["runs_per_year"], 2) for mid, c in mean_cost.items()},
        })

    summary = {
        "n_tasks": len(rows),
        "provider": "mock (deterministic)",
        "currency": pricing["currency"],
        "price_sheet_as_of": pricing["as_of"],
        "provider_default_model": pricing.get("provider_default_model"),
        "token_basis": "mock chars/4 estimate (llm.py) — NOT a real tokenizer; real "
                       "cost only under LLM_PROVIDER=anthropic",
        "caching": "no prompt caching modelled (uncached loop; input tokens resend the "
                   "full transcript each turn)",
        "latency": "excluded (non-deterministic); measured in benchmarks/run_benchmark.py",
    }
    return {
        "summary": summary,
        "models": models,
        "by_usecase": by_uc,
        "projections": projections,
        "tasks": rows,
    }


# --------------------------------------------------------------------------- #
# Renderers — pure functions of the results, so outputs are byte-stable.
# --------------------------------------------------------------------------- #
def _fmt_usd(x: float) -> str:
    return f"${x:,.2f}"


def render_markdown(results: dict[str, Any]) -> str:
    s = results["summary"]
    models = results["models"]
    default = s.get("provider_default_model")
    out = [
        "# Token & cost model",
        "",
        f"Unit economics of the automation flows, run over the {s['n_tasks']} offline "
        f"task fixtures (`eval/tasks/*.json`) with the deterministic mock provider, "
        f"priced against `eval/pricing.json` (list prices as of **{s['price_sheet_as_of']}**, "
        f"{s['currency']}).",
        "",
        "> **What these numbers are — and are not.** Tokens are the **mock chars/4 "
        "estimate** in `llm.py`, not a real tokenizer, so this is an order-of-magnitude "
        "planning model of the loop's shape — **not a bill**. Real token counts and cost "
        "only appear under `LLM_PROVIDER=anthropic`. **No prompt caching** is modelled "
        "(the loop resends the full transcript each turn, so input tokens reflect the "
        "*uncached*, expensive case; caching bills cached input at ~0.1x). **Latency is "
        "excluded** (non-deterministic — see `benchmarks/run_benchmark.py`). List prices "
        "change and partner platforms price differently.",
        "",
        "### Price sheet",
        "",
        "| Model | Input $/1M | Output $/1M | |",
        "|---|--:|--:|---|",
    ]
    for m in models:
        tag = " **(provider default)**" if m["id"] == default else ""
        out.append(f"| {m['name']} (`{m['id']}`) | {m['input']:.2f} | {m['output']:.2f} "
                   f"|{tag} |")

    out += ["", "### Per-flow unit economics (mock-estimated tokens)", ""]
    header = "| Flow | Runs | Mean in-tok | Mean out-tok | " + \
        " | ".join(f"{m['name']} /1k runs" for m in models) + " |"
    sep = "|---|--:|--:|--:|" + "".join("--:|" for _ in models)
    out += [header, sep]
    for uc_name, b in sorted(results["by_usecase"].items()):
        cells = " | ".join(_fmt_usd(b["cost_per_1000_runs"][m["id"]]) for m in models)
        out.append(f"| {uc_name} | {b['runs']} | {b['mean_input_tokens']:.1f} | "
                   f"{b['mean_output_tokens']:.1f} | {cells} |")

    if results["projections"]:
        out += ["", "### Annual projection at business-case volume", ""]
        for p in results["projections"]:
            out += [
                f"**{p['usecase']}** — {p['runs_per_week']:,}/week "
                f"(~{p['runs_per_year']:,}/year). {p['basis']}",
                "",
                "| Model | Annual token cost |",
                "|---|--:|",
            ]
            for m in models:
                out.append(f"| {m['name']} | {_fmt_usd(p['annual_cost'][m['id']])} |")
            out.append("")
        out.append("> Uses the mean cost per run across the fixtures as an illustrative "
                   "\"average order\" — the 5 RFQ fixtures are a small sample, not a "
                   "traffic distribution. Read it against the business case's labour "
                   "savings: the token cost of running the automation is a rounding error "
                   "next to the head-count it offsets — even before prompt caching.")

    out += ["", "### Per-fixture detail", "",
            "| Task | Flow | In-tok | Out-tok | Calls | " +
            " | ".join(f"{m['name']} /run" for m in models) + " |",
            "|---|---|--:|--:|--:|" + "".join("--:|" for _ in models)]
    for r in results["tasks"]:
        cells = " | ".join(f"${r['cost_per_run'][m['id']]['total']:.6f}" for m in models)
        out.append(f"| {r['id']} | {r['usecase']} | {r['input_tokens']} | "
                   f"{r['output_tokens']} | {r['tool_calls']} | {cells} |")

    out += [
        "",
        "*Generated by `eval/cost_model.py`. Deterministic: no wall-clock, RNG, or "
        "hash-derived value in this file. Tokens are the mock chars/4 estimate, not a "
        "real tokenizer. © 2026 Dimitres Kisimov — proprietary, all rights reserved "
        "(see LICENSE).*",
        "",
    ]
    return "\n".join(out)


def render_csv(results: dict[str, Any]) -> str:
    models = results["models"]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    header = ["id", "usecase", "input_tokens", "output_tokens", "tool_calls", "steps"]
    header += [f"total_usd_{m['id']}" for m in models]
    w.writerow(header)
    for r in results["tasks"]:
        row = [r["id"], r["usecase"], r["input_tokens"], r["output_tokens"],
               r["tool_calls"], r["steps"]]
        row += [f"{r['cost_per_run'][m['id']]['total']:.6f}" for m in models]
        w.writerow(row)
    return buf.getvalue()


def _table(results: dict[str, Any]) -> str:
    models = results["models"]
    name_w = 22
    head = f"| {'flow':<{name_w}} | {'runs':>4} | {'mean in':>7} | {'mean out':>8} |"
    for m in models:
        head += f" {m['id'][:16]:>16} |"
    line = "+" + "-" * (name_w + 2) + "+------+---------+----------+" + \
        "".join("-" * 18 + "+" for _ in models)
    rows = [line, head, line]
    for uc_name, b in sorted(results["by_usecase"].items()):
        row = (f"| {uc_name:<{name_w}} | {b['runs']:>4} | {b['mean_input_tokens']:>7.1f} | "
               f"{b['mean_output_tokens']:>8.1f} |")
        for m in models:
            row += f" {_fmt_usd(b['cost_per_1000_runs'][m['id']]) + '/1k':>16} |"
        rows.append(row)
    rows.append(line)
    return "\n".join(rows)


def main() -> int:
    results = evaluate()
    s = results["summary"]
    print(f"TOKEN & COST MODEL -- mock LLM, deterministic ({s['n_tasks']} task fixtures, "
          f"prices as of {s['price_sheet_as_of']}, {s['currency']})\n")
    print(_table(results))
    for p in results["projections"]:
        print(f"\nannual token cost for {p['usecase']} at {p['runs_per_week']:,}/week "
              f"(~{p['runs_per_year']:,}/yr):")
        for m in results["models"]:
            print(f"  {m['name']:<20} {_fmt_usd(p['annual_cost'][m['id']]):>12}")

    print("\nNOTE: tokens are the mock chars/4 estimate, not a real tokenizer; no prompt\n"
          "      caching is modelled (uncached loop) and latency is excluded. Real cost\n"
          "      only under LLM_PROVIDER=anthropic. See the README 'Token & cost model'.")

    RESULTS_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
    SCORECARD_MD.write_text(render_markdown(results), encoding="utf-8")
    SCORECARD_CSV.write_text(render_csv(results), encoding="utf-8")
    print(f"\n-> {RESULTS_JSON}\n-> {SCORECARD_MD}\n-> {SCORECARD_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
