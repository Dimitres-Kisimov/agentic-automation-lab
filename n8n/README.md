# n8n — the low-code build

The same two agents as `src/agentic_lab/`, built low-code in n8n. Each workflow
is a **Tools Agent** (n8n's LangChain-based AI Agent) wired to a chat model and a
set of **HTTP Request tool nodes** that call the shared Python tool server — so
low-code and full-code run the *identical* tools and catalog. That is what makes
the [benchmark](../benchmarks/) a fair A/B.

| Workflow | Mirrors | Tools (via HTTP) |
|---|---|---|
| `rfq_intake_agent.json` | `usecases/rfq_intake.py` | parse_email · lookup_sku · check_stock · draft_quote |
| `product_enrichment_agent.json` | `usecases/product_enrichment.py` | classify_category · normalize_fields · validate_record |

## Run it (≈5 minutes)

1. **Start the tool server on the host** (exposes the Python tools on :8000):
   ```bash
   PYTHONPATH=src python -m agentic_lab.tool_server
   ```
2. **Start n8n**:
   ```bash
   cp .env.example .env        # set the passwords
   docker compose up -d
   ```
   Open http://localhost:5678 and create the owner account (first run only).
3. **Import a workflow**: top-right menu → *Import from File* → pick
   `n8n/rfq_intake_agent.json`.
4. **Bind credentials**: open the *Anthropic Chat Model* node → select/create an
   Anthropic credential (the exported JSON never contains secrets — this is by
   design, and is exactly the portability point the benchmark measures).
5. **Chat**: click *Chat* and paste an RFQ email (see `../data/sample_emails/`).
   The agent parses it, resolves SKUs, checks stock and drafts a quote — the
   same behaviour you get from `python -m agentic_lab rfq_intake`.

> The HTTP tool nodes point at `http://host.docker.internal:8000/...`; the
> `extra_hosts` mapping in `docker-compose.yml` lets the container reach the
> host-run tool server on Linux/WSL as well as macOS/Windows.

## Screenshots

Drop canvas screenshots here after importing — they are linked from the root
README:

- `docs/img/n8n_rfq_canvas.png` — the RFQ agent graph (trigger → agent → model + 4 tools)
- `docs/img/n8n_rfq_run.png` — a chat run with the tool calls in the execution log

## Why the JSON is the artifact (not a Power Automate export)

n8n workflows serialise to a single, secret-free JSON that diffs and versions in
Git and runs from a `git clone` + Docker. Power Automate / Copilot Studio flows
only export as tenant-bound Power Platform solution `.zip`s that need a licensed
Microsoft environment to run — so they are covered in
[`../docs/POWER_AUTOMATE_COMPARISON.md`](../docs/POWER_AUTOMATE_COMPARISON.md)
as the third, *documented-only*, column of the comparison.
