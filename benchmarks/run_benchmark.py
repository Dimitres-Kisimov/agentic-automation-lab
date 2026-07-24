"""run_benchmark.py — the evaluation harness behind docs/DECISION_GUIDE.md.

Two things happen here:

1. MEASURED — the full-code agent is run live (mock provider, N repetitions) on
   both use cases; we record steps, tool calls, latency and token estimates.
   The n8n build calls the *same* tools over HTTP, so its business result is
   identical by construction (only orchestration overhead differs) — the harness
   asserts the full-code result shape so the comparison rests on real behaviour.

2. SCORED — the two approaches (plus Power Automate as a documented-only third
   column) are rated 1-5 on nine evaluation dimensions drawn from the low-code
   literature (see docs/EVALUATION_FRAMEWORK.md for the rubric + sources). These
   are judgement scores, clearly labelled as such — not measurements.

Outputs (committed, so the README can show them without a run):
    benchmarks/results/metrics.json     measured full-code metrics
    benchmarks/results/scorecard.md      the 9-dimension comparison table
    benchmarks/results/*.png             charts (needs matplotlib; skipped if absent)

    PYTHONPATH=src python benchmarks/run_benchmark.py [--runs 20]

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
RESULTS = Path(__file__).resolve().parent / "results"

from agentic_lab.usecases import product_enrichment, rfq_intake  # noqa: E402

# --------------------------------------------------------------------------- #
# Scorecard — 1..5, higher = better for that approach on that dimension.
# Rationale + sources are documented in docs/EVALUATION_FRAMEWORK.md.
# --------------------------------------------------------------------------- #
APPROACHES = ["n8n (low-code)", "Python (full-code)", "Power Automate (doc-only)"]
SCORECARD: list[dict] = [
    {"dimension": "Time-to-first-demo", "n8n": 5, "full": 3, "pa": 4,
     "why": "Visual wiring is fastest to a working agent; full-code pays boilerplate up front."},
    {"dimension": "Maintainability at scale", "n8n": 2, "full": 5, "pa": 2,
     "why": "Literature flags weak fault-tolerance / tight platform coupling for low-code."},
    {"dimension": "Testability & CI", "n8n": 2, "full": 5, "pa": 1,
     "why": "Full-code has native pytest + GitHub Actions; low-code unit testing is unusual."},
    {"dimension": "Cost / TCO (self-host)", "n8n": 4, "full": 4, "pa": 2,
     "why": "Self-hosted n8n avoids seat fees; PA adds premium licensing + Copilot credits."},
    {"dimension": "Latency control", "n8n": 3, "full": 5, "pa": 3,
     "why": "Full-code can cache/short-circuit calls; platforms add orchestration hops."},
    {"dimension": "Governance & observability", "n8n": 4, "full": 3, "pa": 5,
     "why": "n8n ships run logs; PA has enterprise DLP/analytics; full-code is DIY."},
    {"dimension": "Extensibility", "n8n": 3, "full": 5, "pa": 2,
     "why": "Code nodes help, but full-code is unbounded; PA is most constrained."},
    {"dimension": "Portability / no lock-in", "n8n": 4, "full": 5, "pa": 1,
     "why": "Open-source n8n JSON runs from a clone; PA flows are tenant-bound."},
    {"dimension": "Versioning (Git diff quality)", "n8n": 3, "full": 5, "pa": 1,
     "why": "Python diffs cleanly; workflow JSON diffs are noisy; PA solutions barely diff."},
]


def measure(build_agent, demo_input, runs: int) -> dict:
    lat, steps, calls, in_tok, out_tok = [], [], [], [], []
    last = None
    for _ in range(runs):
        run = build_agent().run(demo_input())
        assert run.stopped == "answered", "agent did not converge"
        lat.append(run.latency_s)
        steps.append(run.steps)
        calls.append(len(run.tool_calls))
        in_tok.append(run.input_tokens)
        out_tok.append(run.output_tokens)
        last = run
    return {
        "runs": runs,
        "tool_calls": calls[0],
        "steps": steps[0],
        "latency_ms_median": round(statistics.median(lat) * 1000, 3),
        "latency_ms_mean": round(statistics.mean(lat) * 1000, 3),
        "input_tokens_est": in_tok[0],
        "output_tokens_est": out_tok[0],
        "final": last.final,
        "tool_call_sequence": last.tool_calls,
    }


def write_scorecard() -> str:
    def avg(k: str) -> float:
        return round(statistics.mean(row[k] for row in SCORECARD), 2)
    lines = ["# Low-code vs Full-code — scorecard",
             "",
             "Scores 1–5 (higher = better). Judgement ratings from the rubric in "
             "`docs/EVALUATION_FRAMEWORK.md`; the runtime numbers in `metrics.json` are measured.",
             "",
             "| Dimension | n8n (low-code) | Python (full-code) | Power Automate (doc-only) |",
             "|---|:--:|:--:|:--:|"]
    for r in SCORECARD:
        lines.append(f"| {r['dimension']} | {r['n8n']} | {r['full']} | {r['pa']} |")
    lines.append(f"| **Average** | **{avg('n8n')}** | **{avg('full')}** | **{avg('pa')}** |")
    lines += ["", "### Why each score", ""]
    for r in SCORECARD:
        lines.append(f"- **{r['dimension']}** — {r['why']}")
    return "\n".join(lines) + "\n"


def make_charts(metrics: dict) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    import numpy as np

    # 1) grouped bar of the scorecard
    dims = [r["dimension"] for r in SCORECARD]
    x = np.arange(len(dims))
    w = 0.27
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(x - w, [r["n8n"] for r in SCORECARD], w, label="n8n (low-code)", color="#ea4b71")
    ax.bar(x, [r["full"] for r in SCORECARD], w, label="Python (full-code)", color="#2f6bff")
    ax.bar(x + w, [r["pa"] for r in SCORECARD], w, label="Power Automate (doc-only)", color="#8a8f98")
    ax.set_ylim(0, 5.5)
    ax.set_ylabel("score (1-5, higher better)")
    ax.set_xticks(x)
    ax.set_xticklabels(dims, rotation=30, ha="right", fontsize=8)
    ax.set_title("Agentic automation: low-code vs full-code - evaluation scorecard")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(RESULTS / "scorecard.png", dpi=140)
    plt.close(fig)

    # 2) measured full-code runtime per use case
    ucs = list(metrics["measured"])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 3.6))
    a1.bar(ucs, [metrics["measured"][u]["tool_calls"] for u in ucs], color="#2f6bff")
    a1.set_title("tool calls per run (measured)")
    a1.set_ylabel("count")
    a1.tick_params(axis="x", labelsize=8)
    a2.bar(ucs, [metrics["measured"][u]["latency_ms_median"] for u in ucs], color="#1d9e6f")
    a2.set_title("agent-loop latency (mock, ms)")
    a2.set_ylabel("ms")
    a2.tick_params(axis="x", labelsize=8)
    fig.tight_layout()
    fig.savefig(RESULTS / "measured.png", dpi=140)
    plt.close(fig)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=20)
    a = ap.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)

    measured = {
        "rfq_intake": measure(rfq_intake.build_agent, rfq_intake.demo_input, a.runs),
        "product_enrichment": measure(product_enrichment.build_agent,
                                      product_enrichment.demo_input, a.runs),
    }
    scorecard_avg = {
        "n8n": round(statistics.mean(r["n8n"] for r in SCORECARD), 2),
        "full": round(statistics.mean(r["full"] for r in SCORECARD), 2),
        "pa": round(statistics.mean(r["pa"] for r in SCORECARD), 2),
    }
    metrics = {"measured": measured, "scorecard_average": scorecard_avg,
               "note": "latency is the mock-provider loop overhead; swap LLM_PROVIDER=anthropic for real model latency."}
    (RESULTS / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (RESULTS / "scorecard.md").write_text(write_scorecard(), encoding="utf-8")
    charted = make_charts(metrics)

    print("MEASURED (full-code, mock):")
    for u, m in measured.items():
        print(f"  {u:20s} {m['tool_calls']} tool calls, {m['steps']} steps, "
              f"{m['latency_ms_median']} ms median")
    print("SCORECARD averages:", scorecard_avg)
    print("charts:", "written" if charted else "skipped (no matplotlib)")
    print("->", RESULTS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
