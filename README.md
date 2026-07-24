# Agentic Automation Lab

![CI](https://github.com/Dimitres-Kisimov/agentic-automation-lab/actions/workflows/ci.yml/badge.svg)

I kept reading that low-code tools like n8n are "good enough" for agentic automation and that you should reach for full code "when things get complex", without anyone showing the actual trade-off. So I built the same use case both ways and scored it. The use case is an RFQ agent: a furniture-distributor emails an order, and an LLM tool-use loop parses it, resolves each line to a SKU, checks stock, and drafts a quote. Off-catalog items get flagged instead of guessed.

I wrote this while teaching myself how agentic loops actually work, mostly for internship applications, so the goal was to build the loop from scratch rather than lean on a framework that hides it.

The whole thing runs with no API key. There's a deterministic mock provider standing in for the model, so `clone` → `pytest` is green in a few seconds and you can watch the agent's tool-use loop without paying for tokens.

<p align="center">
  <img src="benchmarks/results/scorecard.png" alt="Nine-dimension scorecard comparing n8n, Python full-code and Power Automate" width="820">
</p>

Averages across nine dimensions came out full-code 4.44, n8n 3.33, Power Automate 2.33 — but the averages are the least interesting part. Each approach wins specific columns, and the repo is really about which column matters for your situation.

## Running it

```bash
pip install -e ".[dev,charts]"

python -m agentic_lab rfq_intake      # watch the tool-use loop run
pytest -q                             # 15 tests, no key needed
python benchmarks/run_benchmark.py    # regenerate the scorecard + charts
```

A run against the mock provider looks like this (swap `--provider anthropic` for live Claude):

```
AGENT TRACE:
  -> parse_email(...)          customer + 5 line items
  -> lookup_sku(...) x5        resolved to SKUs with prices
  -> check_stock(...) x5       availability + lead time
  -> draft_quote(...)          Quote Q-15325
RESULT: Quote Q-15325 drafted for procurement@acme-bau.de: 5 line items, 911.44 EUR excl. VAT.
METRICS: 13 steps, 12 tool calls, answered
```

The number of tool calls depends on the email, which is the part that makes it genuinely agentic rather than a fixed script.

## How it's put together

The tools (`tools.py`) are written once. The full-code agent imports them directly; the n8n workflow calls the exact same functions over HTTP via `tool_server.py`. That's deliberate — it means the comparison isn't full-code-vs-a-different-implementation, it's two orchestrators driving identical logic. It also makes the "hybrid" story real: n8n on top, tested Python underneath.

Layout worth knowing:

- `src/agentic_lab/` — the from-scratch tool-use loop, provider-agnostic (mock or Claude), instrumented.
- `n8n/*.json` — two importable AI-Agent workflows.
- `benchmarks/` — measured runtime plus the nine-dimension scorecard that feeds `docs/DECISION_GUIDE.md`.

There's a second use case in there too — product-data enrichment — but RFQ intake is the one to look at first.

## The n8n side (optional)

```bash
PYTHONPATH=src python -m agentic_lab.tool_server   # tools on :8000
docker compose up -d                               # n8n on :5678
```

Then import `n8n/rfq_intake_agent.json` and bind an Anthropic credential in the UI. One thing I was careful about: the workflow JSON references credentials by name, never by value, so the exported files are safe to commit — there are no secrets baked into them.

## Honest limitations

- The mock proves control flow and results. Real token cost and latency only show up under `LLM_PROVIDER=anthropic`.
- The 1–5 scorecard ratings are reasoned judgements with sources in `docs/EVALUATION_FRAMEWORK.md`. Only the runtime figures are actually measured — I've tried to keep that line clear rather than dress up opinions as data.
- One catalog, one domain. The ranking holds here; I wouldn't call it universal.

## What I'd add next

A parallel n8n run against the *same* emails so I can put measured latency and cost side by side with the Python path, instead of scoring that dimension by judgement.

---

MIT © 2026 Dimitres Kisimov. All data is synthetic.
