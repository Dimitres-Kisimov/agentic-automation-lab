# Agentic Automation Lab — low-code (n8n) vs full-code, benchmarked

<p align="center">
  <img src="benchmarks/results/scorecard.png" alt="Nine-dimension scorecard comparing n8n low-code, Python full-code and Power Automate for agentic automation" width="820">
  <br>
  <em>The same agentic use case built three ways, scored on nine dimensions — full-code 4.44, n8n 3.33, Power Automate 2.33 average, but each wins specific columns. The point is the decision, not a winner.</em>
</p>

![CI](https://github.com/Dimitres-Kisimov/agentic-automation-lab/actions/workflows/ci.yml/badge.svg)
![python](https://img.shields.io/badge/python-3.10%E2%80%933.12-2f6bff)
![n8n](https://img.shields.io/badge/low--code-n8n-ea4b71)
![agentic](https://img.shields.io/badge/pattern-LLM%20tool--use%20loop-8a4dff)
![license](https://img.shields.io/badge/license-MIT-green)

> **When should an agentic automation be built low-code (n8n) and when full-code?**
> This repo answers that by *building the same use case both ways* — a real RFQ-email→quote
> agent — and measuring the difference. Written for the "Data & AI — (Agentic) Automation
> with Low-code Platforms" problem space.

**One furniture-distributor email in → a priced, stock-checked quote out** — produced by an
LLM tool-use agent that decides its own steps, implemented (1) full-code in Python and
(2) low-code in n8n calling the *same* Python tools, with Power Automate covered as a
documented third option. Everything runs **with no API key** (deterministic mock provider),
so `git clone` → `pytest` is green in seconds.

## Run it in 30 seconds (no key needed)

```bash
git clone https://github.com/Dimitres-Kisimov/agentic-automation-lab.git
cd agentic-automation-lab
pip install -e ".[dev,charts]"

python -m agentic_lab rfq_intake          # watch the agent's tool-use loop
pytest -q                                 # 15 tests, green, key-free
python benchmarks/run_benchmark.py        # regenerate the scorecard + charts
```

Real output (mock provider — swap `--provider anthropic` for live Claude):

```
AGENT TRACE:
  -> parse_email(...)          customer + 5 line items
  -> lookup_sku(...) x5        resolved to SKUs with prices
  -> check_stock(...) x5       availability + lead time
  -> draft_quote(...)          Quote Q-15325
RESULT: Quote Q-15325 drafted for procurement@acme-bau.de: 5 line items, 911.44 EUR excl. VAT.
METRICS: 13 steps, 12 tool calls, answered
```

## What's inside

| Part | What it demonstrates |
|---|---|
| **Full-code agent** (`src/agentic_lab/`) | An LLM tool-use loop from scratch — provider-agnostic (mock / Claude), instrumented, tested. The *agentic* pattern per [Anthropic's definition](docs/ARCHITECTURE.md). |
| **Low-code build** (`n8n/*.json`) | Two importable n8n **AI-Agent** workflows calling the same tools over HTTP. Runnable via `docker compose up`. |
| **Shared tools** (`tools.py` + `tool_server.py`) | One tool implementation, two orchestrators — so the comparison is controlled, and the **hybrid** (n8n + tested Python) is real. |
| **Benchmark** (`benchmarks/`) | Measured runtime + a nine-dimension [scorecard](benchmarks/results/scorecard.md) → a [decision guide](docs/DECISION_GUIDE.md). |
| **CI** (`.github/workflows/ci.yml`) | ruff + pytest + CLI smoke + benchmark + JSON validation on 3.10 & 3.12. |

## The two agentic use cases

1. **RFQ intake → quote** (flagship) — parse an order email, resolve every line item to a
   SKU, check stock, draft a quote; off-catalog items are flagged for review. Data-dependent
   number of tool calls = genuinely agentic.
2. **Product-data enrichment** — classify, normalise and validate a messy catalog record.

Full write-up: [docs/USE_CASES.md](docs/USE_CASES.md).

## The comparison, in one line each

- **n8n (low-code):** fastest to build, run logs built in, business-team-ownable — weaker on
  tests/versioning at scale. ([n8n/README](n8n/README.md))
- **Python (full-code):** testable, portable, unbounded, cheapest to control — slower to
  first demo. ([architecture](docs/ARCHITECTURE.md))
- **Power Automate:** best M365 governance, but no portable artifact and tenant-locked —
  covered in [docs/POWER_AUTOMATE_COMPARISON.md](docs/POWER_AUTOMATE_COMPARISON.md).

**→ Which to use when: [docs/DECISION_GUIDE.md](docs/DECISION_GUIDE.md).**

## The n8n build (5 minutes, optional)

```bash
PYTHONPATH=src python -m agentic_lab.tool_server   # tools on :8000
docker compose up -d                               # n8n on :5678
# import n8n/rfq_intake_agent.json, bind an Anthropic credential, chat an email
```

<!-- add canvas screenshots to docs/img/ after importing -->
<!-- ![n8n RFQ agent](docs/img/n8n_rfq_canvas.png) -->

## About this project

Built end-to-end by **Dimitres Kisimov** to demonstrate, on one focused problem:

- **Agentic AI from first principles** — a tool-use loop, provider abstraction, and the
  workflow-vs-agent distinction applied deliberately.
- **Low-code fluency (n8n)** — real, importable AI-Agent workflows, self-hosted via Docker.
- **Engineering discipline** — src-layout package, pytest, ruff, GitHub Actions CI, a
  key-free mock so anyone can run it, honest measured-vs-scored separation.
- **Analytical evaluation** — a sourced rubric turned into a decision guide, not an opinion.

## Limitations (honest)

- The mock provider proves control flow and results; **real token cost/latency** need
  `LLM_PROVIDER=anthropic`.
- Scorecard 1–5 ratings are **reasoned judgements** (sources in
  [EVALUATION_FRAMEWORK.md](docs/EVALUATION_FRAMEWORK.md)); only the runtime numbers are measured.
- One catalog, one domain — the ranking is defensible here, not a universal law.

## License

MIT © 2026 Dimitres Kisimov. Data is synthetic. See [CREDITS.md](CREDITS.md).
