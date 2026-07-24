# Credits & attribution

## Code
All application code © 2026 Dimitres Kisimov, MIT-licensed (see `LICENSE`).

## Data
The product catalog (`data/product_catalog.csv`) and sample RFQ emails
(`data/sample_emails/`) are **synthetic** — invented for this demo. SKUs, prices,
stock levels and customer names are fictional and do not represent any real
company's data. The "Würth" brand string in the catalog is used only as a
plausible industrial-distributor label to frame the use case; this project is
independent and unaffiliated.

## Tools & platforms referenced
| Component | Role | License / terms |
|---|---|---|
| **n8n** | Low-code workflow platform (the low-code build) | Sustainable Use License / fair-code; self-hosted |
| **Anthropic Claude** (optional) | Live LLM provider for the full-code agent | Commercial API; needs your key |
| **Docker / Postgres** | Self-hosting n8n | Apache-2.0 / PostgreSQL License |
| **pytest, ruff, matplotlib** | Dev tooling, tests, charts | MIT / MIT / PSF-BSD-style |
| **GitHub Actions** | CI | GitHub-hosted |

The default run uses a **deterministic mock provider** — no third-party model or
key is required, which is why CI is green without secrets.

## Method sources (see docs/EVALUATION_FRAMEWORK.md)
- Anthropic — *Building Effective Agents* (workflow vs. agent; when to add agency)
- deepset — *AI agents and deterministic workflows: a spectrum*
- Systematic literature review on low-code viability (ScienceDirect, 2026)
- MDPI multisector low-code adoption study; SparkCo TCO / vendor-lock-in analysis
- n8n documentation (Tools Agent, cluster nodes, JSON export)
- Microsoft — *What's new in Copilot Studio* (2025)

## Author
**Dimitres Kisimov** — github.com/Dimitres-Kisimov · Last verified 2026-07-17.
