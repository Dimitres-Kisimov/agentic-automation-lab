# Architecture

One agentic use case, built three ways, sharing one tool layer — so the
comparison is controlled.

## The three builds

```mermaid
flowchart TB
    email["RFQ email / raw record"]

    subgraph FC["Full-code (Python)  ·  src/agentic_lab"]
      loop["Agent loop (agent.py)"]
      prov["LLM provider (llm.py)<br/>mock · Anthropic"]
      loop <--> prov
    end

    subgraph LC["Low-code (n8n)  ·  n8n/*.json"]
      trig["Chat Trigger"] --> agentnode["AI Agent (Tools Agent)"]
      model["Anthropic Chat Model"] -. ai_languageModel .-> agentnode
    end

    subgraph TOOLS["Shared tools (tools.py)"]
      t1["parse_email"]
      t2["lookup_sku"]
      t3["check_stock"]
      t4["draft_quote"]
    end

    cat[("product_catalog.csv")]

    email --> loop
    email --> trig
    loop -->|Python call| TOOLS
    agentnode -->|HTTP via tool_server.py| TOOLS
    TOOLS --> cat
    loop --> quote["Quote / enriched record"]
    agentnode --> quote
```

The **full-code** agent calls the tools directly as Python functions. The
**low-code** n8n agent calls the *same* functions over HTTP (`tool_server.py`).
Because both hit one implementation and one catalog, any behaviour difference is
orchestration, not logic — which is exactly what the benchmark isolates.

## The agent loop (the "agentic" part)

```mermaid
sequenceDiagram
    participant U as Input (email)
    participant A as Agent loop
    participant M as LLM (mock / Claude)
    participant T as Tools + catalog

    U->>A: raw RFQ email
    loop until the model answers (or max_steps)
        A->>M: transcript + tool specs
        alt model requests a tool
            M-->>A: tool_call(name, args)
            A->>T: execute(name, args)
            T-->>A: JSON result
            A->>A: append result, continue
        else model answers
            M-->>A: final text
        end
    end
    A-->>U: quote + metrics (steps, calls, latency, tokens)
```

The number of loop iterations is **data-dependent** (one lookup + one stock check
per line item). That is the line between an *agent* (model drives control flow)
and a *workflow* (control flow fixed in advance) — see
[DECISION_GUIDE.md](DECISION_GUIDE.md).

## Provider abstraction

`agent.py` never imports a model SDK. It talks to an `LLMProvider` with one
method, `complete(system, messages, tools) -> LLMResponse`. Two implementations:

- **`MockProvider`** — deterministic; a `policy(messages, tools)` function reads
  the transcript and returns the next tool call or the final answer. Zero deps,
  zero key, fully reproducible → CI-safe.
- **`AnthropicProvider`** — real Claude tool-use, imported lazily.

Swap them with one env var (`LLM_PROVIDER`). This is what keeps the benchmark
fair (both builds face the same contract) and the repo runnable by anyone.

## Repo layout

```
src/agentic_lab/       full-code agent: llm, agent, tools, catalog, tool_server, usecases/, CLI
n8n/                   importable workflow JSON (low-code build) + how-to
data/                  product_catalog.csv + sample RFQ emails
benchmarks/            run_benchmark.py + committed results/ (metrics, scorecard, charts)
tests/                 pytest: tools, agents (mock), n8n JSON structure
docs/                  this file + evaluation framework, decision guide, PA comparison, use cases
.github/workflows/     CI: ruff + pytest + CLI smoke + benchmark + JSON validation
docker-compose.yml     self-hosted n8n + Postgres
```
