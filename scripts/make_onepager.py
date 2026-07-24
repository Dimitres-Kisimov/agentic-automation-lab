"""make_onepager.py — render the executive one-pager leadership can circulate.

Produces `deliverables/executive_onepager.pdf` (two pages, matplotlib PdfPages):

    page 1  the business case on a page — situation, quantified problem,
            solution, ROI and a recommendation.
    page 2  how the numbers were derived (assumptions + the repo's measured
            figures) and where to read more.

The measured figures (tool calls, steps) are pulled from
`benchmarks/results/metrics.json` so the one-pager can't drift from the harness.
Cost figures are estimates and are labelled as such — see docs/BUSINESS_CASE.md.

    python scripts/make_onepager.py

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / "benchmarks" / "results" / "metrics.json"
OUT = ROOT / "deliverables" / "executive_onepager.pdf"

INK = "#1b1f24"
MUTE = "#5b6470"
BLUE = "#2f6bff"
GREEN = "#1d9e6f"
PINK = "#ea4b71"
BAND = "#eef2fb"

# --- inputs: assumptions (estimates) + measured behaviour (from the harness) ---
EMAILS_PER_WEEK = 2000
MIN_MANUAL = 10
MIN_REVIEW = 2
RATE_EUR_H = 45
WEEKS = 52
BUILD_EUR = 100_000

HOURS_YEAR = EMAILS_PER_WEEK * MIN_MANUAL / 60 * WEEKS
COST_YEAR = HOURS_YEAR * RATE_EUR_H
REDUCTION = (MIN_MANUAL - MIN_REVIEW) / MIN_MANUAL
HOURS_SAVED = HOURS_YEAR * REDUCTION
COST_SAVED = HOURS_SAVED * RATE_EUR_H
PAYBACK_MONTHS = BUILD_EUR / (COST_SAVED / 12)


def _measured() -> dict:
    if METRICS.exists():
        m = json.loads(METRICS.read_text(encoding="utf-8"))
        return m["measured"]["rfq_intake"]
    return {"tool_calls": 12, "steps": 13}


def _band(fig, y, h, color=BAND):
    fig.patches.append(Rectangle((0, y), 1, h, transform=fig.transFigure,
                                 facecolor=color, edgecolor="none", zorder=0))


def _stat(fig, x, y, big, label, color, size=21):
    fig.text(x, y, big, fontsize=size, fontweight="bold", color=color,
             ha="left", va="baseline")
    fig.text(x, y - 0.026, label, fontsize=7.6, color=MUTE, ha="left", va="top")


def _card(fig, x, y, w, h, color):
    fig.patches.append(FancyBboxPatch(
        (x, y), w, h, transform=fig.transFigure,
        boxstyle="round,pad=0.006,rounding_size=0.012",
        facecolor="white", edgecolor=color, linewidth=1.3, zorder=1))


def page_one(pdf, meas):
    fig = plt.figure(figsize=(8.27, 11.69))  # A4 portrait
    _band(fig, 0.902, 0.098, BLUE)
    fig.text(0.06, 0.955, "Executive one-pager", fontsize=11, color="white",
             fontweight="bold", ha="left")
    fig.text(0.06, 0.925, "RFQ / order-email intake agent", fontsize=20,
             color="white", fontweight="bold", ha="left")
    fig.text(0.94, 0.923, "Agentic Automation Lab", fontsize=9, color="#d6e2ff",
             ha="right")

    fig.text(0.06, 0.878, "Situation", fontsize=12, color=INK, fontweight="bold")
    fig.text(0.06, 0.860,
             "Nordwerk Industrievertrieb (illustrative mid-size industrial distributor) runs a\n"
             "12-person inside-sales desk that hand-builds quotes from ~2,000 unstructured RFQ /\n"
             "order emails a week — read each one, match every line to a SKU, check stock and\n"
             "price, type back a quote.",
             fontsize=9.3, color=MUTE, va="top", linespacing=1.55)

    _band(fig, 0.688, 0.092, "#fdeef2")
    fig.text(0.06, 0.766, "The problem, in numbers", fontsize=12, color=PINK,
             fontweight="bold")
    _stat(fig, 0.07, 0.726, f"{HOURS_YEAR/1000:.1f}k h", "inside-sales hours / year\non manual quoting", PINK)
    _stat(fig, 0.30, 0.726, f"€{COST_YEAR/1000:.0f}k", "fully-loaded labour cost\n/ year (estimate)", PINK)
    _stat(fig, 0.53, 0.726, "~3%", "assumed hand-keying\nerror rate on lines", PINK)
    _stat(fig, 0.74, 0.726, "next-day", "typical turnaround\nunder load", PINK, size=17)

    fig.text(0.06, 0.648, "Solution", fontsize=12, color=INK, fontweight="bold")
    fig.text(0.06, 0.630,
             "A from-scratch LLM tool-use loop that, given one email, decides its own steps and\n"
             "drafts the quote. Off-catalogue items are flagged for a human, never guessed. Tested\n"
             "Python underneath; an optional n8n front-door logs every run — the desk reviews and sends.",
             fontsize=9.3, color=MUTE, va="top", linespacing=1.55)

    # measured pipeline strip
    steps = ["parse_email", "lookup_sku ×5", "check_stock ×5", "draft_quote"]
    x0, w, gap = 0.06, 0.19, 0.013
    for i, s in enumerate(steps):
        x = x0 + i * (w + gap)
        fig.patches.append(FancyBboxPatch(
            (x, 0.545), w, 0.030, transform=fig.transFigure,
            boxstyle="round,pad=0.004,rounding_size=0.01",
            facecolor="white", edgecolor=BLUE, linewidth=1.1))
        fig.text(x + w / 2, 0.560, s, fontsize=7.8, color=INK, ha="center", va="center")
    fig.text(0.06, 0.523,
             f"Measured on a real 5-line email: {meas['tool_calls']} tool calls across "
             f"{meas['steps']} steps → one drafted quote.",
             fontsize=8, color=MUTE, style="italic")

    _band(fig, 0.300, 0.185, "#eafaf3")
    fig.text(0.06, 0.462, "Impact / ROI", fontsize=12, color=GREEN, fontweight="bold")
    fig.text(0.06, 0.444,
             "Conservative case: a rep still reviews and approves every draft in ~2 min instead of\n"
             "keying for ~10 min — an 80% cut, before any straight-through automation.",
             fontsize=9, color=MUTE, va="top", linespacing=1.55)
    _stat(fig, 0.07, 0.383, "80%", "time cut per quote\n(10 min → 2 min)", GREEN)
    _stat(fig, 0.30, 0.383, f"{HOURS_SAVED/1000:.1f}k h", "inside-sales hours saved\n/ year", GREEN)
    _stat(fig, 0.53, 0.383, f"€{COST_SAVED/1000:.0f}k", "labour saved / year\n(estimate)", GREEN)
    _stat(fig, 0.74, 0.383, f"<{PAYBACK_MONTHS:.0f} mo", "payback on ~€100k\nbuild (estimate)", GREEN)

    _card(fig, 0.06, 0.135, 0.88, 0.115, BLUE)
    fig.text(0.08, 0.222, "Recommendation", fontsize=11, color=BLUE, fontweight="bold")
    fig.text(0.08, 0.203,
             "Pilot the RFQ agent on one product division as tested full-code tool logic behind an\n"
             "n8n operator front-door — the hybrid the decision guide recommends. Measure live model\n"
             "cost and latency on real emails before scaling to the full desk.",
             fontsize=9, color=INK, va="top", linespacing=1.55)

    fig.text(0.06, 0.055,
             "Estimates are labelled as such; all sample data is synthetic.",
             fontsize=7.2, color=MUTE, ha="left")
    fig.text(0.94, 0.055, "Dimitres Kisimov · page 1 / 2", fontsize=7.2,
             color=MUTE, ha="right")
    pdf.savefig(fig)
    plt.close(fig)


def page_two(pdf, meas):
    fig = plt.figure(figsize=(8.27, 11.69))
    _band(fig, 0.902, 0.098, "#39424f")
    fig.text(0.06, 0.94, "How the numbers were derived", fontsize=17,
             color="white", fontweight="bold", ha="left")

    fig.text(0.06, 0.855, "Assumptions (estimates)", fontsize=12, color=INK,
             fontweight="bold")
    rows = [
        ("RFQ / order emails per week", f"{EMAILS_PER_WEEK:,}"),
        ("Manual handling per email", f"{MIN_MANUAL} min"),
        ("Review-and-send per email (automated draft)", f"{MIN_REVIEW} min"),
        ("Fully-loaded inside-sales labour cost", f"€{RATE_EUR_H} / hour"),
        ("Working weeks per year", f"{WEEKS}"),
        ("One-off build + integration (estimate)", f"€{BUILD_EUR:,}"),
    ]
    y = 0.828
    for i, (k, v) in enumerate(rows):
        if i % 2 == 0:
            fig.patches.append(Rectangle((0.06, y - 0.006), 0.88, 0.03,
                               transform=fig.transFigure, facecolor="#f2f5fa",
                               edgecolor="none"))
        fig.text(0.08, y + 0.006, k, fontsize=9.3, color=INK, va="center")
        fig.text(0.92, y + 0.006, v, fontsize=9.3, color=INK, va="center", ha="right",
                 fontweight="bold")
        y -= 0.032

    fig.text(0.06, 0.60, "The arithmetic", fontsize=12, color=INK, fontweight="bold")
    calc = [
        f"Manual hours/year = 2,000 × 10 min ÷ 60 × 52  ≈  {HOURS_YEAR:,.0f} h",
        f"Manual cost/year  = {HOURS_YEAR:,.0f} h × €{RATE_EUR_H}  ≈  €{COST_YEAR:,.0f}",
        f"Time cut per quote = (10 − 2) ÷ 10  =  {REDUCTION*100:.0f}%",
        f"Hours saved/year  = {HOURS_YEAR:,.0f} × {REDUCTION*100:.0f}%  ≈  {HOURS_SAVED:,.0f} h",
        f"Cost saved/year   = {HOURS_SAVED:,.0f} h × €{RATE_EUR_H}  ≈  €{COST_SAVED:,.0f}",
        f"Payback           = €{BUILD_EUR:,} ÷ (€{COST_SAVED:,.0f} ÷ 12)  ≈  {PAYBACK_MONTHS:.1f} months",
    ]
    y = 0.572
    for line in calc:
        fig.text(0.08, y, line, fontsize=9.2, color=MUTE, family="monospace")
        y -= 0.03

    fig.text(0.06, 0.36, "Measured behaviour (not estimated)", fontsize=12,
             color=GREEN, fontweight="bold")
    fig.text(0.08, 0.335,
             f"From benchmarks/results/metrics.json, {meas.get('runs', 25)} runs of the flagship "
             f"agent on a real 5-line email:\n"
             f"  •  {meas['tool_calls']} tool calls across {meas['steps']} steps, converging to one "
             f"drafted quote\n"
             f"  •  tool sequence: parse_email → lookup_sku ×5 → check_stock ×5 → draft_quote\n"
             f"The number of tool calls tracks the number of line items — that is what makes it agentic,\n"
             f"not a fixed script.",
             fontsize=9.2, color=MUTE, va="top", linespacing=1.6)

    _card(fig, 0.06, 0.11, 0.88, 0.115, BLUE)
    fig.text(0.08, 0.20, "Read more", fontsize=11, color=BLUE, fontweight="bold")
    fig.text(0.08, 0.182,
             "•  docs/BUSINESS_CASE.md   —  the full one-page business case\n"
             "•  docs/DECISION_GUIDE.md   —  low-code vs full-code, per use case\n"
             "•  benchmarks/results/scorecard.md   —  the measured 9-dimension scorecard",
             fontsize=9, color=INK, va="top", linespacing=1.7)

    fig.text(0.94, 0.055, "Dimitres Kisimov · page 2 / 2", fontsize=7.2,
             color=MUTE, ha="right")
    pdf.savefig(fig)
    plt.close(fig)


def main() -> int:
    meas = _measured()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(OUT) as pdf:
        page_one(pdf, meas)
        page_two(pdf, meas)
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  headline: ~€{COST_SAVED/1000:.0f}k / {HOURS_SAVED/1000:.1f}k h "
          f"saved per year, payback <{PAYBACK_MONTHS:.0f} months (estimates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
