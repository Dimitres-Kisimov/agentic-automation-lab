# Evaluation framework

How the [scorecard](../benchmarks/results/scorecard.md) is built, so the ratings
are auditable rather than vibes.

## Two kinds of number

| | What | Source | File |
|---|---|---|---|
| **Measured** | tool calls, agent steps, loop latency, token estimates | live runs of the full-code agent | `benchmarks/results/metrics.json` |
| **Scored** | nine 1–5 ratings per approach | reasoned from the literature below | `benchmarks/results/scorecard.md` |

Keeping these separate is deliberate: it is the same honesty discipline as
reporting a model's F-score *and* its failure cases. The runtime numbers come
from `benchmarks/run_benchmark.py`; the 1–5 scores are argued here.

## The nine dimensions (and why each score)

Higher is better. Scores are for *agentic* automation specifically.

1. **Time-to-first-demo** — n8n 5 / full 3 / PA 4. Visual wiring reaches a
   working agent fastest; full-code pays boilerplate before the first run.
2. **Maintainability at scale** — n8n 2 / full 5 / PA 2. The low-code SLR
   literature flags weak fault-tolerance and tight platform coupling as growth
   hits; code refactors normally.
3. **Testability & CI** — n8n 2 / full 5 / PA 1. Full-code has native pytest +
   GitHub Actions (this repo runs both); unit-testing a low-code flow is unusual,
   a PA flow harder still.
4. **Cost / TCO (self-host)** — n8n 4 / full 4 / PA 2. Self-hosted n8n avoids
   seat fees (infra only); full-code is infra + engineering time; PA adds premium
   licensing and Copilot credits. Judge over ~3 years, not month one.
5. **Latency control** — n8n 3 / full 5 / PA 3. Code can cache and short-circuit
   model/tool calls; platforms add orchestration hops.
6. **Governance & observability** — n8n 4 / full 3 / PA 5. n8n ships execution
   logs; PA has enterprise DLP + analytics; full-code observability is DIY
   (OpenTelemetry/LangSmith).
7. **Extensibility** — n8n 3 / full 5 / PA 2. Code nodes help low-code, but
   full-code is unbounded; PA is the most constrained.
8. **Portability / no lock-in** — n8n 4 / full 5 / PA 1. Open-source n8n JSON
   runs from a `git clone` + Docker; PA flows are tenant-bound solution zips.
9. **Versioning (Git diff quality)** — n8n 3 / full 5 / PA 1. Python diffs
   cleanly; workflow JSON diffs are noisy but reviewable; PA solutions barely
   diff.

## Sources

- **Anthropic — Building Effective Agents** — the workflow-vs-agent distinction
  and the "add agency only when it pays" heuristic.
- **deepset — "a spectrum, not a binary"** — framing agentic vs deterministic as
  a continuum.
- **Systematic literature review on low-code viability (ScienceDirect, 2026)** —
  maintainability, testing and versioning gaps.
- **MDPI multisector low-code adoption study**; **SparkCo TCO / vendor-lock-in
  analysis** (3-year TCO, migration cost).
- **n8n docs** — Tools Agent, cluster/sub-nodes, JSON export format.
- **Microsoft — What's new in Copilot Studio (2025)** — PA/Copilot agentic
  features and the solution-export/licensing model.

## Limitations

- Scores are judgement calls; reasonable people can move any of them ±1. They are
  argued, not measured — treat them as a structured opinion, not data.
- Latency in `metrics.json` is the **mock** loop overhead (sub-millisecond); real
  end-to-end latency is dominated by the model and is measured only with
  `LLM_PROVIDER=anthropic`.
- One catalog, two use cases, one distributor domain — the ranking is defensible
  here, not a universal law.
- Power Automate is evaluated from docs, not a running build (no portable
  artifact to run) — a limitation that is also one of the results.
