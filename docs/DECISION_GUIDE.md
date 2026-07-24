# Decision guide — low-code (n8n) vs full-code, for agentic automation

*The deliverable this project exists to produce: a defensible answer to "which
use cases should be built low-code, and which full-code?" — grounded in a working
implementation of both, not opinion.*

## TL;DR

| If the use case is… | Build it… | Because |
|---|---|---|
| A quick internal automation, few tools, low change rate, owned by a business team | **Low-code (n8n)** | Fastest to a working agent; run logs built in; a non-engineer can maintain it |
| Business-critical, high volume, needs tests/CI, tight latency or cost control, many custom tools | **Full-code (Python)** | Testable, observable, portable, unbounded — the scorecard's maintainability/testability/latency columns |
| Anything that must run inside Microsoft 365 with enterprise DLP/governance and no self-hosting | **Power Automate / Copilot Studio** | Native M365 governance — at the cost of portability and Git-native versioning |
| **Most real systems** | **Hybrid** | n8n orchestrates + logs; the hard logic lives in tested Python tools it calls over HTTP (this repo's `tool_server.py`) |

Measured average across nine dimensions (see the [scorecard](../benchmarks/results/scorecard.md)):
**full-code 4.44 · n8n 3.33 · Power Automate 2.33** — but the averages hide the
point: **each approach wins specific columns.** Pick per use case, not per religion.

## The rule of thumb (from Anthropic's "Building Effective Agents")

> Start with the simplest thing that works; add agency (and tooling, and a
> platform) only when the flexibility clearly outweighs the added latency, cost
> and error surface.

Applied here:

1. **Is it even agentic?** If the steps are fixed and known, a deterministic
   workflow (or a plain script) beats an agent — cheaper, faster, debuggable.
   Both use cases in this repo *are* agentic: the RFQ agent makes a
   data-dependent number of tool calls (one lookup + one stock check per line
   item), which a fixed pipeline can't express cleanly.
2. **Who owns it?** Business-team-owned → low-code. Engineering-owned and
   critical → full-code.
3. **What does it integrate with?** M365-bound → Power Automate. Everything else,
   self-hostable → n8n and/or Python.
4. **How often will it change, and can you afford a bug?** High churn + low risk →
   low-code. Low churn + high risk → full-code with tests.

## Where this repo lands each of its own use cases

- **RFQ intake → quote (flagship):** high business value, touches pricing (bug =
  money), needs tests. → **Full-code** for the tool logic, **n8n** as the
  operator-facing front door that logs every run. The **hybrid** in this repo.
- **Product-data enrichment:** medium value, run in bulk, rules evolve. → either
  works; **n8n** if the catalog team owns it, **full-code** if it runs inside a
  data pipeline. Shown both ways so the trade-off is concrete.

## The honest caveats (see also [PROCUREMENT-style limitations](EVALUATION_FRAMEWORK.md#limitations))

- The scorecard scores are **reasoned judgements** from the low-code literature,
  not measurements — the runtime numbers (`metrics.json`) are measured, the
  1–5 ratings are argued in [EVALUATION_FRAMEWORK.md](EVALUATION_FRAMEWORK.md).
- The mock provider proves the *mechanics and control flow*; real token cost and
  model latency need `LLM_PROVIDER=anthropic` (one env var).
- Power Automate is rated from documentation, not a running build, because it has
  no portable artifact — which is itself the finding.
